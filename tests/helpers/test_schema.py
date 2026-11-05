"""The schema is built under a lock of the session wherever more than one copy can build it at once."""

import pytest
from sqlalchemy import event

import helpers.schema_lock as helpers_schema_lock_module
from helpers import schema
from helpers.db import DROP_DIALECTS, async_engine

LOCK = helpers_schema_lock_module.SchemaLock("SELECT 1 /* take */", "SELECT 1 /* release */")


def test_migrate_builds_every_table_in_a_fresh_process(tmp_path):
    import json
    import subprocess
    import sys

    from helpers.settings import settings

    script = """
import asyncio
import json
import sys

from helpers.settings import settings

settings.database.url = f"sqlite+aiosqlite:///{sys.argv[1]}"

from helpers.commands import execute_from_command_line

assert execute_from_command_line(["manage.py", "migrate"]) == 0

from helpers.db import async_engine
from sqlalchemy import inspect

async def tables():
    async with async_engine.connect() as connection:
        names = await connection.run_sync(lambda sync: inspect(sync).get_table_names())

    await async_engine.dispose()

    return names

print(json.dumps(asyncio.run(tables())))
"""
    done = subprocess.run([sys.executable, "-c", script, str(tmp_path / "schema.db")], cwd=settings.base_dir, capture_output=True, text=True, check=True, timeout=30)
    expected = {table.name for metadata in schema.SCHEMAS for table in metadata.sorted_tables}

    assert "user" in expected
    assert set(json.loads(done.stdout.splitlines()[-1])) == expected


@pytest.fixture
def statements():
    heard = []

    def listen(connection, cursor, statement, *rest):
        heard.append(statement)

    event.listen(async_engine.sync_engine, "before_cursor_execute", listen)
    yield heard
    event.remove(async_engine.sync_engine, "before_cursor_execute", listen)


async def test_a_server_database_builds_the_schema_holding_its_lock_and_gives_it_back(monkeypatch, statements):
    monkeypatch.setitem(schema.SCHEMA_LOCKS, "sqlite", LOCK)

    await schema.run_schema(lambda connection: statements.append("built"))

    assert statements == [LOCK.take, "built", LOCK.release]


async def test_a_lock_that_waits_forever_on_its_own_is_bounded_before_it_is_taken(monkeypatch, statements):
    bounded = helpers_schema_lock_module.SchemaLock("SELECT 1 /* take */", "SELECT 1 /* release */", "SELECT 1 /* bound */")
    monkeypatch.setitem(schema.SCHEMA_LOCKS, "sqlite", bounded)

    await schema.run_schema(lambda connection: statements.append("built"))

    assert statements == [bounded.bound, bounded.take, "built", bounded.release]


async def test_the_lock_is_given_back_when_the_building_fails(monkeypatch, statements):
    monkeypatch.setitem(schema.SCHEMA_LOCKS, "sqlite", LOCK)

    def failing(connection):
        raise ValueError("a table nobody can build")

    with pytest.raises(ValueError):
        await schema.run_schema(failing)

    assert statements == [LOCK.take, LOCK.release]


async def test_a_lock_another_copy_kept_is_a_refusal_and_never_a_build_over_it(monkeypatch):
    built = []
    monkeypatch.setitem(schema.SCHEMA_LOCKS, "sqlite", helpers_schema_lock_module.SchemaLock("SELECT 0", "SELECT 1"))

    with pytest.raises(RuntimeError):
        await schema.run_schema(built.append)

    assert built == []


def test_every_dialect_the_engine_can_drop_says_how_it_locks_the_schema():
    assert set(schema.SCHEMA_LOCKS) == set(DROP_DIALECTS)
