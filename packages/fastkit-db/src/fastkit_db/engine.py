from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from fastkit_db.capabilities import DatabaseCapabilities, capabilities_for


def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    # sqlite does not enforce foreign keys (and therefore cascade deletes) unless asked
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Database:
    """Owns the async engine and session factory and exposes dialect capabilities."""

    def __init__(
        self,
        url: str,
        pool_pre_ping: bool = True,
        pool_recycle: int = 1800,
        echo: bool = False,
    ):
        self.url = url
        self.engine: AsyncEngine = create_async_engine(
            url, pool_pre_ping=pool_pre_ping, pool_recycle=pool_recycle, echo=echo
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

        if self.dialect_name == "sqlite":
            event.listen(
                self.engine.sync_engine, "connect", _enable_sqlite_foreign_keys
            )

    @property
    def dialect_name(self) -> str:
        return self.engine.dialect.name

    @property
    def capabilities(self) -> DatabaseCapabilities:
        return capabilities_for(self.dialect_name)

    async def create_all(self, metadata) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)

    async def drop_all(self, metadata) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)

    async def dispose(self) -> None:
        await self.engine.dispose()
