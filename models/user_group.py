from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from helpers.search import search_index
from models.base import tenant_scoped_unique
from models.identified_mixin import BigId, IdentifiedMixin
from models.tenant import Tenant
from models.timestamp_mixin import TimestampMixin


class UserGroup(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "user_group"
    __table_args__ = (tenant_scoped_unique("user_group_tenant_code", "code"), search_index("user_group_search", "name"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)
