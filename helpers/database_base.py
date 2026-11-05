"""The database base shared by application modules."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
