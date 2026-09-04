from uuid import uuid4

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.system_log import LogCategory, LogLevel
from enums.upload import UploadPurpose
from enums.user import UserAddressType, UserGender, UserStatus
from helpers.dates import now
from helpers.db import commit
from helpers.errors import ValidationError
from helpers.scope import belongs_to_tenant
from helpers.security import hash_password
from helpers.storage import storage
from helpers.text import display_name, only_digits
from models.account import CreditTransaction, UserBalance
from models.commerce import Purchase, UserProduct
from models.event import AppEvent
from models.user import User, UserAddress
from services.country import country_service
from services.crud import CrudService, Dependent, Reach
from services.system_log import system_log_service
from services.upload import IncomingFile, upload_service

USER_DEPENDENTS = (Dependent(UserAddress, "user_id"), Dependent(UserProduct, "user_id"), Dependent(Purchase, "user_id"), Dependent(CreditTransaction, "user_id"), Dependent(UserBalance, "user_id"), Dependent(AppEvent, "user_id"))

IDENTITY_FIELDS = ("username", "email", "cpf", "mobile_phone")

LOGIN_UNIQUE_FIELDS = (("username", User.username, "error.username-already-used"), ("email", User.email, "error.email-already-used"), ("cpf", User.cpf, "error.cpf-already-used"), ("mobile_phone", User.mobile_phone, "error.mobile-phone-already-used"))


class UserService(CrudService):
    model = User
    search_fields = ("username", "email", "cpf", "mobile_phone")
    text_search_fields = ("first_name", "last_name", "nickname")
    filter_fields = ("tenant_id", "role", "status", "language_id")
    ordering_fields = ("id", "username", "email", "first_name", "last_name", "role", "status", "created_at")
    default_ordering = "-id"
    relations = ("tenant", "language")
    label_fields = ("username",)
    file_fields = {"avatar": UploadPurpose.AVATAR}
    markup_fields = ("notes",)
    dependents = USER_DEPENDENTS

    def normalize(self, data: dict) -> dict:
        """An identity is checked the way it is stored, or an address differing only in case reaches the index as a plain conflict."""
        normalized = dict(data)

        if normalized.get("email"):
            normalized["email"] = normalized["email"].lower()

        for name in IDENTITY_FIELDS:
            if name in normalized and not normalized[name]:
                normalized[name] = None

        return normalized

    async def prepare(self, data: dict, instance) -> dict:
        prepared = self.normalize(data)
        password = prepared.pop("password", None)

        if password:
            prepared["password_hash"] = await hash_password(password)

        return prepared

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        # Hashing is left to `prepare`, because argon2 costs what it is meant to cost and one write must not pay it twice.
        normalized = self.normalize(data)
        scope = belongs_to_tenant(User.tenant_id, self.declared(normalized, instance, "tenant_id"))

        for name, column, code in LOGIN_UNIQUE_FIELDS:
            if name in normalized:
                await self.ensure_unique(db, column, normalized[name], code, name, instance, scope)

        self.ensure_identity(normalized, instance)

    def identity_of(self, user: User) -> str:
        """The one an account is asked to type back, in the order a person recognises rather than the order they are validated in."""
        return next(value for name in ("email", "username", "cpf", "mobile_phone") if (value := getattr(user, name)))

    def ensure_identity(self, data: dict, instance) -> None:
        """An account is signed in by one of the four, and losing all of them would leave nobody able to reach it."""
        values = [self.declared(data, instance, name) for name in IDENTITY_FIELDS]

        if not any(values):
            raise ValidationError("error.at-least-one-identity", "email")

    async def settle_avatar(self, db: AsyncSession, user: User, picture: IncomingFile) -> User:
        """The account sends the image and never a storage key, so the only file it can replace is the one it already has."""
        stored = await upload_service.store(db, UploadPurpose.AVATAR, picture)
        previous = self.mentioned(user)

        user.avatar = stored["key"]
        await upload_service.claim(db, self.mentioned(user))

        # The row that would have claimed it never landed, so the file goes now and the sweep would have taken it either way.
        try:
            await commit(db)
        except Exception:
            await storage.delete(stored["key"])

            raise

        # The file goes after the row points elsewhere, or a failed write would leave the account naming what is gone.
        await upload_service.release(db, previous - self.mentioned(user))

        return user

    async def discard_avatar(self, db: AsyncSession, user: User) -> User:
        previous = self.mentioned(user)

        if user.avatar is None:
            return user

        user.avatar = None
        await commit(db)

        await upload_service.release(db, previous)

        return user

    async def present(self, user: User) -> dict:
        """The account reads an address for its picture and its own token, never a storage key and never the id."""
        return {
            "token": user.token,
            "language_id": user.language_id,
            "language": user.language,
            "username": user.username,
            "email": user.email,
            "cpf": user.cpf,
            "mobile_phone": user.mobile_phone,
            "status": user.status,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "nickname": user.nickname,
            "gender": user.gender,
            "avatar_url": storage.url(user.avatar) if user.avatar else None,
            "timezone": user.timezone,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    def build_label(self, instance) -> str:
        return display_name(instance)

    async def find_by_login(self, db: AsyncSession, login: str, tenant_id: int | None) -> User | None:
        """An identity only means something inside a scope now, so the caller says which one it is asking about."""
        digits = only_digits(login)
        conditions = [User.username == login, User.email == login.lower()]

        if digits:
            conditions.extend([User.cpf == digits, User.mobile_phone == digits])

        return await db.scalar(select(User).where(or_(*conditions), belongs_to_tenant(User.tenant_id, tenant_id)))

    async def erase(self, db: AsyncSession, user: User) -> User:
        """What the law calls the right to be forgotten, done by replacing the person instead of dropping the row."""
        orphaned = self.mentioned(user)
        drawn = uuid4().hex

        user.username = f"erased-{drawn}"
        # The reserved tld never reaches a mailbox, not even by accident.
        user.email = f"{drawn}@erased.invalid"
        user.cpf = drawn[:11]
        user.mobile_phone = drawn[:16]
        user.password_hash = await hash_password(uuid4().hex)

        # The `sub` of a JWT is this, so drawing it again is what signs the account out of every device.
        user.token = str(uuid4())

        user.first_name = None
        user.last_name = None
        user.nickname = None
        user.gender = UserGender.NONE
        user.avatar = None
        user.notes = None
        user.meta = {}
        user.recovery_token = None
        user.recovery_token_created_at = None
        user.status = UserStatus.ERASED
        user.erased_at = now()

        await self.forget_behaviour(db, user.id)

        # Drawn values collide only by accident, and an accident is a conflict and never a five hundred.
        await commit(db)

        # The file goes once the row no longer names it, which is the rule wherever one is discarded here.
        await upload_service.release(db, orphaned)

        await system_log_service.record(db, user.tenant_id, user.id, LogLevel.INFO, LogCategory.ACCOUNT, "account erased on request", {"user_id": user.id})

        return user

    async def forget_behaviour(self, db: AsyncSession, user_id: int) -> None:
        """What the person did is theirs and goes, what they paid is the record of a transaction and stays."""
        for model in (UserAddress, AppEvent):
            await db.execute(delete(model).where(model.user_id == user_id))

    async def find_by_recovery_token(self, db: AsyncSession, token: str) -> User | None:
        return await db.scalar(select(User).where(User.recovery_token == token))


class UserAddressService(CrudService):
    model = UserAddress
    reaches_through = Reach(UserAddress.user_id, User)
    search_fields = ("postal_code", "city")
    filter_fields = ("user_id", "type", "country_code")
    ordering_fields = ("id", "type", "city", "created_at")
    default_ordering = "-id"
    relations = ("user",)
    label_fields = ("line1",)

    async def prepare(self, data: dict, instance) -> dict:
        prepared = dict(data)

        if prepared.get("country_code"):
            prepared["country_code"] = prepared["country_code"].upper()

        return prepared

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        prepared = await self.prepare(data, instance)
        user_id = self.declared(prepared, instance, "user_id")
        address_type = self.declared(prepared, instance, "type")
        country_code = self.declared(prepared, instance, "country_code")

        await self.ensure_unique(db, UserAddress.type, address_type, "error.address-type-already-used", "type", instance, UserAddress.user_id == user_id)

        # The code is a natural key of the registry, so an address is only ever written in a country this instance offers.
        if country_code and await country_service.find_by_code(db, country_code) is None:
            raise ValidationError("error.country-not-offered", "country_code")

    async def find_for_user(self, db: AsyncSession, user_id: int, address_type: UserAddressType) -> UserAddress | None:
        return await db.scalar(select(UserAddress).where(UserAddress.user_id == user_id, UserAddress.type == address_type))

    async def save_for_user(self, db: AsyncSession, user_id: int, address_type: UserAddressType, data: dict) -> UserAddress:
        """One address per purpose, so the account writes the same row again instead of collecting a second one."""
        existing = await self.find_for_user(db, user_id, address_type)

        if existing is not None:
            return await self.update(db, existing.id, data)

        return await self.create(db, {**data, "user_id": user_id, "type": address_type})

    async def list_for_user(self, db: AsyncSession, user_id: int) -> list[UserAddress]:
        result = await db.execute(self.base_statement().where(UserAddress.user_id == user_id).order_by(UserAddress.type.asc()))

        return list(result.scalars().unique())


user_service = UserService()
user_address_service = UserAddressService()
