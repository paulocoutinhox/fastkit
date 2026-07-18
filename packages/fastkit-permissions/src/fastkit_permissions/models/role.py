from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin


class Role(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "role"

    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def display_label(self) -> str:
        return self.name
