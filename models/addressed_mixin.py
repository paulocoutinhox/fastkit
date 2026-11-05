from uuid import uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class AddressedMixin:
    """The name a record answers by outside this application, because an autoincrement id is guessable and says how many of them exist."""

    uuid: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()), nullable=False)
