from fastapi import Request

from fastkit_core.context.request import update_request_context
from fastkit_core.errors.codes import AUTHENTICATION_REQUIRED
from fastkit_core.errors.exceptions import AuthenticationError
from fastkit_accounts.models import User
from fastkit_admin.api import AdminDeps


class AdminSecurity:
    """Cookie-session authentication and authorization wired from the runtime components.

    Reads the session cookie name from ``settings.auth.session_cookie_name`` and resolves
    the current user through the ``session_service``, ``database``, ``authorizer`` and
    ``locale_resolver`` components. Every FastKit project shares this wiring, so nobody has
    to hand-write it.
    """

    def __init__(
        self, runtime, tenant_id: int = 0, locale_cookie: str = "fastkit_locale"
    ):
        self._database = runtime.component("database")
        self._sessions = runtime.component("session_service")
        self._authorizer = runtime.component("authorizer")
        self._resolver = runtime.component("locale_resolver")
        self._session_cookie = runtime.settings.auth.session_cookie_name
        self._locale_cookie = locale_cookie
        self._tenant_id = tenant_id

    async def get_session(self):
        async with self._database.session_factory() as session:
            yield session

    async def get_current_user(self, request: Request):
        raw_token = request.cookies.get(self._session_cookie)

        if not raw_token:
            raise AuthenticationError(
                AUTHENTICATION_REQUIRED, message="authentication is required"
            )

        record = await self._sessions.validate(raw_token)

        if record is None:
            raise AuthenticationError(
                AUTHENTICATION_REQUIRED, message="session is invalid or expired"
            )

        async with self._database.session_factory() as session:
            user = await session.get(User, record.user_id)

        if user is None or not user.is_active:
            raise AuthenticationError(
                AUTHENTICATION_REQUIRED, message="account is not available"
            )

        update_request_context(user_id=str(user.id), tenant_id=user.tenant_id)

        return user

    async def get_optional_user(self, request: Request):
        try:
            return await self.get_current_user(request)
        except AuthenticationError:
            return None

    async def get_locale(self, request: Request):
        return self._resolver.resolve(
            accept_language=request.headers.get("accept-language"),
            cookie_locale=request.cookies.get(self._locale_cookie),
        )

    async def authorize(self, user, permission):
        await self._authorizer.require(user, permission, tenant_id=self._tenant_id)


def build_admin_deps(
    runtime, security=None, audit=None, translate=None, tenant_id: int = 0
):
    """Build a fully-wired ``AdminDeps`` from the runtime.

    Returns ``(deps, security)`` — the ``AdminSecurity`` is returned too so the same
    instance backs any other routers (auth, content, reports) that authenticate the
    request. ``translate`` defaults to the runtime translator when a project does not
    pass its own.
    """

    if security is None:
        security = AdminSecurity(runtime, tenant_id=tenant_id)

    translator = runtime.try_component("translator")

    if translate is None and translator is not None:

        def translate(text, locale):
            return translator.gettext(text, locale=locale)

    deps = AdminDeps(
        get_session=security.get_session,
        get_current_user=security.get_current_user,
        get_locale=security.get_locale,
        authorize=security.authorize,
        get_optional_user=security.get_optional_user,
        audit=audit,
        translate=translate,
        translator=translator,
    )

    return deps, security
