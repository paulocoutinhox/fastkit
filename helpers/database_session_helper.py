"""Restores session records and ordered batch results after transaction rollback."""

from sqlalchemy import case, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseSessionHelper:
    @staticmethod
    async def read(db: AsyncSession, model, identifiers: list[int], *options) -> list:
        if not identifiers:
            return []

        ordering = case({identifier: position for position, identifier in enumerate(identifiers)}, value=model.id)
        statement = select(model).where(model.id.in_(identifiers)).options(*options).order_by(ordering).execution_options(populate_existing=True)

        return list((await db.scalars(statement)).all())

    @staticmethod
    async def refresh_expired(db: AsyncSession, *records) -> None:
        for record in records:
            if record is not None and inspect(record).expired_attributes:
                await db.refresh(record)
