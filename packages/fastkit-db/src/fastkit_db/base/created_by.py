from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column


class CreatedByMixin:
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
