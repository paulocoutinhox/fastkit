from typing import Generic, TypeVar

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class Repository(Generic[ModelT]):
    """Generic async repository providing the common data access operations."""

    def __init__(self, model: type[ModelT], session: AsyncSession):
        self.model = model
        self.session = session

    async def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()

        return instance

    async def get(self, identifier) -> ModelT | None:
        return await self.session.get(self.model, identifier)

    async def find_one(self, **filters) -> ModelT | None:
        result = await self.session.execute(self._filtered_query(filters))

        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 100, order_by=None, **filters) -> list[ModelT]:
        query = self._filtered_query(filters)

        if order_by is not None:
            query = query.order_by(order_by)

        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)

        return list(result.scalars().all())

    async def count(self, **filters) -> int:
        query = select(func.count()).select_from(self.model)

        for column, value in filters.items():
            query = query.where(getattr(self.model, column) == value)

        result = await self.session.execute(query)

        return int(result.scalar_one())

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
        await self.session.flush()

    async def delete_where(self, **filters) -> None:
        query = sa_delete(self.model)

        for column, value in filters.items():
            query = query.where(getattr(self.model, column) == value)

        await self.session.execute(query)

    def _filtered_query(self, filters: dict):
        query = select(self.model)

        for column, value in filters.items():
            query = query.where(getattr(self.model, column) == value)

        return query
