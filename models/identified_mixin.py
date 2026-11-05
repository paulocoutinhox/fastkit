from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column

BigId = BigInteger().with_variant(Integer, "sqlite")


class IdentifiedMixin:
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
