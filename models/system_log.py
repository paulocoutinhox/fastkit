from sqlalchemy import JSON, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.system_log import LogCategory, LogLevel
from helpers.db import Base
from models.base import BigId, IdentifiedMixin, TimestampMixin, enum_type
from models.tenant import Tenant
from models.user import User


class SystemLog(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "system_log"
    # Level and category are read off a handful of values, so no index over one of them narrows anything — and this is the table that grows fastest.
    __table_args__ = (Index("system_log_created_at", "created_at"), Index("system_log_tenant", "tenant_id", "created_at"), Index("system_log_user", "user_id", "created_at"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    level: Mapped[LogLevel] = mapped_column(enum_type(LogLevel, 16), default=LogLevel.DEBUG, nullable=False)
    category: Mapped[LogCategory | None] = mapped_column(enum_type(LogCategory), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)
    user: Mapped[User | None] = relationship(User)
