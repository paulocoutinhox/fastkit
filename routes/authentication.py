from fastapi import APIRouter, Request, Response

from enums.authentication_surface import AuthenticationSurface
from enums.social_provider import SocialProvider
from helpers import captcha
from helpers.auth import CurrentUser
from helpers.authentication_cookie_helper import AuthenticationCookieHelper
from helpers.authentication_helper import AuthenticationHelper
from helpers.authentication_route_helper import AuthenticationRouteHelper
from helpers.db import DatabaseSession
from helpers.settings import settings
from helpers.validation_error import ValidationError
from schemas.authentication_methods_response import AuthenticationMethodsResponse
from schemas.email_login_confirmation import EmailLoginConfirmation
from schemas.email_login_request import EmailLoginRequest
from schemas.email_login_response import EmailLoginResponse
from schemas.login_ticket_request import LoginTicketRequest
from schemas.social_authorization_response import SocialAuthorizationResponse
from schemas.social_connection_request import SocialConnectionRequest
from schemas.social_connection_schema import SocialConnectionSchema
from schemas.token_response import TokenResponse
from services.email_login_service import email_login_service
from services.login_ticket_service import login_ticket_service
from services.social_login_service import social_login_service

router = APIRouter(tags=["auth"])


@router.get("/auth/methods", response_model=AuthenticationMethodsResponse, summary="List the enabled sign-in methods")
async def methods(surface: AuthenticationSurface = AuthenticationSurface.SITE):
    return AuthenticationHelper.methods(surface)


@router.post("/auth/email/request", response_model=EmailLoginResponse, summary="Request a one-time email sign-in code")
async def request_code(request: Request, db: DatabaseSession, payload: EmailLoginRequest):
    """A code request never creates an account and never returns the code itself."""
    AuthenticationHelper.require_email(payload.surface)

    if not await captcha.verify(payload.captcha_answer, payload.captcha_token, request.client.host if request.client else None):
        raise ValidationError("error.captcha-invalid", "captcha_answer")

    brand = await AuthenticationRouteHelper.brand(db, request, payload.surface)
    challenge = await email_login_service.request(db, brand, str(payload.email), payload.surface)

    return EmailLoginResponse(challenge=challenge.token, expires_at=challenge.expires_at, resend_at=challenge.resend_at)


@router.post("/auth/email/confirm", response_model=TokenResponse, summary="Confirm an email code and open a session")
async def confirm_code(request: Request, db: DatabaseSession, payload: EmailLoginConfirmation):
    brand = await AuthenticationRouteHelper.brand(db, request, payload.surface)
    user = await email_login_service.confirm(db, brand, payload.challenge, payload.code, payload.surface)

    return await AuthenticationRouteHelper.session(user)


@router.post("/admin/social/redeem", response_model=TokenResponse, summary="Redeem a browser-bound admin sign-in ticket")
async def redeem_ticket(request: Request, response: Response, db: DatabaseSession, payload: LoginTicketRequest):
    brand = await AuthenticationRouteHelper.brand(db, request, AuthenticationSurface.ADMIN)
    browser = request.cookies.get(AuthenticationCookieHelper.name(payload.ticket), "")
    user = await login_ticket_service.redeem(db, brand.id, payload.ticket, browser)
    AuthenticationCookieHelper.forget(response, payload.ticket)

    return await AuthenticationRouteHelper.session(user)


@router.get("/account/social-connections", response_model=list[SocialConnectionSchema], summary="List this account's social sign-in connections")
async def connections(db: DatabaseSession, user: CurrentUser, surface: AuthenticationSurface = AuthenticationSurface.SITE):
    AuthenticationHelper.ensure_access(user, surface)

    return AuthenticationHelper.connections(surface, await social_login_service.connections(db, user))


@router.post("/account/social-connections/{provider}/start", response_model=SocialAuthorizationResponse, summary="Connect a social identity to this account")
async def connect(request: Request, response: Response, db: DatabaseSession, user: CurrentUser, provider: SocialProvider, payload: SocialConnectionRequest):
    brand = await AuthenticationRouteHelper.brand(db, request, payload.surface)
    destination = "/profile" if payload.surface == AuthenticationSurface.ADMIN else "/account/connections"
    authorization = await social_login_service.start(db, brand, provider, payload.surface, destination, user=user)
    AuthenticationCookieHelper.remember(response, authorization.state, authorization.browser, settings.authentication.social_ttl, provider)

    return SocialAuthorizationResponse(authorization_url=authorization.url)


@router.delete("/account/social-connections/{provider}", status_code=204, summary="Remove a social sign-in connection")
async def disconnect(db: DatabaseSession, user: CurrentUser, provider: SocialProvider, surface: AuthenticationSurface = AuthenticationSurface.SITE):
    AuthenticationHelper.ensure_access(user, surface)
    await social_login_service.disconnect(db, user, provider, surface)
