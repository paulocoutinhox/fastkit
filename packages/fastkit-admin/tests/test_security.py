from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from fastkit_core.errors.exceptions import AuthenticationError
from fastkit_admin.security import AdminSecurity, build_admin_deps


class _Session:
    def __init__(self, user):
        self._user = user

    async def get(self, model, user_id):
        return self._user


class _Database:
    def __init__(self, user):
        self._user = user

    @asynccontextmanager
    async def session_factory(self):
        yield _Session(self._user)


class _Sessions:
    def __init__(self, record):
        self._record = record

    async def validate(self, token):
        return self._record


class _Authorizer:
    def __init__(self):
        self.calls = []

    async def require(self, user, permission, tenant_id):
        self.calls.append((user, permission, tenant_id))


class _Resolver:
    def resolve(self, accept_language, cookie_locale):
        return cookie_locale or accept_language or "en"


class _Runtime:
    def __init__(
        self, user=None, record=None, translator=None, cookie_name="fastkit_session"
    ):
        self.settings = SimpleNamespace(
            auth=SimpleNamespace(session_cookie_name=cookie_name)
        )
        self._components = {
            "database": _Database(user),
            "session_service": _Sessions(record),
            "authorizer": _Authorizer(),
            "locale_resolver": _Resolver(),
        }
        self._optional = {"translator": translator} if translator is not None else {}

    def component(self, name):
        return self._components[name]

    def try_component(self, name):
        return self._optional.get(name)


def _request(cookies=None, headers=None):
    return SimpleNamespace(cookies=cookies or {}, headers=headers or {})


def _user(active=True, tenant_id=None):
    return SimpleNamespace(id=7, is_active=active, tenant_id=tenant_id)


async def test_get_session_yields_a_session():
    security = AdminSecurity(_Runtime())

    async for session in security.get_session():
        assert isinstance(session, _Session)


async def test_get_current_user_requires_a_cookie():
    security = AdminSecurity(_Runtime())

    with pytest.raises(AuthenticationError):
        await security.get_current_user(_request())


async def test_get_current_user_rejects_invalid_session():
    security = AdminSecurity(_Runtime(record=None))

    with pytest.raises(AuthenticationError):
        await security.get_current_user(_request(cookies={"fastkit_session": "t"}))


async def test_get_current_user_rejects_missing_account():
    runtime = _Runtime(user=None, record=SimpleNamespace(user_id=7))
    security = AdminSecurity(runtime)

    with pytest.raises(AuthenticationError):
        await security.get_current_user(_request(cookies={"fastkit_session": "t"}))


async def test_get_current_user_rejects_inactive_account():
    runtime = _Runtime(user=_user(active=False), record=SimpleNamespace(user_id=7))
    security = AdminSecurity(runtime)

    with pytest.raises(AuthenticationError):
        await security.get_current_user(_request(cookies={"fastkit_session": "t"}))


async def test_get_current_user_returns_the_active_user():
    user = _user()
    runtime = _Runtime(user=user, record=SimpleNamespace(user_id=7))
    security = AdminSecurity(runtime)

    resolved = await security.get_current_user(
        _request(cookies={"fastkit_session": "t"})
    )

    assert resolved is user


async def test_get_current_user_stamps_the_actor_tenant_into_the_request_context():
    from fastkit_core.context.request import get_request_context

    user = _user(tenant_id=42)
    runtime = _Runtime(user=user, record=SimpleNamespace(user_id=7))
    security = AdminSecurity(runtime)

    await security.get_current_user(_request(cookies={"fastkit_session": "t"}))
    context = get_request_context()

    assert context.user_id == "7"
    assert context.tenant_id == 42


async def test_get_current_user_honours_the_configured_cookie_name():
    user = _user()
    runtime = _Runtime(
        user=user, record=SimpleNamespace(user_id=7), cookie_name="app_sid"
    )
    security = AdminSecurity(runtime)

    resolved = await security.get_current_user(_request(cookies={"app_sid": "t"}))

    assert resolved is user


async def test_get_optional_user_returns_user_when_authenticated():
    user = _user()
    runtime = _Runtime(user=user, record=SimpleNamespace(user_id=7))
    security = AdminSecurity(runtime)

    assert (
        await security.get_optional_user(_request(cookies={"fastkit_session": "t"}))
        is user
    )


async def test_get_optional_user_swallows_authentication_errors():
    security = AdminSecurity(_Runtime())

    assert await security.get_optional_user(_request()) is None


async def test_get_locale_uses_the_resolver():
    security = AdminSecurity(_Runtime())

    locale = await security.get_locale(
        _request(cookies={"fastkit_locale": "pt"}, headers={"accept-language": "en"})
    )

    assert locale == "pt"


async def test_authorize_delegates_to_the_authorizer_with_the_tenant():
    runtime = _Runtime()
    security = AdminSecurity(runtime, tenant_id=5)

    await security.authorize("user", "products.view")

    assert runtime.component("authorizer").calls == [("user", "products.view", 5)]


def test_build_admin_deps_wires_the_security_and_translator():
    translator = SimpleNamespace(gettext=lambda text, locale: f"{locale}:{text}")
    runtime = _Runtime(translator=translator)

    deps, security = build_admin_deps(runtime)

    assert isinstance(security, AdminSecurity)
    assert deps.get_current_user == security.get_current_user
    assert deps.translate("hi", "pt") == "pt:hi"


def test_build_admin_deps_leaves_translate_unset_without_a_translator():
    deps, _ = build_admin_deps(_Runtime())

    assert deps.translate is None


def test_build_admin_deps_honours_an_explicit_security_and_translate():
    security = AdminSecurity(_Runtime())

    def translate(text, locale):
        return text

    deps, returned = build_admin_deps(
        _Runtime(), security=security, translate=translate
    )

    assert returned is security
    assert deps.translate is translate
