from sqlalchemy import text

from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_core.health.base import HealthResult, HealthStatus
from fastkit_db.base import Base
from fastkit_db.engine import Database


async def _database_health(database: Database) -> HealthResult:
    try:
        async with database.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        return HealthResult("database", HealthStatus.healthy)
    except Exception as error:
        return HealthResult("database", HealthStatus.unavailable, detail=str(error))


class DbApp(FastKitApp):
    name = "fastkit.db"
    label = "db"
    version = "1.0.0"
    requires = ("fastkit.core",)

    def register_services(self, context: BootstrapContext) -> None:
        settings = context.settings.database
        database = Database(
            url=settings.url,
            pool_pre_ping=settings.pool_pre_ping,
            pool_recycle=settings.pool_recycle,
            echo=settings.echo,
        )

        context.set_component("database", database)
        context.set_component("metadata", Base.metadata)

        context.health.register("database", lambda: _database_health(database))

    async def shutdown(self, context: BootstrapContext) -> None:
        database = context.runtime.try_component("database")

        if database is not None:
            await database.dispose()
