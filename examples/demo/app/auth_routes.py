from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from fastkit_core.api.envelope import build_message, success_envelope
from fastkit_core.context.request import update_request_context
from fastkit_core.errors.codes import AUTHORIZATION_DENIED
from fastkit_core.errors.exceptions import AuthorizationError
from fastkit_admin.security import AdminSecurity


class LoginRequest(BaseModel):
    identifier_type: str = "email"
    identifier: str
    password: str
    captcha: dict | None = None


def _user_summary(user, effective_tenant_id: int | None = None) -> dict:
    return {
        "id": str(user.id),
        "display_name": user.display_name or user.email,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_root": user.is_root,
        "effective_tenant_id": effective_tenant_id,
    }


def build_auth_router(runtime, security: AdminSecurity, secure_cookie: bool) -> APIRouter:
    router = APIRouter()
    auth_service = runtime.component("auth_service")
    session_service = runtime.component("session_service")
    audit_service = runtime.component("audit_log_service")
    session_cookie = runtime.settings.auth.session_cookie_name
    runtime.component("captcha_provider").mount_routes(router)

    @router.post("/auth/login")
    async def login(payload: LoginRequest, request: Request, response: Response):
        result = await auth_service.login(
            identifier_type=payload.identifier_type,
            identifier_value=payload.identifier,
            password=payload.password,
            requested_tenant_id=0,
            captcha=payload.captcha,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        if not (result.user.is_staff or result.user.is_root):
            await auth_service.logout(result.session_token)

            raise AuthorizationError(AUTHORIZATION_DENIED, message="This account cannot access the admin panel.")

        response.set_cookie(session_cookie, result.session_token, httponly=True, secure=secure_cookie, samesite="lax", path="/")

        update_request_context(user_id=str(result.user.id))
        await audit_service.record(action="login", resource_type="auth", resource_id=str(result.user.id))

        return success_envelope(data=_user_summary(result.user, result.effective_tenant_id), message=build_message("auth.logged_in", "Signed in successfully."))

    @router.post("/auth/logout")
    async def logout(request: Request, response: Response):
        raw_token = request.cookies.get(session_cookie)

        if raw_token:
            record = await session_service.validate(raw_token)

            if record is not None:
                update_request_context(user_id=str(record.user_id))
                await audit_service.record(action="logout", resource_type="auth", resource_id=str(record.user_id))

            await auth_service.logout(raw_token)

        response.delete_cookie(session_cookie, path="/")

        return success_envelope(message=build_message("auth.logged_out", "Signed out."))

    @router.get("/auth/session")
    async def session(user=Depends(security.get_current_user)):
        return success_envelope(data=_user_summary(user))

    return router
