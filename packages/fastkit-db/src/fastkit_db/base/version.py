from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column


class VersionMixin:
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
