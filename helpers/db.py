"""The engine, the session and the two writes that settle a race instead of failing one."""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, AsyncIterator

from fastapi import Depends
from sqlalchemy import Select, event, inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from config.base import DatabaseSettings
from helpers.errors import ConflictError
from helpers.settings import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DropDialect:
    """What one dialect needs to drop a table other tables still point at."""

    disable: str
    enable: str
    cascade: bool = False


DROP_DIALECTS = {"sqlite": DropDialect("PRAGMA foreign_keys=OFF", "PRAGMA foreign_keys=ON"), "mysql": DropDialect("SET FOREIGN_KEY_CHECKS=0", "SET FOREIGN_KEY_CHECKS=1"), "postgresql": DropDialect("SET session_replication_role = replica", "SET session_replication_role = origin", cascade=True)}


def is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def build_engine_options(database: DatabaseSettings) -> dict:
    """SQLite is a file the tests recreate constantly so it keeps no pool, while a server engine is sized and recycled."""
    options = {"echo": database.echo, "pool_pre_ping": True}

    if is_sqlite(database.url):
        options["poolclass"] = NullPool

        return options

    options["pool_size"] = database.pool_size
    options["max_overflow"] = database.max_overflow
    options["pool_recycle"] = database.pool_recycle

    # The code reads, decides and reads again inside one transaction, which under repeatable read answers the snapshot it opened with and never what another node has since committed.
    options["isolation_level"] = "READ COMMITTED"

    return options


def ensure_sqlite_directory(url: str) -> None:
    """Creates the directory the database file sits in, which the driver never does on its own."""
    Path(url.split("///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)


def enforce_foreign_keys(connection, record):
    """Turns foreign keys on for every SQLite connection, because they are off by default and the cascades of this schema depend on them."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


if is_sqlite(settings.database.url):
    ensure_sqlite_directory(settings.database.url)

async_engine = create_async_engine(settings.database.url, **build_engine_options(settings.database))

AsyncSessionLocal = async_sessionmaker(bind=async_engine, autoflush=False, expire_on_commit=False)

if is_sqlite(settings.database.url):
    event.listen(async_engine.sync_engine, "connect", enforce_foreign_keys)


class Base(DeclarativeBase):
    pass


def run_scoped(coroutine):
    """A command may open more than one loop, and a connection the pool kept from one that ended cannot serve the next."""

    async def scoped():
        try:
            return await coroutine
        finally:
            await async_engine.dispose()

    return asyncio.run(scoped())


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except SQLAlchemyError:
            logger.exception("Database session error")
            await session.rollback()
            raise


async def insert_or_read(session: AsyncSession, instance, read: Select):
    """Two callers pass the same read at once and the database settles it: the loser is handed the row the winner wrote."""
    # The row is looked for before it is written, so a caller meeting one that is already there never issues the insert that would lock it.
    settled = await session.scalar(read)

    if settled is not None:
        return settled

    # A savepoint undoes the insert alone, where a rollback would expire every object the caller already holds.
    try:
        async with session.begin_nested():
            session.add(instance)
    except IntegrityError:
        # The read is plain because the session runs at read committed, and locking the row the winner wrote is what turns a handful of losers into a deadlock.
        return await session.scalar(read)

    return instance


@asynccontextmanager
async def refusing(session: AsyncSession, code: str) -> AsyncIterator[None]:
    """A constraint the database enforced anywhere in here is a conflict the caller can act on, because a statement refuses where it runs and not only at the commit."""
    try:
        yield
    except IntegrityError as error:
        await session.rollback()
        logger.warning("integrity error: %s", error)

        raise ConflictError(code) from error


async def commit(session: AsyncSession, code: str = "error.duplicated-record") -> None:
    """The write settled, where a key the database refused is named by whoever asked for the write."""
    async with refusing(session, code):
        await session.commit()


def drop_statement(dialect: DropDialect, preparer, name: str) -> str:
    """The name is quoted by the dialect itself, because MySQL reads a double quoted identifier as a string and refuses the statement."""
    quoted = preparer.quote_identifier(name)

    if dialect.cascade:
        return f"DROP TABLE IF EXISTS {quoted} CASCADE"

    return f"DROP TABLE IF EXISTS {quoted}"


def drop_everything(connection) -> None:
    """The database is read for what it holds, so every table it carries goes and not only what the metadata declares."""
    names = inspect(connection).get_table_names()

    if not names:
        return

    dialect = DROP_DIALECTS[connection.dialect.name]
    connection.exec_driver_sql(dialect.disable)

    for name in names:
        connection.exec_driver_sql(drop_statement(dialect, connection.dialect.identifier_preparer, name))

    connection.exec_driver_sql(dialect.enable)


DatabaseSession = Annotated[AsyncSession, Depends(get_session)]
