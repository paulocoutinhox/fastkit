from urllib.parse import quote

from fastapi import APIRouter, File, Form, UploadFile
from starlette.responses import JSONResponse

from enums.user import UserAddressType, UserGender, UserStatus
from helpers import captcha, postal_code
from helpers.crud import RecordId
from helpers.db import DatabaseSession
from helpers.errors import AppError
from helpers.forms import payload_of, validated
from helpers.i18n import translate
from helpers.security import create_token
from helpers.settings import settings
from helpers.site import PageNotFound, inside, notice, paged, redirect, render, sign_in, sign_out
from helpers.storage import storage
from helpers.text import display_name
from routes.site.base import CsrfToken, CurrentPage, PrivatePage, guard, refused_by_captcha
from schemas.auth import AccountUpdateRequest, ConfirmationRequest, NewPasswordRequest, PasswordChangeRequest, PasswordResetRequest, SiteSignUpRequest
from schemas.common import TIMEZONES
from schemas.user import AccountAddressRequest
from services.account import credit_transaction_service, user_balance_service
from services.auth import auth_service
from services.commerce import purchase_service, user_product_service
from services.country import country_service
from services.language import language_service
from services.subscription import subscription_service, user_entitlement_service
from services.user import user_address_service, user_service

PROFILE_FIELDS = tuple(AccountUpdateRequest.model_fields)

ADDRESS_FIELDS = ("line1", "street_number", "complement", "district", "city", "state", "postal_code", "country_code")

# Landing on one of these is landing where somebody just came from, so it is never where signing in puts them.
AUTH_PAGES = ("/account/login", "/account/signup", "/account/password-recovery")

# What the letter's page asks, which is opening the account for a sign up and taking the new address for an account that already has one.
SIGN_UP_QUESTION = {"heading": "site.confirm-sign-up-title", "lead": "site.confirm-sign-up-lead", "button": "site.confirm-sign-up-button"}

ADDRESS_QUESTION = {"heading": "site.confirm-address-title", "lead": "site.confirm-address-lead", "button": "site.confirm-address-button"}

router = APIRouter(include_in_schema=False)


def landing(wanted: str | None) -> str:
    """Where signing in puts somebody: back where they were going, and on their account when they were going nowhere."""
    settled = inside(wanted, "/account")

    return "/account" if settled.split("?")[0] in AUTH_PAGES else settled


def avatar_of(user) -> str | None:
    return storage.url(user.avatar) if user.avatar else None


async def profile_context(db, page, values: dict, errors: dict) -> dict:
    """A number is written the way its country writes it, and the country of an account is the one it writes its address in."""
    held = await user_address_service.find_for_user(db, page.user.id, UserAddressType.MAIN)
    country = await country_service.find_by_code(db, held.country_code) if held else None

    return {
        "values": values,
        "errors": errors,
        "avatar_url": avatar_of(page.user),
        "display_name": display_name(page.user),
        "phone_mask": country.phone_mask if country else None,
        "language_options": [(language.id, language.native_name) for language in await language_service.offered(db)],
        "gender_options": [(gender.value, translate(f"enum.user_gender.{gender.value}")) for gender in UserGender],
        "timezone_options": [(zone, zone) for zone in TIMEZONES],
    }


@router.get("/account/login")
async def login(page: CurrentPage):
    wanted = landing(page.request.query_params.get("next"))

    if page.user is not None:
        return redirect(wanted)

    return render(page, "account/login.html", {"challenge": captcha.issue(), "values": {}, "errors": {}, "next": wanted, "confirms_sign_up": settings.confirm_sign_up})


@router.post("/account/login")
async def sign_in_page(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, login: str = Form(""), password: str = Form(""), captcha_answer: str = Form(""), captcha_token: str = Form(""), next_path: str = Form("", alias="next")):
    guard(page, csrf_token)

    wanted = landing(next_path)

    def again(errors):
        return render(page, "account/login.html", {"challenge": captcha.issue(), "values": {"login": login}, "errors": errors, "next": wanted, "confirms_sign_up": settings.confirm_sign_up}, status_code=422)

    refused_here = await refused_by_captcha(page, captcha_answer, captcha_token)

    if refused_here:
        return again(refused_here)

    try:
        user = await auth_service.authenticate(db, page.brand.id, login, password)
    except AppError as refused:
        return again({"login": refused.message})

    answer = redirect(wanted, [notice("site.signed-in")])
    sign_in(answer, create_token(user.token, user.role, user.session_epoch))

    return answer


@router.post("/account/logout")
async def logout(page: CurrentPage, csrf_token: CsrfToken = None):
    guard(page, csrf_token)

    # Landing on the home signed out is the whole message, so there is no notice to read.
    answer = redirect("/")
    sign_out(answer)

    return answer


@router.get("/account/signup")
async def signup(page: CurrentPage):
    wanted = landing(page.request.query_params.get("next"))

    if page.user is not None:
        return redirect(wanted)

    return render(page, "account/signup.html", {"challenge": captcha.issue(), "values": {}, "errors": {}, "next": wanted})


@router.post("/account/signup")
async def register(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, first_name: str = Form(""), last_name: str = Form(""), email: str = Form(""), password: str = Form(""), captcha_answer: str = Form(""), captcha_token: str = Form(""), next_path: str = Form("", alias="next")):
    guard(page, csrf_token)

    values = {"first_name": first_name, "last_name": last_name or None, "email": email, "password": password}
    payload, errors = validated(SiteSignUpRequest, values)
    wanted = landing(next_path)

    def again(refused):
        return render(page, "account/signup.html", {"challenge": captcha.issue(), "values": values, "errors": refused, "next": wanted}, status_code=422)

    refused_here = errors | await refused_by_captcha(page, captcha_answer, captcha_token)

    if refused_here:
        return again(refused_here)

    try:
        user = await auth_service.register(db, page.brand, payload.model_dump(), wanted)
    except AppError as refused:
        return again({refused.field or "email": refused.message})

    # An account still waiting on its address has nothing to be signed in to, so the page says where to look instead.
    if user.status == UserStatus.PENDING:
        return redirect("/account/login", [notice("site.sign-up-confirmation-sent")])

    answer = redirect(wanted, [notice("site.signed-up")])
    sign_in(answer, create_token(user.token, user.role, user.session_epoch))

    return answer


@router.get("/account/confirm/{token}")
async def confirmation_question(page: CurrentPage, db: DatabaseSession, token: str):
    """A mail client and the scanner in front of it open a link on their own, so the link asks and only the answer sent from the page opens the account."""
    waiting = await auth_service.awaiting_confirmation(db, page.brand.id, token)

    if waiting is None:
        return redirect("/account/login", [notice("error.confirmation-token-invalid", "error")])

    asked = ADDRESS_QUESTION if waiting.pending_email is not None else SIGN_UP_QUESTION

    return render(page, "pages/answer.html", {**asked, "next": page.request.query_params.get("next")})


@router.post("/account/confirm/{token}")
async def confirm_sign_up(page: CurrentPage, db: DatabaseSession, token: str, csrf_token: CsrfToken = None, next_path: str = Form("", alias="next")):
    """Answering puts the person where they were going before the account existed."""
    guard(page, csrf_token)

    try:
        user, opened = await auth_service.confirm_sign_up(db, page.brand.id, token)
    except AppError as refused:
        return redirect("/account/login", [notice(refused.code, "error")])

    if not opened:
        return redirect(landing(next_path or None), [notice("site.address-confirmed")])

    answer = redirect(landing(next_path or None), [notice("site.sign-up-confirmed")])
    sign_in(answer, create_token(user.token, user.role, user.session_epoch))

    return answer


@router.get("/account/confirmation")
async def confirmation_page(page: CurrentPage):
    return render(page, "account/confirmation.html", {"challenge": captcha.issue(), "values": {}, "errors": {}})


@router.post("/account/confirmation")
async def resend_confirmation(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, login: str = Form(""), captcha_answer: str = Form(""), captcha_token: str = Form("")):
    """An address that never got the letter has no other way back in, and the answer is the same one whatever the login names."""
    guard(page, csrf_token)

    payload, errors = validated(ConfirmationRequest, {"login": login})
    refused = errors | await refused_by_captcha(page, captcha_answer, captcha_token)

    if refused:
        return render(page, "account/confirmation.html", {"challenge": captcha.issue(), "values": {"login": login}, "errors": refused}, status_code=422)

    await auth_service.resend_confirmation(db, page.brand, payload.login)

    return redirect("/account/login", [notice("site.confirmation-resent")])


@router.get("/account/password-recovery")
async def password_recovery(page: CurrentPage):
    return render(page, "account/password-recovery.html", {"challenge": captcha.issue(), "values": {}, "errors": {}, "next": landing(page.request.query_params.get("next"))})


@router.post("/account/password-recovery")
async def start_recovery(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, login: str = Form(""), captcha_answer: str = Form(""), captcha_token: str = Form(""), next_path: str = Form("", alias="next")):
    """Where the person was going travels inside the letter, because the recovery is a wait the browser never crosses."""
    guard(page, csrf_token)

    wanted = landing(next_path)
    payload, errors = validated(PasswordResetRequest, {"login": login})
    refused = errors | await refused_by_captcha(page, captcha_answer, captcha_token)

    if refused:
        return render(page, "account/password-recovery.html", {"challenge": captcha.issue(), "values": {"login": login}, "errors": refused, "next": wanted}, status_code=422)

    await auth_service.start_password_reset(db, page.brand, payload.login, wanted)

    # An unknown login answers exactly like a known one, so the page never says who has an account here.
    return redirect("/account/password-recovery", [notice("site.recovery-sent")])


@router.get("/account/reset-password/{token}")
async def reset_password(page: CurrentPage, db: DatabaseSession, token: str):
    """A link that was spent, replaced or left to expire draws no form that can never succeed, and sends the person to ask for another."""
    try:
        await auth_service.recoverable(db, page.brand.id, token)
    except AppError as refused:
        return redirect("/account/password-recovery", [notice(refused.code, "error")])

    return render(page, "account/reset-password.html", {"errors": {}, "next": landing(page.request.query_params.get("next"))})


@router.post("/account/reset-password/{token}")
async def confirm_reset(page: CurrentPage, db: DatabaseSession, token: str, csrf_token: CsrfToken = None, new_password: str = Form(""), next_path: str = Form("", alias="next")):
    guard(page, csrf_token)

    wanted = landing(next_path)
    payload, errors = validated(NewPasswordRequest, {"new_password": new_password})

    if payload is None:
        return render(page, "account/reset-password.html", {"errors": errors, "next": wanted}, status_code=422)

    try:
        await auth_service.confirm_password_reset(db, page.brand.id, token, payload.new_password)
    except AppError as refused:
        return redirect("/account/password-recovery", [notice(refused.code, "error")])

    return redirect(f"/account/login?next={quote(wanted, safe='')}", [notice("site.password-changed")])


@router.get("/account")
async def account(page: PrivatePage, db: DatabaseSession):
    """The hub of the account, which is a list of the places a person goes and never a menu that has to be opened."""
    rights = await user_entitlement_service.list_for_user(db, page.user.id)
    balances = await user_balance_service.list_for_user(db, page.user.id)

    return render(page, "account/index.html", {"avatar_url": avatar_of(page.user), "display_name": display_name(page.user), "identity": user_service.identity_of(page.user), "entitlements": rights, "balances": balances})


@router.get("/account/profile")
async def edit_profile(page: PrivatePage, db: DatabaseSession):
    return render(page, "account/profile.html", await profile_context(db, page, {name: getattr(page.user, name) for name in PROFILE_FIELDS}, {}))


@router.post("/account/profile")
async def save_profile(page: PrivatePage, db: DatabaseSession, csrf_token: CsrfToken = None):
    guard(page, csrf_token)

    values = payload_of(await page.request.form(), PROFILE_FIELDS)
    payload, errors = validated(AccountUpdateRequest, values)

    if payload is None:
        return render(page, "account/profile.html", await profile_context(db, page, values, errors), status_code=422)

    try:
        await auth_service.settle_account(db, page.user, payload.model_dump(exclude_unset=True))
    except AppError as refused:
        return render(page, "account/profile.html", await profile_context(db, page, values, {refused.field or "email": refused.message}), status_code=422)

    return redirect("/account/profile", [notice("site.profile-saved")])


@router.post("/account/avatar")
async def save_avatar(page: PrivatePage, db: DatabaseSession, csrf_token: CsrfToken = None, file: UploadFile = File(...)):
    guard(page, csrf_token)

    try:
        await user_service.settle_avatar(db, page.user, file)
    except AppError as refused:
        return redirect("/account/profile", [notice(refused.code, "error")])

    return redirect("/account/profile", [notice("site.avatar-saved")])


@router.post("/account/avatar/remove")
async def remove_avatar(page: PrivatePage, db: DatabaseSession, csrf_token: CsrfToken = None):
    guard(page, csrf_token)
    await user_service.discard_avatar(db, page.user)

    return redirect("/account/profile", [notice("site.avatar-removed")])


@router.get("/account/password")
async def password(page: PrivatePage):
    return render(page, "account/password.html", {"errors": {}})


@router.post("/account/password")
async def change_password(page: PrivatePage, db: DatabaseSession, csrf_token: CsrfToken = None, current_password: str = Form(""), new_password: str = Form("")):
    guard(page, csrf_token)

    payload, errors = validated(PasswordChangeRequest, {"current_password": current_password, "new_password": new_password})

    if payload is None:
        return render(page, "account/password.html", {"errors": errors}, status_code=422)

    try:
        await auth_service.change_password(db, page.user, payload.current_password, payload.new_password)
    except AppError as refused:
        return render(page, "account/password.html", {"errors": {"current_password": refused.message}}, status_code=422)

    # Every other session ended, and this one is handed the token that replaces the one it arrived with.
    answer = redirect("/account", [notice("site.password-changed")])
    sign_in(answer, create_token(page.user.token, page.user.role, page.user.session_epoch))

    return answer


async def address_context(db, values: dict, errors: dict) -> dict:
    """The country comes first because it is what decides whether the postal code is a field somebody can be helped with."""
    offered = await country_service.list_offered(db)

    return {"values": values, "errors": errors, "countries": [(country.code_iso_3166_1, country.name) for country in offered], "postal_code_countries": ",".join(country.code_iso_3166_1 for country in offered if country.postal_code_provider)}


@router.get("/account/address")
async def address(page: PrivatePage, db: DatabaseSession):
    held = await user_address_service.find_for_user(db, page.user.id, UserAddressType.MAIN)

    return render(page, "account/address.html", await address_context(db, {name: getattr(held, name, None) for name in ADDRESS_FIELDS}, {}))


@router.post("/account/address")
async def save_address(page: PrivatePage, db: DatabaseSession, csrf_token: CsrfToken = None):
    guard(page, csrf_token)

    values = payload_of(await page.request.form(), ADDRESS_FIELDS)
    payload, errors = validated(AccountAddressRequest, values)

    if payload is None:
        return render(page, "account/address.html", await address_context(db, values, errors), status_code=422)

    try:
        await user_address_service.save_for_user(db, page.user.id, UserAddressType.MAIN, payload.model_dump())
    except AppError as refused:
        return render(page, "account/address.html", await address_context(db, values, {refused.field or "country_code": refused.message}), status_code=422)

    return redirect("/account/address", [notice("site.address-saved")])


@router.get("/account/address/postal-code")
async def read_postal_code(page: PrivatePage, db: DatabaseSession, country: str = "", code: str = ""):
    """What a postal code stands for, answered only for a country that has somebody to ask and only to a session of this site."""
    found = await country_service.find_by_code(db, country) if country else None

    if found is None or found.postal_code_provider is None:
        raise PageNotFound()

    place = await postal_code.find(found.postal_code_provider, code)

    if place is None:
        return JSONResponse({"code": "error.postal-code-not-found"}, status_code=404)

    return JSONResponse({"line1": place.line1, "district": place.district, "city": place.city, "state": place.state})


@router.get("/account/subscriptions")
async def subscriptions(page: PrivatePage, db: DatabaseSession):
    return render(page, "account/subscriptions.html", {"subscriptions": await subscription_service.list_for_user(db, page.user.id)})


@router.get("/account/subscriptions/{subscription_id}")
async def subscription(page: PrivatePage, db: DatabaseSession, subscription_id: RecordId):
    held = await subscription_service.find_for_user(db, page.user.id, subscription_id)

    if held is None:
        raise PageNotFound()

    paging = paged(page.request)
    total, payments = await subscription_service.list_transactions(db, page.user.id, subscription_id, paging.limit, paging.offset)

    return render(page, "account/subscription.html", {"subscription": held, "payments": payments, "paging": paging.of(total)})


@router.get("/account/purchases")
async def purchases(page: PrivatePage, db: DatabaseSession):
    paging = paged(page.request)
    total, items = await purchase_service.list_for_user(db, page.user.id, paging.limit, paging.offset)

    return render(page, "account/purchases.html", {"purchases": items, "paging": paging.of(total)})


@router.get("/account/purchases/{purchase_id}")
async def purchase(page: PrivatePage, db: DatabaseSession, purchase_id: RecordId):
    held = await purchase_service.find_for_user(db, page.user.id, purchase_id)

    if held is None:
        raise PageNotFound()

    owned = await user_product_service.owned_by(db, page.user.id, held.product_id)

    return render(page, "account/purchase.html", {"purchase": held, "owned": owned})


@router.get("/account/products")
async def owned(page: PrivatePage, db: DatabaseSession):
    held = await user_product_service.list_for_user(db, page.user.id)

    return render(page, "account/products.html", {"products": [{"name": row.product.name, "slug": row.product.slug, "granted_at": row.granted_at, "image_url": storage.url(row.product.image) if row.product.image else None, "file_url": storage.url(row.product.file) if row.product.file else None} for row in held]})


@router.get("/account/credits")
async def credits(page: PrivatePage, db: DatabaseSession):
    paging = paged(page.request)
    total, items = await credit_transaction_service.list_for_user(db, page.user.id, paging.limit, paging.offset)
    balances = await user_balance_service.list_for_user(db, page.user.id)

    return render(page, "account/credits.html", {"transactions": items, "balances": balances, "paging": paging.of(total)})


@router.get("/account/delete")
async def delete_account(page: PrivatePage):
    return render(page, "account/delete.html", {"identity": user_service.identity_of(page.user), "errors": {}})


@router.post("/account/delete")
async def confirm_delete(page: PrivatePage, db: DatabaseSession, csrf_token: CsrfToken = None, confirmation: str = Form("")):
    guard(page, csrf_token)

    identity = user_service.identity_of(page.user)

    if confirmation.strip().lower() != identity.lower():
        return render(page, "account/delete.html", {"identity": identity, "errors": {"confirmation": notice("error.confirmation-mismatch", "error")["message"]}}, status_code=422)

    await user_service.erase(db, page.user)

    answer = redirect("/", [notice("site.account-erased")])
    sign_out(answer)

    return answer
