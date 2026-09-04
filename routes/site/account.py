from fastapi import APIRouter, File, Form, UploadFile
from pydantic import EmailStr, Field
from starlette.responses import JSONResponse

from enums.user import UserAddressType
from helpers import captcha, postal_code
from helpers.crud import RecordId
from helpers.db import DatabaseSession
from helpers.errors import AppError
from helpers.forms import payload_of, validated
from helpers.i18n import current_locale
from helpers.security import create_token
from helpers.settings import settings
from helpers.site import PageNotFound, inside, notice, paged, redirect, remember_language, render, sign_in, sign_out
from helpers.storage import storage
from helpers.text import display_name
from routes.site.base import CsrfToken, CurrentPage, PrivatePage, guard, refused_by_captcha
from schemas.common import BaseSchema, MobilePhone, Username
from schemas.user import AccountAddressRequest
from services.account import credit_transaction_service, user_balance_service
from services.auth import auth_service
from services.commerce import purchase_service, user_product_service
from services.country import country_service
from services.language import language_service
from services.subscription import subscription_service, user_entitlement_service
from services.user import user_address_service, user_service

PROFILE_FIELDS = ("first_name", "last_name", "nickname", "email", "username", "mobile_phone")

ADDRESS_FIELDS = ("line1", "street_number", "complement", "district", "city", "state", "postal_code", "country_code")

# Landing on one of these is landing where somebody just came from, so it is never where signing in puts them.
AUTH_PAGES = ("/account/login", "/account/signup", "/account/password-recovery")

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

    return {"values": values, "errors": errors, "avatar_url": avatar_of(page.user), "display_name": display_name(page.user), "phone_mask": country.phone_mask if country else None}


class SignUpRequest(BaseSchema):
    first_name: str = Field(min_length=2, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class ProfileRequest(BaseSchema):
    first_name: str | None = Field(None, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    nickname: str | None = Field(None, max_length=128)
    email: EmailStr | None = Field(None, max_length=255)
    username: Username = None
    mobile_phone: MobilePhone = None


class PasswordRequest(BaseSchema):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class RecoveryRequest(BaseSchema):
    login: str = Field(min_length=3, max_length=255)


class ResetRequest(BaseSchema):
    new_password: str = Field(min_length=8, max_length=128)


@router.get("/account/login")
async def login(page: CurrentPage):
    wanted = landing(page.request.query_params.get("next"))

    if page.user is not None:
        return redirect(page, wanted)

    return render(page, "account/login.html", {"challenge": captcha.issue(), "values": {}, "errors": {}, "next": wanted})


@router.post("/account/login")
async def sign_in_page(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, login: str = Form(""), password: str = Form(""), captcha_answer: str = Form(""), captcha_token: str = Form(""), next_path: str = Form("", alias="next")):
    guard(page, csrf_token)

    wanted = landing(next_path)

    def again(errors):
        return render(page, "account/login.html", {"challenge": captcha.issue(), "values": {"login": login}, "errors": errors, "next": wanted}, status_code=422)

    refused_here = await refused_by_captcha(page, captcha_answer, captcha_token)

    if refused_here:
        return again(refused_here)

    try:
        user = await auth_service.authenticate(db, page.brand.id, login, password)
    except AppError as refused:
        return again({"login": refused.message})

    answer = redirect(page, wanted, [notice("site.signed-in")])
    sign_in(answer, create_token(user.token, user.role, user.session_epoch))

    return answer


@router.post("/account/logout")
async def logout(page: CurrentPage, csrf_token: CsrfToken = None):
    guard(page, csrf_token)

    # Landing on the home signed out is the whole message, so there is no notice to read.
    answer = redirect(page, "/")
    sign_out(answer)

    return answer


@router.get("/account/signup")
async def signup(page: CurrentPage):
    wanted = landing(page.request.query_params.get("next"))

    if page.user is not None:
        return redirect(page, wanted)

    return render(page, "account/signup.html", {"challenge": captcha.issue(), "values": {}, "errors": {}, "next": wanted})


@router.post("/account/signup")
async def register(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, first_name: str = Form(""), last_name: str = Form(""), email: str = Form(""), password: str = Form(""), captcha_answer: str = Form(""), captcha_token: str = Form(""), next_path: str = Form("", alias="next")):
    guard(page, csrf_token)

    values = {"first_name": first_name, "last_name": last_name or None, "email": email, "password": password}
    payload, errors = validated(SignUpRequest, values)
    wanted = landing(next_path)

    def again(refused):
        return render(page, "account/signup.html", {"challenge": captcha.issue(), "values": values, "errors": refused, "next": wanted}, status_code=422)

    refused_here = (errors or {}) | await refused_by_captcha(page, captcha_answer, captcha_token)

    if refused_here:
        return again(refused_here)

    try:
        user = await auth_service.register(db, page.brand, payload.model_dump())
    except AppError as refused:
        return again({refused.field or "email": refused.message})

    answer = redirect(page, wanted, [notice("site.signed-up")])
    sign_in(answer, create_token(user.token, user.role, user.session_epoch))

    return answer


@router.get("/account/password-recovery")
async def password_recovery(page: CurrentPage):
    return render(page, "account/password-recovery.html", {"challenge": captcha.issue(), "values": {}, "errors": {}})


@router.post("/account/password-recovery")
async def start_recovery(page: CurrentPage, db: DatabaseSession, csrf_token: CsrfToken = None, login: str = Form(""), captcha_answer: str = Form(""), captcha_token: str = Form("")):
    guard(page, csrf_token)

    payload, errors = validated(RecoveryRequest, {"login": login})
    refused = (errors or {}) | await refused_by_captcha(page, captcha_answer, captcha_token)

    if refused:
        return render(page, "account/password-recovery.html", {"challenge": captcha.issue(), "values": {"login": login}, "errors": refused}, status_code=422)

    await auth_service.start_password_reset(db, page.brand, payload.login)

    # An unknown login answers exactly like a known one, so the page never says who has an account here.
    return redirect(page, "/account/password-recovery", [notice("site.recovery-sent")])


@router.get("/account/reset-password/{token}")
async def reset_password(page: CurrentPage, token: str):
    return render(page, "account/reset-password.html", {"token": token, "errors": {}})


@router.post("/account/reset-password/{token}")
async def confirm_reset(page: CurrentPage, db: DatabaseSession, token: str, csrf_token: CsrfToken = None, new_password: str = Form("")):
    guard(page, csrf_token)

    payload, errors = validated(ResetRequest, {"new_password": new_password})

    if payload is None:
        return render(page, "account/reset-password.html", {"token": token, "errors": errors}, status_code=422)

    try:
        await auth_service.confirm_password_reset(db, token, payload.new_password)
    except AppError as refused:
        return render(page, "account/reset-password.html", {"token": token, "errors": {"new_password": refused.message}}, status_code=422)

    return redirect(page, "/account/login", [notice("site.password-changed")])


@router.get("/account")
async def account(page: PrivatePage, db: DatabaseSession):
    """The hub of the account, which is a list of the places a person goes and never a menu that has to be opened."""
    rights = await user_entitlement_service.list_for_user(db, page.user.id)
    balances = await user_balance_service.list_for_user(db, page.user.id)

    return render(page, "account/index.html", {"avatar_url": avatar_of(page.user), "display_name": display_name(page.user), "entitlements": rights, "balances": balances})


@router.get("/account/profile")
async def edit_profile(page: PrivatePage, db: DatabaseSession):
    return render(page, "account/profile.html", await profile_context(db, page, {name: getattr(page.user, name) for name in PROFILE_FIELDS}, {}))


@router.post("/account/profile")
async def save_profile(page: PrivatePage, db: DatabaseSession, csrf_token: CsrfToken = None):
    guard(page, csrf_token)

    values = payload_of(await page.request.form(), PROFILE_FIELDS)
    payload, errors = validated(ProfileRequest, values)

    if payload is None:
        return render(page, "account/profile.html", await profile_context(db, page, values, errors), status_code=422)

    try:
        await user_service.update(db, page.user.id, payload.model_dump(exclude_unset=True))
    except AppError as refused:
        return render(page, "account/profile.html", await profile_context(db, page, values, {refused.field or "email": refused.message}), status_code=422)

    return redirect(page, "/account/profile", [notice("site.profile-saved")])


@router.post("/account/avatar")
async def save_avatar(page: PrivatePage, db: DatabaseSession, csrf_token: CsrfToken = None, file: UploadFile = File(...)):
    guard(page, csrf_token)

    try:
        await user_service.settle_avatar(db, page.user, file)
    except AppError as refused:
        return redirect(page, "/account", [notice(refused.code, "error")])

    return redirect(page, "/account", [notice("site.avatar-saved")])


@router.post("/account/avatar/remove")
async def remove_avatar(page: PrivatePage, db: DatabaseSession, csrf_token: CsrfToken = None):
    guard(page, csrf_token)
    await user_service.discard_avatar(db, page.user)

    return redirect(page, "/account", [notice("site.avatar-removed")])


@router.get("/account/password")
async def password(page: PrivatePage):
    return render(page, "account/password.html", {"errors": {}})


@router.post("/account/password")
async def change_password(page: PrivatePage, db: DatabaseSession, csrf_token: CsrfToken = None, current_password: str = Form(""), new_password: str = Form("")):
    guard(page, csrf_token)

    payload, errors = validated(PasswordRequest, {"current_password": current_password, "new_password": new_password})

    if payload is None:
        return render(page, "account/password.html", {"errors": errors}, status_code=422)

    try:
        await auth_service.change_password(db, page.user, payload.current_password, payload.new_password)
    except AppError as refused:
        return render(page, "account/password.html", {"errors": {"current_password": refused.message}}, status_code=422)

    # Every other session ended, and this one is handed the token that replaces the one it arrived with.
    answer = redirect(page, "/account", [notice("site.password-changed")])
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

    return redirect(page, "/account/address", [notice("site.address-saved")])


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


@router.get("/account/language")
async def language(page: PrivatePage):
    return render(page, "account/language.html")


@router.post("/account/language")
async def save_language(page: PrivatePage, db: DatabaseSession, csrf_token: CsrfToken = None, language: str = Form("")):
    """The account keeps the choice, and the cookie keeps it too so the browser reads the same thing before the session is resolved."""
    guard(page, csrf_token)

    if language not in settings.languages:
        raise PageNotFound()

    chosen = await language_service.find_by_code(db, language)
    await user_service.update(db, page.user.id, {"language_id": chosen.id if chosen else None})

    # From the moment the choice is made this request speaks the new language, or the notice would arrive in the old one.
    current_locale.set(language)

    answer = redirect(page, "/account/language", [notice("site.language-saved")])
    remember_language(answer, language, page.consent)

    return answer


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

    answer = redirect(page, "/", [notice("site.account-erased")])
    sign_out(answer)

    return answer
