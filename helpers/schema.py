"""Building the schema needs the engine and the models both, so it lives above the two and neither of them defers an import."""

from cachefy.store.sqlalchemy import metadata as cache_metadata
from queuefy.store.sqlalchemy import metadata as task_metadata

import models.registry  # noqa: F401
from helpers.db import Base, async_engine, drop_everything

# Every metadata this application owns tables in, declared once because the queue and the cache each keep their own.
SCHEMAS = (Base.metadata, task_metadata, cache_metadata)


async def run_schema(*operations):
    async with async_engine.begin() as connection:
        for operation in operations:
            await connection.run_sync(operation)


async def create_schema():
    """Creates every table the application needs, the queue and the cache included, because both live in metadata of their own."""
    await run_schema(*(metadata.create_all for metadata in SCHEMAS))


async def recreate_schema():
    """Drops every table the database holds and builds the schema again, losing whatever it held."""
    # Dropping runs outside a transaction, which is the only place SQLite lets the foreign key guard move.
    async with async_engine.connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        await connection.run_sync(drop_everything)

    await create_schema()
