from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped, mapped_column


class ActiveFlagMixin:
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
