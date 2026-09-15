"""Who is calling and whether they may, which is the only place a role decides anything."""

from typing import Annotated

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from enums.user import UserRole, UserStatus
from helpers import brand
from helpers.brand import Brand
from helpers.db import DatabaseSession
from helpers.errors import AppError, AuthenticationError, PermissionError, ValidationError
from helpers.security import decode_token
from helpers.settings import settings
from models.tenant import Tenant
from models.user import User

TENANT_HEADER = "X-Tenant-Code"

bearer = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


async def load_user(db, token: str) -> User:
    try:
        claims = decode_token(token)
    except jwt.PyJWTError as error:
        raise AuthenticationError("error.invalid-token") from error

    statement = select(User).options(selectinload(User.tenant), selectinload(User.language)).where(User.token == claims["sub"])
    user = await db.scalar(statement)

    if user is None:
        raise AuthenticationError("error.invalid-token")

    # An erased account keeps its row and a drawn token, and answering to it would hand back what was erased.
    if user.status == UserStatus.ERASED:
        raise AuthenticationError("error.invalid-token")

    # A password that changed moved the account forward, and a token minted before it belongs to a session that ended.
    if claims.get("epoch") != user.session_epoch:
        raise AuthenticationError("error.invalid-token")

    if user.status == UserStatus.BLOCKED:
        raise AuthenticationError("error.account-blocked")

    if user.status == UserStatus.PENDING:
        raise AuthenticationError("error.account-pending")

    return user


async def get_current_user(db: DatabaseSession, credentials: BearerCredentials) -> User:
    if credentials is None:
        raise AuthenticationError()

    return await load_user(db, credentials.credentials)


async def get_optional_user(db: DatabaseSession, credentials: BearerCredentials) -> User | None:
    """Resolves the caller when a usable token is present, without ever rejecting the request."""
    if credentials is None:
        return None

    try:
        return await load_user(db, credentials.credentials)
    except AppError:
        return None


def requires(*roles: UserRole):
    """The roles a route answers to, which is the one line anywhere in the API that says who may call it."""

    async def guard(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise PermissionError("error.role-not-allowed")

        return user

    return guard


get_administrator = requires(UserRole.ADMINISTRATOR)


async def get_current_brand(db: DatabaseSession, tenant_code: Annotated[str | None, Header(alias=TENANT_HEADER)] = None) -> Brand:
    """Answers the brand the call names, which every anonymous call states where this instance serves many and none of them states where it serves one."""
    if not settings.multi_tenant:
        # Naming a tenant to an instance that has none would be a second way of saying which site this is.
        if tenant_code is not None:
            raise AppError("error.unknown-tenant")

        return brand.of(None)

    if tenant_code is None:
        raise ValidationError("validation.required", TENANT_HEADER)

    found = await db.scalar(select(Tenant).where(Tenant.code == tenant_code, Tenant.active.is_(True)))

    if found is None:
        raise AppError("error.unknown-tenant")

    return brand.of(found)


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdministratorUser = Annotated[User, Depends(get_administrator)]
CurrentBrand = Annotated[Brand, Depends(get_current_brand)]
