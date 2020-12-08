import pytest

from quetz import db_models
from quetz.config import Config


@pytest.fixture
def maintainer(user, db):
    user.role = "maintainer"
    db.commit()


@pytest.mark.parametrize(
    "user_role,expected_status",
    [("owner", 201), ("maintainer", 201), ("member", 201), (None, 403)],
)
def test_create_normal_channel_permissions(auth_client, expected_status):

    response = auth_client.post(
        "/api/channels",
        json={
            "name": "test_create_channel",
            "private": False,
        },
    )
    assert response.status_code == expected_status


@pytest.mark.parametrize("channel_role", ["owner", "maintainer", "member"])
@pytest.mark.parametrize("user_role", ["owner", "maintainer", "member", None])
def test_delete_channel_permissions(
    db, auth_client, public_channel, user_role, channel_role
):

    response = auth_client.delete(f"/api/channels/{public_channel.name}")

    channel = (
        db.query(db_models.Channel)
        .filter(db_models.Channel.name == public_channel.name)
        .one_or_none()
    )

    if user_role in ["owner", "maintainer"] or channel_role in ["owner", "maintainer"]:
        assert response.status_code == 200
        assert channel is None
    else:
        assert response.status_code == 403
        assert channel is not None


@pytest.mark.parametrize("user_role", ["owner"])
def test_delete_channel_with_packages(
    db, auth_client, private_channel, private_package_version, config: Config
):

    pkg_store = config.get_package_store()
    pkg_store.add_file("test-file", private_channel.name, "test_file.txt")
    pkg_store.add_file("second", private_channel.name, "subdir/second_file.txt")

    response = auth_client.delete(f"/api/channels/{private_channel.name}")

    channel = (
        db.query(db_models.Channel)
        .filter(db_models.Channel.name == private_channel.name)
        .one_or_none()
    )

    version = (
        db.query(db_models.PackageVersion)
        .filter_by(package_name=private_package_version.package_name)
        .one_or_none()
    )
    package = (
        db.query(db_models.Package)
        .filter_by(name=private_package_version.package_name)
        .one_or_none()
    )

    files = pkg_store.list_files(private_channel.name)

    assert response.status_code == 200
    assert channel is None
    assert version is None
    assert package is None
    assert not files


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/channels/{channel_name}",
        "/api/channels/{channel_name}/packages",
        "/api/channels/{channel_name}/packages/{package_name}",
        "/api/channels/{channel_name}/packages/{package_name}/versions",
    ],
)
@pytest.mark.parametrize(
    "user_role,expected_status",
    [("owner", 200), ("maintainer", 200), ("member", 403), (None, 403)],
)
def test_permissions_channel_endpoints(
    auth_client,
    private_channel,
    expected_status,
    endpoint,
    private_package,
    private_package_version,
):

    response = auth_client.get(
        endpoint.format(
            channel_name=private_channel.name, package_name=private_package.name
        )
    )
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "channel_role,expected_code",
    [("owner", 200), ("maintainer", 200), ("member", 403), (None, 403)],
)
def test_channel_action_reindex(auth_client, public_channel, expected_code):

    response = auth_client.put(
        f"/api/channels/{public_channel.name}/actions", json={"action": "reindex"}
    )

    assert response.status_code == expected_code


@pytest.mark.parametrize(
    "channel_role,expected_code",
    [("owner", 200), ("maintainer", 200), ("member", 403), (None, 403)],
)
def test_get_channel_members(auth_client, public_channel, expected_code):

    response = auth_client.get(f"/api/channels/{public_channel.name}/members")

    assert response.status_code == expected_code


def test_channel_names_are_case_insensitive(auth_client, maintainer):

    channel_name = "MyChanneL"

    response = auth_client.post(
        "/api/channels", json={"name": channel_name, "private": False}
    )

    assert response.status_code == 201

    response = auth_client.get(f"/api/channels/{channel_name}")

    assert response.status_code == 200
    assert response.json()["name"] == channel_name

    response = auth_client.get(f"/api/channels/{channel_name.lower()}")

    assert response.status_code == 200
    assert response.json()["name"] == channel_name

    response = auth_client.get(f"/api/channels/{channel_name.lower()}/packages")

    assert response.status_code == 200

    assert response.json() == []
    package_filename = "test-package-0.1-0.tar.bz2"
    with open(package_filename, "rb") as fid:
        files = {"files": (package_filename, fid)}
        response = auth_client.post(f"/api/channels/{channel_name}/files/", files=files)

    response = auth_client.get(f"/api/channels/{channel_name.lower()}/packages")
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = auth_client.get(f"/api/channels/{channel_name}/packages")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]['name'] == "test-package"

    response = auth_client.get(
        f"/api/channels/{channel_name}/packages/test-package/versions"
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = auth_client.get(
        f"/api/channels/{channel_name.lower()}/packages/test-package/versions"
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = auth_client.get(
        f"/channels/{channel_name.lower()}/linux-64/repodata.json"
    )
    assert response.status_code == 200
    assert package_filename in response.json()['packages']

    response = auth_client.get(f"/channels/{channel_name}/linux-64/repodata.json")
    assert response.status_code == 200
    assert package_filename in response.json()['packages']

    response = auth_client.get(
        f"/channels/{channel_name.lower()}/linux-64/{package_filename}"
    )
    assert response.status_code == 200

    response = auth_client.get(f"/channels/{channel_name}/linux-64/{package_filename}")
    assert response.status_code == 200


def test_unique_channel_names_are_case_insensitive(auth_client, maintainer):

    channel_name = "MyChanneL"

    response = auth_client.post(
        "/api/channels", json={"name": channel_name, "private": False}
    )

    assert response.status_code == 201

    response = auth_client.post(
        "/api/channels", json={"name": channel_name.lower(), "private": False}
    )

    assert response.status_code == 409
    assert f"{channel_name.lower()} exists" in response.json()['detail']

    response = auth_client.post(
        "/api/channels", json={"name": channel_name.upper(), "private": False}
    )

    assert response.status_code == 409
    assert f"{channel_name.upper()} exists" in response.json()['detail']


def test_unicode_channel_names(auth_client, maintainer):

    channel_name = "검은맘바"

    response = auth_client.post(
        "/api/channels", json={"name": channel_name, "private": False}
    )

    assert response.status_code == 201

    response = auth_client.get("/api/channels")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]['name'] == channel_name

    response = auth_client.get(f"/api/channels/{channel_name}")

    assert response.status_code == 200
    assert response.json()['name'] == channel_name


def test_accents_make_unique_channel_names(auth_client, maintainer):

    channel_names = ["żmija", "zmija", "grün", "grun"]

    for name in channel_names:
        response = auth_client.post(
            "/api/channels", json={"name": name, "private": False}
        )
        assert response.status_code == 201

    response = auth_client.get("/api/channels")

    assert response.status_code == 200

    assert len(response.json()) == 4