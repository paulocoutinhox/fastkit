from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column


class UpdatedByMixin:
    updated_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
