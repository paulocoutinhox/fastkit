from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from fastkit_core.errors.codes import CONFLICT_UNIQUE, RESOURCE_NOT_FOUND
from fastkit_core.errors.exceptions import ConflictError, NotFoundError
from fastkit_accounts.models import LoginIdentifier, User, UserProfile
from fastkit_accounts.normalizers import NormalizerRegistry, default_registry
from fastkit_tenancy.constants import to_persisted


DEFAULT_MIRROR_FIELDS = {"email": "email", "username": "username", "phone": "phone"}


class AccountService:
    """Creates users with normalized login identifiers and resolves login candidates."""

    def __init__(
        self,
        database,
        normalizers: NormalizerRegistry | None = None,
        mirror_fields: dict[str, str] | None = None,
    ):
        self._database = database
        self._normalizers = normalizers or default_registry()
        self._mirror_fields = (
            DEFAULT_MIRROR_FIELDS if mirror_fields is None else mirror_fields
        )

    def identifier_types(self) -> list[str]:
        return self._normalizers.types()

    def normalize_identifier(self, identifier_type: str, raw_value: str) -> str:
        return self._normalizers.normalize(identifier_type, raw_value)

    async def create_user(
        self,
        tenant_id: int | None,
        identifiers: list[tuple[str, str]],
        display_name: str | None = None,
        is_staff: bool = False,
        is_root: bool = False,
        password_hash: str | None = None,
    ) -> User:
        if is_root and to_persisted(tenant_id) is not None:
            raise ConflictError(
                CONFLICT_UNIQUE, message="root users must belong to the global tenant"
            )

        persisted_tenant = to_persisted(tenant_id)

        async with self._database.session_factory() as session:
            for identifier_type, raw_value in identifiers:
                await self._ensure_unique(
                    session, persisted_tenant, identifier_type, raw_value
                )

            user = User(
                tenant_id=persisted_tenant,
                display_name=display_name,
                is_staff=is_staff,
                is_root=is_root,
                password_hash=password_hash,
            )
            user.profile = UserProfile()

            for index, (identifier_type, raw_value) in enumerate(identifiers):
                normalizer = self._normalizers.get(identifier_type)
                normalizer.validate(raw_value)

                user.identifiers.append(
                    LoginIdentifier(
                        tenant_id=persisted_tenant,
                        type=identifier_type,
                        value=raw_value,
                        normalized_value=normalizer.normalize(raw_value),
                        is_primary=index == 0,
                    )
                )

            self._mirror_primary_fields(user, identifiers)

            session.add(user)
            await self._commit_unique(session)
            await session.refresh(user)

            return user

    async def find_candidates(
        self, requested_tenant_id: int | None, identifier_type: str, raw_value: str
    ) -> list[User]:
        normalized = self._normalizers.get(identifier_type).normalize(raw_value)
        persisted_tenant = to_persisted(requested_tenant_id)

        async with self._database.session_factory() as session:
            query = (
                select(User)
                .join(LoginIdentifier, LoginIdentifier.user_id == User.id)
                .where(
                    LoginIdentifier.type == identifier_type,
                    LoginIdentifier.normalized_value == normalized,
                )
                .where(
                    or_(
                        LoginIdentifier.tenant_id == persisted_tenant,
                        LoginIdentifier.tenant_id.is_(None),
                    )
                )
            )
            result = await session.execute(query)

            return list(result.unique().scalars().all())

    async def get_user(self, user_id) -> User | None:
        async with self._database.session_factory() as session:
            return await session.get(User, user_id)

    async def list_identifiers(self, user_id) -> list[LoginIdentifier]:
        async with self._database.session_factory() as session:
            result = await session.execute(
                select(LoginIdentifier)
                .where(LoginIdentifier.user_id == user_id)
                .order_by(LoginIdentifier.type)
            )

            return list(result.scalars().all())

    async def add_identifier(
        self, user_id, tenant_id: int | None, identifier_type: str, raw_value: str
    ) -> LoginIdentifier:
        persisted_tenant = to_persisted(tenant_id)
        normalizer = self._normalizers.get(identifier_type)
        normalizer.validate(raw_value)

        async with self._database.session_factory() as session:
            await self._ensure_unique(
                session, persisted_tenant, identifier_type, raw_value
            )

            identifier = LoginIdentifier(
                user_id=user_id,
                tenant_id=persisted_tenant,
                type=identifier_type,
                value=raw_value,
                normalized_value=normalizer.normalize(raw_value),
            )
            session.add(identifier)
            await self._commit_unique(session)
            await session.refresh(identifier)

            return identifier

    async def remove_identifier(self, user_id, identifier_id) -> bool:
        identifier_pk = _as_int(identifier_id)

        if identifier_pk is None:
            return False

        async with self._database.session_factory() as session:
            identifier = await session.get(LoginIdentifier, identifier_pk)

            if identifier is None or identifier.user_id != user_id:
                return False

            await session.delete(identifier)
            await session.commit()

            return True

    async def update_profile(
        self,
        user_id,
        display_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        preferred_locale: str | None = None,
        timezone: str | None = None,
        avatar_file_id=None,
    ) -> User:
        async with self._database.session_factory() as session:
            user = await self._require_user(session, user_id)

            for attribute, value in (
                ("display_name", display_name),
                ("first_name", first_name),
                ("last_name", last_name),
                ("preferred_locale", preferred_locale),
                ("timezone", timezone),
            ):
                if value is not None:
                    setattr(user, attribute, value)

            if avatar_file_id is not None:
                if user.profile is None:
                    user.profile = UserProfile()

                user.profile.avatar_file_id = avatar_file_id

            await session.commit()
            await session.refresh(user)

            return user

    async def set_password_hash(self, user_id, password_hash: str) -> None:
        async with self._database.session_factory() as session:
            user = await self._require_user(session, user_id)
            user.password_hash = password_hash
            await session.commit()

    async def _require_user(self, session, user_id) -> User:
        user = await session.get(User, user_id)

        if user is None:
            raise NotFoundError(RESOURCE_NOT_FOUND, message="user not found")

        return user

    async def _commit_unique(self, session) -> None:
        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            raise ConflictError(
                CONFLICT_UNIQUE, message="identifier already exists for this tenant"
            ) from error

    async def _ensure_unique(
        self, session, persisted_tenant, identifier_type, raw_value
    ) -> None:
        normalized = self._normalizers.get(identifier_type).normalize(raw_value)

        existing = await session.execute(
            select(LoginIdentifier).where(
                LoginIdentifier.tenant_id == persisted_tenant,
                LoginIdentifier.type == identifier_type,
                LoginIdentifier.normalized_value == normalized,
            )
        )

        if existing.scalar_one_or_none() is not None:
            raise ConflictError(
                CONFLICT_UNIQUE,
                message=f"{identifier_type} already exists for this tenant",
            )

    def _mirror_primary_fields(
        self, user: User, identifiers: list[tuple[str, str]]
    ) -> None:
        for identifier_type, raw_value in identifiers:
            column = self._mirror_fields.get(identifier_type)

            if column is None or getattr(user, column, None) is not None:
                continue

            setattr(
                user,
                column,
                self._normalizers.get(identifier_type).normalize(raw_value),
            )


def _as_int(value):
    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)

    return None
