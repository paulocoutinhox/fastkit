"""Building the schema needs the engine and the models both, so it lives above the two and neither of them defers an import."""

from contextlib import asynccontextmanager

from cachefy.store.sqlalchemy import metadata as cache_metadata
from queuefy.store.sqlalchemy import metadata as task_metadata

import models.registry  # noqa: F401
from helpers.database_base import Base
from helpers.db import async_engine, drop_everything
from helpers.schema_lock import SchemaLock

# Every metadata this application owns tables in, declared once because the queue and the cache each keep their own.
SCHEMAS = (Base.metadata, task_metadata, cache_metadata)


# Copies of the image starting together each build the schema, and without a lock the one that loses dies on a table the other just created.
# SQLite is a file one writer holds at a time, so it has nothing to take.
# A MySQL lock is named for the whole server, so the name carries the database, or a stage and a production on the same server would wait on each other.
# The PostgreSQL lock waits forever on its own, so the transaction that takes it is bounded to the same ten minutes the MySQL one gives up after.
SCHEMA_LOCKS = {"sqlite": None, "mysql": SchemaLock("SELECT GET_LOCK(CONCAT('schema:', DATABASE()), 600)", "SELECT RELEASE_LOCK(CONCAT('schema:', DATABASE()))"), "postgresql": SchemaLock("SELECT 1 FROM pg_advisory_lock(7263)", "SELECT 1 FROM pg_advisory_unlock(7263)", "SET LOCAL lock_timeout = '600s'")}


@asynccontextmanager
async def held(connection):
    lock = SCHEMA_LOCKS[connection.dialect.name]

    if lock is None:
        yield

        return

    if lock.bound is not None:
        await connection.exec_driver_sql(lock.bound)

    if (await connection.exec_driver_sql(lock.take)).scalar() != 1:
        raise RuntimeError("another copy held the schema lock for ten minutes, so this one gives up instead of building over it")

    # The lock belongs to the session and a pooled connection outlives this call, so it is given back whatever the building did.
    try:
        yield
    finally:
        await connection.exec_driver_sql(lock.release)


async def run_schema(*operations):
    async with async_engine.begin() as connection, held(connection):
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
