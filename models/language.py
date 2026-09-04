from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from helpers.db import Base
from helpers.search import search_index
from models.base import IdentifiedMixin, TimestampMixin


class Language(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "language"
    __table_args__ = (UniqueConstraint("code_iso_639_1", name="language_code_iso_639_1"), Index("language_name", "name"), Index("language_code_iso_language", "code_iso_language"), search_index("language_search", "name", "native_name"))

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    native_name: Mapped[str] = mapped_column(String(255), nullable=False)
    code_iso_639_1: Mapped[str] = mapped_column(String(8), nullable=False)
    code_iso_language: Mapped[str] = mapped_column(String(16), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
