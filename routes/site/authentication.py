from urllib.parse import quote

from fastapi import APIRouter, Form, Query

from enums.authentication_surface import AuthenticationSurface
from enums.social_provider import SocialProvider
from helpers import captcha
from helpers.app_error import AppError
from helpers.authentication_cookie_helper import AuthenticationCookieHelper
from helpers.authentication_error import AuthenticationError
from helpers.authentication_helper import AuthenticationHelper
from helpers.authentication_route_helper import AuthenticationRouteHelper
from helpers.db import DatabaseSession
from helpers.forms import validated
from helpers.not_found_error import NotFoundError
from helpers.page_not_found import PageNotFound
from helpers.security import create_token
from helpers.settings import settings
from helpers.site import inside, notice, redirect, render, sign_in
from helpers.validation_error import ValidationError
from routes.site.account import landing
from routes.site.base import CsrfToken, CurrentPage, PrivatePage, guard, refused_by_captcha
from schemas.email_login_confirmation import EmailLoginConfirmation
from schemas.email_login_request import EmailLoginRequest
from schemas.social_callback_request import SocialCallbackRequest
from services.email_login_service import email_login_service
from services.login_ticket_service import login_ticket_service
from services.social_login_service import social_login_service

router = APIRouter(include_in_schema=False)


@router.get("/account/email-login")
async def email_login(page: CurrentPage):
    AuthenticationRouteHelper.require_site_email()

    return render(page, "account/email-login.html", {"values": {}, "errors": {}, "challenge": captcha.issue(), "next": landing(page.request.query_params.get("next"))})


@router.post("/account/email-login")
async def request_email_code(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, email: str = Form(""), captcha_answer: str = Form(""), captcha_token: str = Form(""), next_path: str = Form("", alias="next")):
    guard(page, csrf_token)
    AuthenticationRouteHelper.require_site_email()

    wanted = landing(next_path)
    payload, errors = validated(EmailLoginRequest, {"email": email, "captcha_answer": captcha_answer, "captcha_token": captcha_token})
    errors |= await refused_by_captcha(page, captcha_answer, captcha_token)

    if errors:
        return render(page, "account/email-login.html", {"values": {"email": email}, "errors": errors, "challenge": captcha.issue(), "next": wanted}, status_code=422)

    challenge = await email_login_service.request(db, page.brand, str(payload.email), AuthenticationSurface.SITE)

    return redirect(f"/account/email-login/confirm?challenge={quote(challenge.token, safe='')}&next={quote(wanted, safe='')}", [notice("site.sign-in-code-sent")])


@router.get("/account/email-login/confirm")
async def email_code(page: CurrentPage):
    AuthenticationRouteHelper.require_site_email()

    return render(page, "account/email-code.html", {"values": {}, "errors": {}, "challenge": page.request.query_params.get("challenge", ""), "next": landing(page.request.query_params.get("next"))})


@router.post("/account/email-login/confirm")
async def confirm_email_code(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, challenge: str = Form(""), code: str = Form(""), next_path: str = Form("", alias="next")):
    guard(page, csrf_token)
    AuthenticationRouteHelper.require_site_email()

    wanted = landing(next_path)
    payload, errors = validated(EmailLoginConfirmation, {"challenge": challenge, "code": code})

    if errors:
        return render(page, "account/email-code.html", {"values": {}, "errors": errors, "challenge": challenge, "next": wanted}, status_code=422)

    try:
        user = await email_login_service.confirm(db, page.brand, payload.challenge, payload.code, AuthenticationSurface.SITE)
    except AppError as error:
        return render(page, "account/email-code.html", {"values": {}, "errors": {"code": error.message}, "challenge": challenge, "next": wanted}, status_code=422)

    answer = redirect(wanted, [notice("site.signed-in")])
    sign_in(answer, create_token(user.token, user.role, user.session_epoch))

    return answer


@router.get("/account/social/{provider}/start")
async def start_social(page: CurrentPage, db: DatabaseSession, provider: SocialProvider, surface: AuthenticationSurface = AuthenticationSurface.SITE, next_path: str = Query("", alias="next", max_length=2048)):
    wanted = landing(next_path) if surface == AuthenticationSurface.SITE else inside(next_path, "/")

    try:
        authorization = await social_login_service.start(db, page.brand, provider, surface, wanted)
    except NotFoundError as error:
        raise PageNotFound() from error
    answer = redirect(authorization.url)
    AuthenticationCookieHelper.remember(answer, authorization.state, authorization.browser, settings.authentication.social_ttl, provider)

    return answer


@router.get("/account/social/{provider}/callback")
@router.post("/account/social/{provider}/callback")
async def social_callback(page: CurrentPage, db: DatabaseSession, provider: SocialProvider):
    if page.request.method == "POST" and provider != SocialProvider.APPLE:
        raise PageNotFound()

    incoming = await page.request.form() if page.request.method == "POST" else page.request.query_params
    payload, errors = validated(SocialCallbackRequest, {name: incoming.get(name) for name in ("state", "code", "error")})

    if errors:
        return render(page, "account/social-error.html", {"failure": notice("error.social-attempt-invalid", "error")["message"]}, status_code=400)

    browser = page.request.cookies.get(AuthenticationCookieHelper.name(payload.state), "")

    try:
        attempt = await social_login_service.consume(db, page.brand, provider, payload.state, browser)
    except AppError as error:
        answer = render(page, "account/social-error.html", {"failure": error.message}, status_code=400)
        AuthenticationCookieHelper.forget(answer, payload.state)

        return answer

    surface = attempt.surface
    wanted = attempt.next_path
    connecting = attempt.user_id is not None

    try:
        if payload.error:
            raise AuthenticationError("error.social-denied")

        if not payload.code:
            raise ValidationError("error.social-response-invalid")

        user = await social_login_service.complete(db, attempt, payload.code)
    except AppError as error:
        if surface == AuthenticationSurface.ADMIN:
            answer = redirect(f"{settings.admin_path}/login#sign-in-error={quote(error.code, safe='')}")
        else:
            answer = redirect("/account/connections" if connecting else "/account/login", [notice(error.code, "error")])

        AuthenticationCookieHelper.forget(answer, payload.state)

        return answer

    if connecting:
        if surface == AuthenticationSurface.ADMIN:
            answer = redirect(f"{settings.admin_path}/profile")
        else:
            answer = redirect("/account/connections", [notice("site.social-connected")])
    elif surface == AuthenticationSurface.SITE:
        answer = redirect(wanted, [notice("site.signed-in")])
        sign_in(answer, create_token(user.token, user.role, user.session_epoch))
    else:
        ticket = await login_ticket_service.create(db, page.brand.id, user, browser)
        answer = redirect(f"{settings.admin_path}/login?next={quote(wanted, safe='')}#sign-in={ticket}")
        AuthenticationCookieHelper.remember(answer, ticket, browser, settings.authentication.ticket_ttl)

    AuthenticationCookieHelper.forget(answer, payload.state)

    return answer


@router.get("/account/connections")
async def social_connections(page: PrivatePage, db: DatabaseSession):
    methods = AuthenticationHelper.connections(AuthenticationSurface.SITE, await social_login_service.connections(db, page.user))

    return render(page, "account/connections.html", {"social_methods": methods})


@router.post("/account/connections/{provider}/connect")
async def connect_social(page: PrivatePage, db: DatabaseSession, provider: SocialProvider, csrf_token: CsrfToken = None):
    guard(page, csrf_token)

    authorization = await social_login_service.start(db, page.brand, provider, AuthenticationSurface.SITE, "/account/connections", page.user)
    answer = redirect(authorization.url)
    AuthenticationCookieHelper.remember(answer, authorization.state, authorization.browser, settings.authentication.social_ttl, provider)

    return answer


@router.post("/account/connections/{provider}/remove")
async def remove_social(page: PrivatePage, db: DatabaseSession, provider: SocialProvider, csrf_token: CsrfToken = None):
    guard(page, csrf_token)

    try:
        await social_login_service.disconnect(db, page.user, provider, AuthenticationSurface.SITE)
    except AppError as error:
        return redirect("/account/connections", [notice(error.code, "error")])

    return redirect("/account/connections", [notice("site.social-disconnected")])
