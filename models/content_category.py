from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from helpers.search import search_index
from models.addressed_mixin import AddressedMixin
from models.base import tenant_scoped_unique
from models.identified_mixin import BigId, IdentifiedMixin
from models.tenant import Tenant
from models.timestamp_mixin import TimestampMixin


class ContentCategory(Base, IdentifiedMixin, AddressedMixin, TimestampMixin):
    __tablename__ = "content_category"
    __table_args__ = (UniqueConstraint("uuid", name="content_category_uuid"), tenant_scoped_unique("content_category_tag", "tag"), Index("content_category_name", "name"), search_index("content_category_search", "name"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tag: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)
