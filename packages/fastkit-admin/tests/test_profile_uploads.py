import httpx
import pytest_asyncio
from fastapi import FastAPI
from types import SimpleNamespace

from fastkit_core.errors.exceptions import FastKitError
from fastkit_core.errors.handlers import fastkit_exception_handler
from fastkit_admin.api import AdminDeps
from fastkit_admin.profile import build_profile_router
from fastkit_admin.uploads import build_upload_router


class FakeAccountService:
    def __init__(self, user):
        self.user = user
        self.identifiers = [
            SimpleNamespace(id="id-1", type="email", value="user@acme.com")
        ]
        self.password_hash = None
        self.added = []
        self.removed = []

    def identifier_types(self):
        return ["email", "phone", "username"]

    async def list_identifiers(self, user_id):
        return self.identifiers

    async def update_profile(self, user_id, **changes):
        for key, value in changes.items():
            if value is not None:
                setattr(self.user, key, value)

        return self.user

    async def set_password_hash(self, user_id, password_hash):
        self.password_hash = password_hash

    async def add_identifier(self, user_id, tenant_id, identifier_type, value):
        self.added.append((identifier_type, value))

    async def remove_identifier(self, user_id, identifier_id):
        self.removed.append(identifier_id)


class FakePasswordService:
    def verify(self, password_hash, password):
        return password == "correct-password"

    def hash(self, password):
        return f"hashed:{password}"


def make_user():
    profile = SimpleNamespace(avatar_file_id=None)

    return SimpleNamespace(
        id="user-1",
        tenant_id=None,
        password_hash="stored",
        display_name="Ada",
        email="user@acme.com",
        first_name="Ada",
        last_name="L",
        preferred_locale="en",
        timezone="UTC",
        profile=profile,
    )


@pytest_asyncio.fixture
async def profile_client():
    user = make_user()
    account_service = FakeAccountService(user)
    app = FastAPI()
    app.add_exception_handler(FastKitError, fastkit_exception_handler)

    async def get_current_user():
        return user

    async def get_session():
        yield None

    async def upload_avatar(data, filename, content_type):
        return {"url": "/media/avatar.webp", "file_id": "asset-1"}

    deps = AdminDeps(
        get_session=get_session,
        get_current_user=get_current_user,
        get_locale=lambda: "en",
    )
    app.include_router(
        build_profile_router(
            deps, account_service, FakePasswordService(), upload_avatar=upload_avatar
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://admin"
    ) as client:
        yield client, account_service, user


async def test_get_profile(profile_client):
    client, _, _ = profile_client

    body = (await client.get("/profile")).json()

    assert body["data"]["display_name"] == "Ada"
    assert body["data"]["identifiers"][0]["type"] == "email"


async def test_update_profile(profile_client):
    client, _, user = profile_client

    body = (await client.put("/profile", json={"display_name": "Ada Lovelace"})).json()

    assert body["data"]["display_name"] == "Ada Lovelace"
    assert user.display_name == "Ada Lovelace"


async def test_update_profile_triggers_audit_hook():
    user = make_user()
    account_service = FakeAccountService(user)
    app = FastAPI()
    app.add_exception_handler(FastKitError, fastkit_exception_handler)
    recorded = []

    async def get_current_user():
        return user

    async def get_session():
        yield None

    async def audit(action, entity, entity_id):
        recorded.append((action, entity, entity_id))

    deps = AdminDeps(
        get_session=get_session,
        get_current_user=get_current_user,
        get_locale=lambda: "en",
        audit=audit,
    )
    app.include_router(
        build_profile_router(deps, account_service, FakePasswordService())
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://admin"
    ) as client:
        await client.put("/profile", json={"display_name": "Grace"})

    assert recorded == [("profile_update", "profile", "user-1")]


async def test_change_password_success(profile_client):
    client, account_service, _ = profile_client

    body = (
        await client.post(
            "/profile/password",
            json={
                "current_password": "correct-password",
                "new_password": "brand-new-secret",
            },
        )
    ).json()

    assert body["message"]["code"] == "profile.password_changed"
    assert account_service.password_hash == "hashed:brand-new-secret"


async def test_change_password_wrong_current(profile_client):
    client, _, _ = profile_client

    response = await client.post(
        "/profile/password", json={"current_password": "wrong", "new_password": "x"}
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "current_password"


async def test_add_and_remove_identifier(profile_client):
    client, account_service, _ = profile_client

    await client.post(
        "/profile/identifiers", json={"type": "phone", "value": "+5511999998888"}
    )
    assert account_service.added == [("phone", "+5511999998888")]

    await client.delete("/profile/identifiers/id-1")
    assert account_service.removed == ["id-1"]


async def test_add_identifier_rejects_unknown_type(profile_client):
    client, account_service, _ = profile_client

    response = await client.post(
        "/profile/identifiers", json={"type": "aaaa", "value": "x@y.com"}
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "type"
    assert account_service.added == []


async def test_profile_exposes_identifier_types(profile_client):
    client, _, _ = profile_client

    body = (await client.get("/profile")).json()

    assert body["data"]["identifier_types"] == ["email", "phone", "username"]


async def test_upload_avatar(profile_client):
    client, _, user = profile_client

    response = await client.post(
        "/profile/avatar", files={"file": ("a.png", b"bytes", "image/png")}
    )

    assert response.json()["data"]["url"] == "/media/avatar.webp"


async def test_upload_avatar_attaches_the_asset_to_the_user():
    user = make_user()
    account_service = FakeAccountService(user)
    app = FastAPI()
    app.add_exception_handler(FastKitError, fastkit_exception_handler)
    links = []

    async def get_current_user():
        return user

    async def get_session():
        yield None

    async def upload_avatar(data, filename, content_type):
        return {"url": "/media/avatar.webp", "file_id": "asset-1"}

    class RecordingAssets:
        async def link(self, owner_type, owner_id, slot, asset_id):
            links.append((owner_type, str(owner_id), slot, asset_id))

    deps = AdminDeps(
        get_session=get_session,
        get_current_user=get_current_user,
        get_locale=lambda: "en",
    )
    app.include_router(
        build_profile_router(
            deps,
            account_service,
            FakePasswordService(),
            upload_avatar=upload_avatar,
            files=RecordingAssets(),
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://admin"
    ) as client:
        await client.post(
            "/profile/avatar", files={"file": ("a.png", b"bytes", "image/png")}
        )

    assert links == [("user", "user-1", "avatar", "asset-1")]


async def test_identifier_without_normalizer_shows_raw_value():
    from fastkit_admin.profile import profile_summary

    user = make_user()
    identifiers = [
        SimpleNamespace(id="id-2", type="unknown-provider", value="raw-value")
    ]

    summary = profile_summary(user, identifiers, ["email"])

    assert summary["identifiers"][0]["value"] == "raw-value"
    assert summary["identifier_types"] == ["email"]


async def test_upload_router():
    app = FastAPI()
    app.add_exception_handler(FastKitError, fastkit_exception_handler)

    async def get_current_user():
        return SimpleNamespace(id="u")

    async def image_handler(data, filename, content_type):
        return {"url": "/media/x.png", "file_id": "asset-9"}

    async def file_handler(data, filename, content_type):
        return {"url": "/media/doc.txt", "file_id": None}

    deps = AdminDeps(
        get_session=lambda: None,
        get_current_user=get_current_user,
        get_locale=lambda: "en",
    )
    app.include_router(
        build_upload_router(deps, {"image": image_handler, "file": file_handler})
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://admin"
    ) as client:
        image = (
            await client.post(
                "/uploads/image", files={"file": ("x.png", b"data", "image/png")}
            )
        ).json()
        document = (
            await client.post(
                "/uploads/file", files={"file": ("d.txt", b"d", "text/plain")}
            )
        ).json()
        missing = await client.post(
            "/uploads/other", files={"file": ("x", b"x", "text/plain")}
        )

    assert image["data"]["url"] == "/media/x.png"
    assert image["data"]["file_id"] == "asset-9"
    assert document["data"]["file_id"] is None
    assert missing.status_code == 404
