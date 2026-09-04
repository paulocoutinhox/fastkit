import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from config.base import DatabaseSettings
from helpers import db as db_helper
from helpers.db import Base, async_engine, build_engine_options, get_session, is_sqlite
from helpers.errors import ConflictError
from helpers.schema import create_schema, recreate_schema
from models.commerce import UserProduct
from models.subscription import Entitlement
from models.user import User
from tests.factories import make_product


def test_a_sqlite_engine_keeps_no_pool():
    options = build_engine_options(DatabaseSettings(url="sqlite+aiosqlite:///./app.db"))

    assert options["poolclass"] is NullPool
    assert "pool_size" not in options


def test_a_server_engine_is_sized_and_recycled():
    options = build_engine_options(DatabaseSettings(url="mysql+aiomysql://app:app@db/app", pool_size=5, max_overflow=7, pool_recycle=120))

    assert options["pool_size"] == 5
    assert options["max_overflow"] == 7
    assert options["pool_recycle"] == 120


def test_is_sqlite():
    assert is_sqlite("sqlite+aiosqlite:///./app.db") is True
    assert is_sqlite("mysql+aiomysql://app:app@db/app") is False


async def test_foreign_keys_are_enforced(db):
    result = await db.execute(text("PRAGMA foreign_keys"))

    assert result.scalar() == 1


async def test_create_schema_is_idempotent(db):
    """The container runs it before every boot, so the second one has to leave what the first one built alone."""
    await create_schema()
    await create_schema()

    assert await db.scalar(select(func.count()).select_from(User)) == 0


async def test_the_session_rolls_back_a_database_error():
    generator = get_session()
    session = await anext(generator)

    with pytest.raises(SQLAlchemyError):
        await generator.athrow(SQLAlchemyError("broken"))

    assert session.in_transaction() is False


async def test_recreate_drops_a_table_the_metadata_no_longer_declares():
    async with async_engine.begin() as connection:
        await connection.execute(text("CREATE TABLE leftover (id INTEGER PRIMARY KEY)"))

    await recreate_schema()

    async with async_engine.connect() as connection:
        names = await connection.run_sync(lambda sync: inspect(sync).get_table_names())

    assert "leftover" not in names
    assert "commerce_product" in names


async def test_recreate_accepts_an_empty_database():
    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await recreate_schema()

    async with async_engine.connect() as connection:
        names = await connection.run_sync(lambda sync: inspect(sync).get_table_names())

    assert "commerce_product" in names


def preparer_of(name: str):
    return {"postgresql": postgresql, "mysql": mysql, "sqlite": sqlite}[name].dialect().identifier_preparer


def test_a_dialect_that_cascades_says_so_in_the_drop():
    assert db_helper.drop_statement(db_helper.DROP_DIALECTS["postgresql"], preparer_of("postgresql"), "user") == 'DROP TABLE IF EXISTS "user" CASCADE'


def test_a_dialect_that_guards_instead_drops_plainly():
    assert db_helper.drop_statement(db_helper.DROP_DIALECTS["sqlite"], preparer_of("sqlite"), "user") == 'DROP TABLE IF EXISTS "user"'


def test_the_name_is_quoted_the_way_the_dialect_reads_it():
    """MySQL reads a double quoted name as a string, so the whole recreate would fail on the first table."""
    assert db_helper.drop_statement(db_helper.DROP_DIALECTS["mysql"], preparer_of("mysql"), "user") == "DROP TABLE IF EXISTS `user`"


async def test_a_unique_constraint_the_database_enforced_is_a_conflict(db, tenant, member):
    """A second row the constraint refuses has to reach the caller as a conflict, never as an unhandled failure."""
    product = await make_product(db, tenant)

    db.add(UserProduct(user_id=member.id, product_id=product.id, meta={}))
    await db.commit()

    db.add(UserProduct(user_id=member.id, product_id=product.id, meta={}))

    with pytest.raises(ConflictError):
        await db_helper.commit(db)


async def test_a_write_the_database_accepts_commits_quietly(db, tenant, member):
    product = await make_product(db, tenant)

    db.add(UserProduct(user_id=member.id, product_id=product.id, meta={}))

    assert await db_helper.commit(db) is None


async def test_dropping_a_database_that_holds_nothing_does_nothing():
    async with db_helper.async_engine.connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        await connection.run_sync(db_helper.drop_everything)
        await connection.run_sync(db_helper.drop_everything)

        names = await connection.run_sync(lambda sync: inspect(sync).get_table_names())

    assert names == []

    await recreate_schema()


async def test_recreating_the_schema_leaves_the_queue_its_table():
    """The queue is not in Base.metadata, and a database without it is one where no scheduled job can be claimed."""
    await recreate_schema()

    async with db_helper.async_engine.connect() as connection:
        names = await connection.run_sync(lambda sync: inspect(sync).get_table_names())

    assert "queuefy_run" in names
    assert "user" in names


async def test_the_loser_of_an_insert_race_is_handed_the_row_the_winner_wrote(db, tenant, member):
    """Two callers pass the same read at once, and one row is what both of them end up holding."""
    product = await make_product(db, tenant)

    winner = UserProduct(user_id=member.id, product_id=product.id, meta={})
    db.add(winner)
    await db.commit()

    loser = UserProduct(user_id=member.id, product_id=product.id, meta={})
    settled = await db_helper.insert_or_read(db, loser, select(UserProduct).where(UserProduct.user_id == member.id))

    assert settled.id == winner.id
    assert len((await db.execute(select(UserProduct))).scalars().all()) == 1


async def test_an_insert_nobody_raced_is_the_row_that_was_added(db, tenant, member):
    product = await make_product(db, tenant)

    row = UserProduct(user_id=member.id, product_id=product.id, meta={})
    settled = await db_helper.insert_or_read(db, row, select(UserProduct))

    assert settled is row


async def test_a_lost_race_leaves_the_objects_the_caller_already_held_usable(db, tenant, member):
    """A rollback would expire the whole session, and the caller would meet MissingGreenlet instead of the winner's row."""
    product = await make_product(db, tenant)

    db.add(UserProduct(user_id=member.id, product_id=product.id, meta={}))
    await db.commit()

    loser = UserProduct(user_id=member.id, product_id=product.id, meta={})
    await db_helper.insert_or_read(db, loser, select(UserProduct))

    assert product.name
    assert member.email


async def test_two_shared_entitlements_cannot_answer_to_the_same_code(db):
    """The app turns a feature on by code, so two of them reaching every tenant would make the answer a coin toss."""
    db.add(Entitlement(code="member", name="Member", meta={}))
    await db.commit()

    db.add(Entitlement(code="member", name="Another member", meta={}))

    with pytest.raises(ConflictError):
        await db_helper.commit(db)


async def test_the_same_code_belongs_to_one_entitlement_of_each_tenant(db, tenant):
    db.add(Entitlement(code="member", name="Member", meta={}))
    db.add(Entitlement(code="member", name="Member of the tenant", tenant_id=tenant.id, meta={}))

    assert await db_helper.commit(db) is None
