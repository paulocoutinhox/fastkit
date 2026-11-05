from uuid import uuid4

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from enums.log_category import LogCategory
from enums.log_level import LogLevel
from enums.upload_purpose import UploadPurpose
from enums.user import PANEL_ROLES
from enums.user_gender import UserGender
from enums.user_status import UserStatus
from helpers.conflict_error import ConflictError
from helpers.dates import now
from helpers.db import commit, refusing
from helpers.scope import belongs_to_tenant
from helpers.security import hash_password
from helpers.settings import settings
from helpers.storage import storage
from helpers.text import display_name, only_digits
from helpers.validation_error import ValidationError
from models.app_event import AppEvent
from models.credit_transaction import CreditTransaction
from models.email_login_challenge import EmailLoginChallenge
from models.login_ticket import LoginTicket
from models.purchase import Purchase
from models.social_identity import SocialIdentity
from models.social_login_attempt import SocialLoginAttempt
from models.subscription import Subscription
from models.user import User
from models.user_address import UserAddress
from models.user_balance import UserBalance
from models.user_group import UserGroup
from models.user_group_member import UserGroupMember
from models.user_product import UserProduct
from services.crud_service import CrudService
from services.dependent import Dependent
from services.incoming_file import IncomingFile
from services.language_service import language_service
from services.system_log_service import system_log_service
from services.upload import owner_of
from services.upload_service import upload_service

USER_DEPENDENTS = (Dependent(UserAddress, "user_id"), Dependent(UserProduct, "user_id"), Dependent(Purchase, "user_id"), Dependent(CreditTransaction, "user_id"), Dependent(UserBalance, "user_id"), Dependent(AppEvent, "user_id"), Dependent(UserGroupMember, "user_id"))


IDENTITY_FIELDS = ("username", "email", "document", "mobile_phone")

# What a brand writes about an account, which stays in that brand whatever happens to the account.
BRAND_WRITTEN = (Purchase, Subscription, UserProduct, CreditTransaction, UserBalance)


LOGIN_UNIQUE_FIELDS = (("username", "error.username-already-used"), ("email", "error.email-already-used"), ("document", "error.document-already-used"), ("mobile_phone", "error.mobile-phone-already-used"))


class UserService(CrudService):
    model = User
    search_fields = ("username", "email", "document", "mobile_phone")
    text_search_fields = ("first_name", "last_name", "nickname")
    filter_fields = ("tenant_id", "role", "status", "language_id")
    ordering_fields = ("id", "username", "email", "first_name", "last_name", "role", "status", "created_at")
    default_ordering = "-id"
    relations = ("tenant", "language")
    label_fields = ("username",)
    file_fields = {"avatar": UploadPurpose.AVATAR}
    markup_fields = ("notes",)
    dependents = USER_DEPENDENTS

    def stamped(self, data: dict, operator) -> dict:
        """Reaching the shared rows is granted by an operator of no brand, so one of a brand never grants it, not even to itself."""
        stamped = super().stamped(data, operator)

        if operator is None or operator.tenant_id is None:
            return stamped

        return {name: value for name, value in stamped.items() if name != "reaches_shared"}

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

        # An address an operator writes is the address, so one the account was still waiting on is forgotten, and a form sending the current one back writes nothing.
        if instance is not None and "email" in prepared and prepared["email"] != instance.email:
            prepared |= {"pending_email": None, "confirmation_token": None, "confirmation_sent_at": None, "recovery_token": None, "recovery_token_created_at": None}

        # A password written from the panel ends the sessions the old one opened, like any other change of password.
        if password:
            prepared["password_hash"] = await hash_password(password)

            if instance is not None:
                prepared |= {"session_epoch": User.session_epoch + 1, "recovery_token": None, "recovery_token_created_at": None}

        return prepared

    async def hold(self, db: AsyncSession, user_id: int) -> None:
        """A write about an account holds its row first, so an erasure and that write never interleave and nothing personal lands on a row that was just forgotten."""
        held = update(User).where(User.id == user_id, User.status != UserStatus.ERASED).values(status=User.status)

        if (await db.execute(held)).rowcount != 1:
            raise ConflictError("error.account-erased")

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        if instance is not None:
            await self.hold(db, instance.id)
            await db.refresh(instance)

        # Hashing is left to `prepare`, because argon2 costs what it is meant to cost and one write must not pay it twice.
        normalized = self.normalize(data)
        tenant_id = self.declared(normalized, instance, "tenant_id")

        for name in IDENTITY_FIELDS:
            if normalized.get(name):
                await self.ensure_free(db, name, normalized[name], tenant_id, instance)

        self.ensure_identity(normalized, instance)

        if instance is not None and not instance.has_password and not normalized.get("password") and not self.declared(normalized, instance, "email"):
            enabled = {provider for provider, configuration in settings.authentication.social.items() if configuration.enabled and (configuration.site or configuration.admin and instance.role in PANEL_ROLES)}
            connected = await db.scalar(select(SocialIdentity.id).where(SocialIdentity.user_id == instance.id, SocialIdentity.provider.in_(enabled)).limit(1))

            if connected is None:
                raise ValidationError("error.last-sign-in-method", "email")

        if normalized.get("language_id") is not None and normalized["language_id"] not in {language.id for language in await language_service.offered(db)}:
            raise ValidationError("error.language-not-offered", "language_id")

        if instance is not None and tenant_id != instance.tenant_id:
            await self.ensure_nothing_stays_behind(db, instance)

            async with refusing(db, "error.social-identity-in-use"):
                await db.execute(update(SocialIdentity).where(SocialIdentity.user_id == instance.id).values(tenant_id=tenant_id))

    async def ensure_nothing_stays_behind(self, db: AsyncSession, instance: User) -> None:
        """An account leaves its brand only while that brand wrote nothing about it, because a purchase, a subscription, a balance or a membership stays in the brand it was made in and would point across brands, and a purchase keeps that brand from ever being deleted."""
        if instance.tenant_id is None:
            return

        written = [select(model.id).where(model.user_id == instance.id) for model in BRAND_WRITTEN]
        written.append(select(UserGroupMember.id).join(UserGroup, UserGroup.id == UserGroupMember.group_id).where(UserGroupMember.user_id == instance.id, UserGroup.tenant_id == instance.tenant_id))

        for statement in written:
            if await db.scalar(statement.limit(1)) is not None:
                raise ValidationError("error.record-still-referenced", "tenant_id")

    async def ensure_free(self, db: AsyncSession, name: str, value: str, tenant_id: int | None, instance) -> None:
        """A sign in matches the four columns at once, so an identity is taken when, typed as a login, it would answer for another account of the scope."""
        taken = select(User.id).where(self.identified_by(value), belongs_to_tenant(User.tenant_id, tenant_id))

        if await db.scalar(taken if instance is None else taken.where(User.id != instance.id)) is not None:
            raise ConflictError(dict(LOGIN_UNIQUE_FIELDS)[name], name)

    def identity_of(self, user: User) -> str:
        """The one an account is asked to type back, in the order a person recognises rather than the order they are validated in."""
        return next(value for name in ("email", "username", "document", "mobile_phone") if (value := getattr(user, name)))

    def ensure_identity(self, data: dict, instance) -> None:
        """An account is signed in by one of the four, and losing all of them would leave nobody able to reach it."""
        values = [self.declared(data, instance, name) for name in IDENTITY_FIELDS]

        if not any(values):
            raise ValidationError("error.at-least-one-identity", "email")

    async def settle_avatar(self, db: AsyncSession, user: User, picture: IncomingFile) -> User:
        """The account sends the image and never a storage key, so the only file it can replace is the one it already has."""
        stored = await upload_service.store(db, UploadPurpose.AVATAR, picture)

        try:
            await self.hold(db, user.id)
        except ConflictError:
            await storage.delete(stored["key"])

            raise

        await db.refresh(user)
        previous = self.mentioned(user)

        user.avatar = stored["key"]
        dropped = await upload_service.mention(db, owner_of(user), self.mentioned(user), self.keys_of(user))

        # The row that would have claimed it never landed, so the file goes now and the sweep would have taken it either way.
        try:
            await commit(db)
        except Exception:
            await storage.delete(stored["key"])

            raise

        # The file goes after the row points elsewhere, or a failed write would leave the account naming what is gone.
        # Two pictures sent at once each name the one before them, and only what was written down knows the one in between.
        await upload_service.release(db, (previous - self.mentioned(user)) | dropped)

        return user

    async def discard_avatar(self, db: AsyncSession, user: User) -> User:
        await self.hold(db, user.id)
        await db.refresh(user)

        if user.avatar is None:
            return user

        previous = self.mentioned(user)

        user.avatar = None
        dropped = await upload_service.mention(db, owner_of(user), self.mentioned(user))
        await commit(db)

        await upload_service.release(db, (previous - self.mentioned(user)) | dropped)

        return user

    async def present(self, user: User) -> dict:
        """The account reads an address for its picture and its own token, never a storage key and never the id."""
        return {
            "token": user.token,
            "language_id": user.language_id,
            "language": user.language,
            "username": user.username,
            "email": user.email,
            "pending_email": user.pending_email,
            "document": user.document,
            "mobile_phone": user.mobile_phone,
            "status": user.status,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "nickname": user.nickname,
            "gender": user.gender,
            "avatar_url": storage.url(user.avatar) if user.avatar else None,
            "timezone": user.timezone,
            "last_login_at": user.last_login_at,
            "has_password": user.has_password,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    def build_label(self, instance) -> str:
        return display_name(instance)

    def label_ordering(self):
        """A lookup names an account by what it is called, so it is ordered by the same cascade, and one with no username, which is most of those the site signs up, is never pushed past the page."""
        called = func.coalesce(User.nickname, User.first_name, User.username, User.email)

        return [called.is_(None), called.asc(), User.id.asc()]

    def identified_by(self, login: str):
        """Any of the four identities, typed in the one field a sign in has: what carries a letter is a username or an address, and what does not is a number."""
        # A username always carries a letter, so the two families never answer for the same login and one account can never sign in as another.
        if any(character.isalpha() for character in login):
            return or_(User.username == login, User.email == login.lower())

        return or_(User.document == only_digits(login), User.mobile_phone == only_digits(login))

    async def find_by_login(self, db: AsyncSession, login: str, tenant_id: int | None) -> User | None:
        """An identity only means something inside a scope now, so the caller says which one it is asking about."""
        return await db.scalar(select(User).where(self.identified_by(login), belongs_to_tenant(User.tenant_id, tenant_id)))

    async def find_operator(self, db: AsyncSession, login: str, tenant_id: int | None) -> User | None:
        """An operator of a brand signs in on that brand and one of no brand signs in on every one, and the brand's own is found first when both share a login."""
        return await db.scalar(select(User).where(self.identified_by(login), or_(belongs_to_tenant(User.tenant_id, tenant_id), User.tenant_id.is_(None))).order_by(User.role.not_in(PANEL_ROLES), User.tenant_id.is_(None)).limit(1))

    async def erase(self, db: AsyncSession, user: User) -> User:
        """What the law calls the right to be forgotten, done by replacing the person instead of dropping the row."""
        await self.hold(db, user.id)
        await db.refresh(user)

        orphaned = self.mentioned(user)
        drawn = uuid4().hex
        email = user.email

        user.username = f"erased-{drawn}"
        # The reserved tld never reaches a mailbox, not even by accident.
        user.email = f"{drawn}@erased.invalid"
        user.document = drawn[:11]
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
        user.pending_email = None
        user.confirmation_token = None
        user.confirmation_sent_at = None
        user.status = UserStatus.ERASED
        user.erased_at = now()

        orphaned |= await upload_service.forget(db, [owner_of(user)])

        await self.forget_behaviour(db, user.id, user.tenant_id, email)

        # Drawn values collide only by accident, and an accident is a conflict and never a five hundred.
        await commit(db)

        # The file goes once the row no longer names it, which is the rule wherever one is discarded here.
        await upload_service.release(db, orphaned)

        await system_log_service.record(db, user.tenant_id, user.id, LogLevel.INFO, LogCategory.ACCOUNT, "account erased on request", {"user_id": user.id})

        return user

    async def forget_behaviour(self, db: AsyncSession, user_id: int, tenant_id: int | None, email: str | None) -> None:
        """What the person did is theirs and goes, what they paid is the record of a transaction and stays."""
        for model in (UserAddress, AppEvent, SocialIdentity, SocialLoginAttempt, LoginTicket, UserGroupMember):
            await db.execute(delete(model).where(model.user_id == user_id))

        await db.execute(delete(EmailLoginChallenge).where(belongs_to_tenant(EmailLoginChallenge.tenant_id, tenant_id), EmailLoginChallenge.email == email))

    async def find_by_recovery_token(self, db: AsyncSession, token: str, tenant_id: int | None) -> User | None:
        """A link opens an account of the brand it was followed on, because it signs in or sets a password there and an account is an account of one brand."""
        return await db.scalar(select(User).where(User.recovery_token == token, belongs_to_tenant(User.tenant_id, tenant_id)))

    async def find_by_confirmation_token(self, db: AsyncSession, token: str, tenant_id: int | None) -> User | None:
        return await db.scalar(select(User).where(User.confirmation_token == token, belongs_to_tenant(User.tenant_id, tenant_id)))


user_service = UserService()
