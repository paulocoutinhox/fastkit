from sqlalchemy import JSON, Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from helpers.db import Base
from helpers.search import search_index
from models.base import IdentifiedMixin, TimestampMixin


class Tenant(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "tenant"
    __table_args__ = (UniqueConstraint("code", name="tenant_code"), UniqueConstraint("domain", name="tenant_domain"), Index("tenant_order", "name"), search_index("tenant_search", "name"))

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    email_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_administrative: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
