from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, PrimaryKeyMixin, TimestampMixin


class GeoSample(PrimaryKeyMixin, TimestampMixin, Base):
    """Exercises triple dependent country→state→city selects and lookups with slow remote options."""

    __tablename__ = "demo_geo"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sel_country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sel_state: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sel_city: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sel_district: Mapped[str | None] = mapped_column(String(8), nullable=True)
    look_country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    look_state: Mapped[str | None] = mapped_column(String(8), nullable=True)
    look_city: Mapped[str | None] = mapped_column(String(8), nullable=True)
    look_district: Mapped[str | None] = mapped_column(String(8), nullable=True)

    def display_label(self) -> str:
        return self.name
