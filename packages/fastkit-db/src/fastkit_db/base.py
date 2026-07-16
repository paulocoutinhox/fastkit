from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fastkit_db.types import PortableJSON

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PrimaryKeyMixin:
    # bigint everywhere, but sqlite only autoincrements INTEGER PRIMARY KEY
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)


class TenantMixin:
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        self.deleted_at = None


class VersionMixin:
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class MetadataMixin:
    meta: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)


class CreatedByMixin:
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class UpdatedByMixin:
    updated_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ActiveFlagMixin:
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
