from fastapi import APIRouter, Request, status

from enums.user_status import UserStatus
from helpers import captcha
from helpers.auth import CurrentBrand
from helpers.db import DatabaseSession
from helpers.security import create_token
from helpers.site import brand_of
from helpers.validation_error import ValidationError
from schemas.account_schema import AccountSchema
from schemas.admin_sign_in_request import AdminSignInRequest
from schemas.session_response import SessionResponse
from schemas.sign_in_request import SignInRequest
from schemas.sign_up_request import SignUpRequest
from schemas.token_response import TokenResponse
from services.auth_service import auth_service
from services.user_service import user_service

router = APIRouter(tags=["auth"])


@router.post("/signin", response_model=TokenResponse, summary="Sign in")
async def sign_in(db: DatabaseSession, brand: CurrentBrand, payload: SignInRequest):
    """An identity is unique inside a tenant, so the caller states which one it is signing in to."""
    user = await auth_service.authenticate(db, brand.id, payload.login, payload.password)

    return TokenResponse(token=create_token(user.token, user.role, user.session_epoch), user=AccountSchema.model_validate(await user_service.present(user)))


@router.post("/signup", response_model=SessionResponse, status_code=status.HTTP_201_CREATED, summary="Sign up")
async def sign_up(db: DatabaseSession, brand: CurrentBrand, payload: SignUpRequest):
    """An account whose address still has to answer is created without a session, and the token of nothing is what says so."""
    user = await auth_service.register(db, brand, payload.model_dump())
    minted = create_token(user.token, user.role, user.session_epoch) if user.status == UserStatus.ACTIVE else None

    return SessionResponse(token=minted, user=AccountSchema.model_validate(await user_service.present(user)))


@router.post("/admin/signin", response_model=TokenResponse, summary="Sign in to the admin")
async def admin_sign_in(request: Request, db: DatabaseSession, payload: AdminSignInRequest):
    """The panel accepts the roles that work in it, so an account of a reader is refused here even with the right password."""
    if not await captcha.verify(payload.captcha_answer, payload.captcha_token, request.client.host if request.client else None):
        raise ValidationError("error.captcha-invalid", "captcha_answer")

    # The panel resolves its brand the way the site does, by the host it was opened on.
    opened_on = await brand_of(db, request)
    user = await auth_service.authenticate_for_panel(db, opened_on.id if opened_on else None, payload.login, payload.password)

    return TokenResponse(token=create_token(user.token, user.role, user.session_epoch), user=AccountSchema.model_validate(await user_service.present(user)))
