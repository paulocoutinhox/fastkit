import logging
from contextlib import asynccontextmanager

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("fastkit.db")


@asynccontextmanager
async def open_session(session_factory):
    """Yield a session, rolling back on any database error before re-raising."""

    session: AsyncSession = session_factory()

    try:
        yield session
    except SQLAlchemyError:
        logger.exception("database session error")
        await session.rollback()
        raise
    finally:
        await session.close()


@asynccontextmanager
async def transaction(session: AsyncSession):
    """Explicit transaction boundary that commits on success and rolls back on error."""

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
