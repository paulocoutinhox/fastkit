from contextlib import asynccontextmanager

from fastkit_db.engine import Database


def sqlite_url(directory) -> str:
    return f"sqlite+aiosqlite:///{directory}/test.db"


@asynccontextmanager
async def managed_database(metadata, directory):
    """Yield a ready SQLite database with the given metadata created."""

    database = Database(url=sqlite_url(directory))
    await database.create_all(metadata)

    try:
        yield database
    finally:
        await database.dispose()
