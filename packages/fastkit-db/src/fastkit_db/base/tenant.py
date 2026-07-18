from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column


class TenantMixin:
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
