from fastapi import APIRouter, Request, status

from helpers import captcha
from helpers.auth import CurrentBrand
from helpers.db import DatabaseSession
from helpers.errors import ValidationError
from helpers.security import create_token
from schemas.auth import AdminSignInRequest, SignInRequest, SignUpRequest, TokenResponse
from schemas.user import AccountSchema
from services.auth import auth_service
from services.user import user_service

router = APIRouter(tags=["auth"])


@router.post("/signin", response_model=TokenResponse, summary="Sign in")
async def sign_in(db: DatabaseSession, brand: CurrentBrand, payload: SignInRequest):
    """An identity is unique inside a tenant, so the caller states which one it is signing in to."""
    user = await auth_service.authenticate(db, brand.id, payload.login, payload.password)

    return TokenResponse(token=create_token(user.token, user.role, user.session_epoch), user=AccountSchema.model_validate(await user_service.present(user)))


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, summary="Sign up")
async def sign_up(db: DatabaseSession, brand: CurrentBrand, payload: SignUpRequest):
    user = await auth_service.register(db, brand, payload.model_dump())

    return TokenResponse(token=create_token(user.token, user.role, user.session_epoch), user=AccountSchema.model_validate(await user_service.present(user)))


@router.post("/admin/signin", response_model=TokenResponse, summary="Sign in to the admin")
async def admin_sign_in(request: Request, db: DatabaseSession, payload: AdminSignInRequest):
    """The panel accepts the roles that work in it, so an account of a reader is refused here even with the right password."""
    if not await captcha.verify(payload.captcha_answer, payload.captcha_token, request.client.host if request.client else None):
        raise ValidationError("error.captcha-invalid", "captcha_answer")

    user = await auth_service.authenticate_for_panel(db, payload.login, payload.password)

    return TokenResponse(token=create_token(user.token, user.role, user.session_epoch), user=AccountSchema.model_validate(await user_service.present(user)))
