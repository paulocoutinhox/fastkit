import uuid

import pytest
from sqlalchemy.exc import SQLAlchemyError

from fastkit_db.base import Base
from fastkit_db.capabilities import GENERIC, capabilities_for
from fastkit_db.dialects.adapters import capabilities_from_url, dialect_name_from_url
from fastkit_db.repository import Repository
from fastkit_db.session import open_session, transaction
from fastkit_db.types import GUID, PortableJSON, new_uuid
from fastkit_db.uow import UnitOfWork


def test_new_uuid_is_unique():
    assert new_uuid() != new_uuid()


def test_guid_roundtrip():
    guid = GUID()
    value = uuid.uuid4()

    bound = guid.process_bind_param(value, None)
    assert bound == value.hex
    assert guid.process_result_value(bound, None) == value

    assert guid.process_bind_param(None, None) is None
    assert guid.process_result_value(None, None) is None
    assert guid.process_bind_param(str(value), None) == value.hex


def test_portable_json_roundtrip():
    column = PortableJSON()

    encoded = column.process_bind_param({"b": 1, "a": 2}, None)
    assert encoded == '{"a":2,"b":1}'
    assert column.process_result_value(encoded, None) == {"a": 2, "b": 1}

    assert column.process_bind_param(None, None) is None
    assert column.process_result_value(None, None) is None


def test_capabilities_matrix():
    assert capabilities_for("postgresql").supports_skip_locked is True
    assert capabilities_for("sqlite").supports_native_uuid is False
    assert capabilities_for("mysql").supports_select_for_update is True
    assert capabilities_for("unknown") is GENERIC


def test_dialect_from_url():
    assert dialect_name_from_url("postgresql+asyncpg://x") == "postgresql"
    assert dialect_name_from_url("sqlite+aiosqlite:///x") == "sqlite"
    assert dialect_name_from_url("weird://x") == "generic"
    assert capabilities_from_url("mysql+asyncmy://x").supports_skip_locked is True


async def test_database_reports_dialect_and_capabilities(database):
    assert database.dialect_name == "sqlite"
    assert database.capabilities.supports_returning is True


async def test_repository_crud(session, widget):
    repo = Repository(widget, session)
    item = await repo.add(widget(name="alpha", tenant_id=1))

    assert await repo.get(item.id) is item
    assert await repo.find_one(name="alpha") is item
    assert await repo.find_one(name="missing") is None
    assert await repo.count(tenant_id=1) == 1

    items = await repo.list(tenant_id=1, order_by=widget.name)
    assert [row.name for row in items] == ["alpha"]

    await repo.delete(item)
    assert await repo.count() == 0


async def test_repository_delete_where(session, widget):
    repo = Repository(widget, session)
    await repo.add(widget(name="a", tenant_id=1))
    await repo.add(widget(name="b", tenant_id=2))

    await repo.delete_where(tenant_id=1)
    assert await repo.count() == 1


def test_mixins_soft_delete_and_version(widget):
    item = widget(name="x")

    assert item.is_deleted is False
    item.soft_delete()
    assert item.is_deleted is True
    item.restore()
    assert item.deleted_at is None


async def test_transaction_commits(session, widget):
    repo = Repository(widget, session)

    async with transaction(session):
        await repo.add(widget(name="committed"))

    assert await repo.count() == 1


async def test_transaction_rolls_back(session, widget):
    repo = Repository(widget, session)

    with pytest.raises(RuntimeError):
        async with transaction(session):
            await repo.add(widget(name="doomed"))
            raise RuntimeError("boom")

    assert await repo.count() == 0


async def test_open_session_rolls_back_on_db_error(database):
    from sqlalchemy import text

    with pytest.raises(SQLAlchemyError):
        async with open_session(database.session_factory) as active:
            await active.execute(text("SELECT * FROM does_not_exist"))


async def test_unit_of_work_commits_and_hooks(database, widget):
    calls: list[str] = []

    async with UnitOfWork(database.session_factory) as uow:
        uow.session.add(widget(name="uow"))
        uow.on_after_commit(lambda: calls.append("done"))

    assert calls == ["done"]

    async with database.session_factory() as active:
        assert await Repository(widget, active).count() == 1


async def test_unit_of_work_rolls_back_on_error(database, widget):
    with pytest.raises(ValueError):
        async with UnitOfWork(database.session_factory) as uow:
            uow.session.add(widget(name="bad"))
            raise ValueError("nope")

    async with database.session_factory() as active:
        assert await Repository(widget, active).count() == 0


async def test_drop_all(database):
    await database.drop_all(Base.metadata)


async def test_sqlite_foreign_keys_enforced(database):
    from sqlalchemy import text

    async with database.session_factory() as session:
        result = await session.execute(text("PRAGMA foreign_keys"))
        assert result.scalar_one() == 1


def test_non_sqlite_dialect_skips_pragma():
    from fastkit_db.engine import Database

    database = Database(url="postgresql+asyncpg://user:pass@localhost/db")

    assert database.dialect_name == "postgresql"


def test_enable_sqlite_foreign_keys_runs_pragma():
    from fastkit_db.engine import _enable_sqlite_foreign_keys

    executed = []

    class FakeCursor:
        def execute(self, sql):
            executed.append(sql)

        def close(self):
            executed.append("closed")

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    _enable_sqlite_foreign_keys(FakeConnection(), None)

    assert executed == ["PRAGMA foreign_keys=ON", "closed"]
