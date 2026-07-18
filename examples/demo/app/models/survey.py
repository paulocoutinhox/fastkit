from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, PrimaryKeyMixin, TimestampMixin


class Survey(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "demo_survey"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def display_label(self) -> str:
        return self.name
