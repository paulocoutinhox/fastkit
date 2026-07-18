from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError

from fastkit_core.errors.codes import VALIDATION_FAILED
from fastkit_core.errors.exceptions import FieldError, ValidationError
from fastkit_permissions.models import Permission, Role, RolePermission, UserRole
from fastkit_tenancy.constants import to_persisted


class PermissionService:
    """Manages roles and assignments and computes a user's effective permissions.

    A role is a named set of permissions, so there is no separate group concept.
    """

    def __init__(self, database, cache=None):
        self._database = database
        self._cache = cache

    async def create_permission(
        self, code: str, name: str, group: str = "General", scope: str = "tenant"
    ) -> Permission:
        async with self._database.session_factory() as session:
            permission = Permission(code=code, name=name, group=group, scope=scope)
            session.add(permission)
            await session.commit()
            await session.refresh(permission)

            return permission

    async def create_role(
        self, name: str, tenant_id: int | None = None, description: str | None = None
    ) -> Role:
        async with self._database.session_factory() as session:
            role = Role(
                name=name, description=description, tenant_id=to_persisted(tenant_id)
            )
            session.add(role)
            await session.commit()
            await session.refresh(role)

            return role

    async def grant_permission(self, role_id, permission_id) -> None:
        await self._add(RolePermission(role_id=role_id, permission_id=permission_id))

    async def assign_role(self, user_id, role_id, tenant_id: int | None = None) -> None:
        await self._add(
            UserRole(
                user_id=user_id, role_id=role_id, tenant_id=to_persisted(tenant_id)
            )
        )

    async def set_role_permissions(self, role_id, permission_ids: list) -> None:
        """Replace the whole permission set of a role in a single transaction."""

        unique_ids = list(dict.fromkeys(permission_ids))

        async with self._database.session_factory() as session:
            await session.execute(
                delete(RolePermission).where(RolePermission.role_id == role_id)
            )

            for permission_id in unique_ids:
                session.add(
                    RolePermission(role_id=role_id, permission_id=permission_id)
                )

            try:
                await session.commit()
            except IntegrityError as error:
                raise ValidationError(
                    VALIDATION_FAILED,
                    field_errors=[
                        FieldError("permission_ids", "validation.unknown-reference")
                    ],
                ) from error

        if self._cache is not None:
            self._cache.bump_version()

    async def role_permission_ids(self, role_id) -> list:
        async with self._database.session_factory() as session:
            result = await session.execute(
                select(RolePermission.permission_id).where(
                    RolePermission.role_id == role_id
                )
            )

            return list(result.scalars().all())

    async def permissions_grouped(self) -> list[dict]:
        """Return permissions organized by their group, for a grouped selector."""

        async with self._database.session_factory() as session:
            result = await session.execute(
                select(Permission).order_by(Permission.group, Permission.code)
            )
            permissions = result.scalars().all()

        grouped: dict[str, list] = {}

        for permission in permissions:
            grouped.setdefault(permission.group, []).append(
                {
                    "id": str(permission.id),
                    "code": permission.code,
                    "name": permission.name,
                }
            )

        return [
            {"group": group, "permissions": items} for group, items in grouped.items()
        ]

    async def compute_permissions(self, user_id, tenant_id: int | None) -> set[str]:
        persisted = to_persisted(tenant_id)

        async with self._database.session_factory() as session:
            role_ids = await self._role_ids_for_user(session, user_id, persisted)

            if not role_ids:
                return set()

            query = (
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id.in_(role_ids))
            )
            result = await session.execute(query)

            return set(result.scalars().all())

    async def _role_ids_for_user(self, session, user_id, persisted_tenant) -> set:
        direct = await session.execute(
            select(UserRole.role_id).where(
                UserRole.user_id == user_id,
                or_(
                    UserRole.tenant_id == persisted_tenant, UserRole.tenant_id.is_(None)
                ),
            )
        )

        return set(direct.scalars().all())

    async def _add(self, row) -> None:
        async with self._database.session_factory() as session:
            session.add(row)

            try:
                await session.commit()
            except IntegrityError:
                # the assignment already exists, so the desired state is reached and this is a no-op
                await session.rollback()
                return

        if self._cache is not None:
            self._cache.bump_version()
