"""HTTP account scope and response construction for optional authentication."""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from enums.authentication_surface import AuthenticationSurface
from helpers.auth import TENANT_HEADER, get_current_brand
from helpers.authentication_helper import AuthenticationHelper
from helpers.brand import Brand
from helpers.not_found_error import NotFoundError
from helpers.page_not_found import PageNotFound
from helpers.security import create_token
from helpers.settings import settings
from helpers.site import brand_of
from models.user import User
from schemas.account_schema import AccountSchema
from schemas.token_response import TokenResponse
from services.user_service import user_service


class AuthenticationRouteHelper:
    @staticmethod
    def require_site_email() -> None:
        if not AuthenticationHelper.available(settings.authentication.email, AuthenticationSurface.SITE):
            raise PageNotFound()

    @staticmethod
    async def brand(db: AsyncSession, request: Request, surface: AuthenticationSurface) -> Brand:
        if surface == AuthenticationSurface.SITE:
            return await get_current_brand(db, request.headers.get(TENANT_HEADER))

        found = await brand_of(db, request)

        if found is None:
            raise NotFoundError()

        return found

    @staticmethod
    async def session(user: User) -> TokenResponse:
        return TokenResponse(token=create_token(user.token, user.role, user.session_epoch), user=AccountSchema.model_validate(await user_service.present(user)))
