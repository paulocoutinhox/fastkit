from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from enums.country import PostalCodeProvider
from helpers.db import Base
from helpers.search import search_index
from models.base import IdentifiedMixin, TimestampMixin, enum_type


class Country(Base, IdentifiedMixin, TimestampMixin):
    """A country an address can be written in, which is also where the postal code of that address is looked up."""

    __tablename__ = "country"
    __table_args__ = (UniqueConstraint("code_iso_3166_1", name="country_code_iso_3166_1"), Index("country_name", "name"), search_index("country_search", "name"))

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code_iso_3166_1: Mapped[str] = mapped_column(String(2), nullable=False)

    # A country with nobody to ask draws a plain field, which is why this is a column and not a table of its own.
    postal_code_provider: Mapped[PostalCodeProvider | None] = mapped_column(enum_type(PostalCodeProvider, 32), nullable=True)

    # The shape a number of this country is written in, where a zero is a digit somebody types, and a country without one draws a plain field.
    phone_mask: Mapped[str | None] = mapped_column(String(32), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
