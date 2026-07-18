from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column


class PrimaryKeyMixin:
    # bigint everywhere, but sqlite only autoincrements INTEGER PRIMARY KEY
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
