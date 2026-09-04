"""The suite runs on SQLite and production runs on MySQL, so syntax only one of them accepts passes every test and fails where it counts."""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects import mysql

import models.registry  # noqa
from helpers.db import Base
from models.integration import WebhookEvent

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ("services", "helpers", "routes", "models", "jobs", "schemas", "enums", "config")


def sources() -> list[Path]:
    return [path for folder in SOURCE for path in (ROOT / folder).rglob("*.py")]


def test_no_query_orders_with_a_nulls_clause_mysql_refuses():
    """MySQL 8.4 answers `NULLS LAST` with a syntax error, and SQLite accepts it — write `column.is_(None)` first instead."""
    offenders = [f"{path.relative_to(ROOT)}:{number}" for path in sources() for number, line in enumerate(path.read_text().splitlines(), 1) if "nullslast(" in line or "nullsfirst(" in line]

    assert offenders == [], f"these order by a clause mysql refuses: {offenders}"


def test_the_statement_behind_a_subscription_extract_compiles_for_mysql():
    """The one that broke it in production, kept as the sample of the whole class."""
    statement = select(WebhookEvent.id).order_by(WebhookEvent.occurred_at.is_(None), WebhookEvent.occurred_at.desc(), WebhookEvent.id.desc())

    assert "NULLS" not in str(statement.compile(dialect=mysql.dialect())).upper()


def test_every_timestamp_column_keeps_its_fraction_on_mysql():
    """MySQL stores whole seconds unless the column asks for the fraction, and a truncated timestamp stops equalling the one still in memory: a reconciliation would then rewrite what nobody changed, on every pass, forever."""
    from sqlalchemy.schema import CreateTable

    from helpers.db import Base
    from models.base import UtcDateTime

    offenders = []

    for table in Base.metadata.sorted_tables:
        stamped = [column.name for column in table.columns if isinstance(column.type, UtcDateTime)]

        if not stamped:
            continue

        ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
        offenders += [f"{table.name}.{name}" for name in stamped if f"{name} DATETIME(6)" not in ddl]

    assert offenders == [], f"these would be rounded to the second by mysql: {offenders}"


def test_every_number_a_client_writes_fits_the_column_it_lands_in():
    """SQLite holds whatever it is handed and MySQL does not, so a field bounded only from below passes every test here and answers out of range in production."""
    import importlib
    import pkgutil

    from pydantic import BaseModel
    from sqlalchemy import BigInteger, Integer

    import schemas
    from helpers.db import Base
    from models.base import BIG_INTEGER_MAX, INTEGER_MAX

    # What each column of that name holds, read off the schema rather than assumed.
    widths = {}

    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, BigInteger):
                widths.setdefault(column.name, BIG_INTEGER_MAX)
            elif isinstance(column.type, Integer):
                widths[column.name] = min(widths.get(column.name, INTEGER_MAX), INTEGER_MAX)

    offenders = []
    checked = 0

    for module in pkgutil.iter_modules(schemas.__path__):
        loaded = importlib.import_module(f"schemas.{module.name}")

        for name, klass in vars(loaded).items():
            if not (isinstance(klass, type) and issubclass(klass, BaseModel) and klass.__module__ == loaded.__name__):
                continue

            if not name.endswith(("Create", "Update", "Request")):
                continue

            for field_name, info in klass.model_fields.items():
                if info.annotation not in (int, int | None) or field_name not in widths:
                    continue

                checked += 1
                ceiling = next((getattr(item, "le", None) for item in info.metadata if getattr(item, "le", None) is not None), None)

                if ceiling is None or ceiling > widths[field_name]:
                    offenders.append(f"{name}.{field_name} against {widths[field_name]}")

    assert checked >= 10, f"the scan read only {checked} fields, so it is proving nothing"
    assert offenders == [], f"these are written by a client and reach a column that cannot hold them: {offenders}"


def test_every_named_thing_in_the_schema_begins_with_the_table_it_belongs_to():
    """An index name is database wide on PostgreSQL, and a name that drops the table of its own is one nobody can resolve back to it."""
    from collections import Counter

    named = []

    for table_name, table in Base.metadata.tables.items():
        named += [(table_name, index.name) for index in table.indexes]
        named += [(table_name, constraint.name) for constraint in table.constraints if type(constraint).__name__ in ("UniqueConstraint", "ForeignKeyConstraint") and constraint.name]

    astray = sorted(f"{name} belongs to {table} and does not begin with it" for table, name in named if not name.startswith(table))
    repeated = sorted(name for name, count in Counter(name for _, name in named).items() if count > 1)
    long = sorted(name for _, name in named if len(name) > 64)

    assert len(named) >= 100, f"the scan read only {len(named)} named things, so it is proving nothing"
    assert astray == [], f"these do not name the table they belong to: {astray}"
    assert repeated == [], f"these are used twice, which PostgreSQL refuses: {repeated}"
    assert long == [], f"these are longer than an identifier MySQL accepts: {long}"


def test_no_ordering_leaves_what_a_null_means_to_the_dialect():
    """MySQL and SQLite read a null as the smallest value and PostgreSQL as the largest, so an order that decides which row answers has to say which it wants."""
    import ast

    nullable = {f"{mapper.class_.__name__}.{column.key}" for mapper in Base.registry.mappers for column in mapper.local_table.columns if column.nullable}
    quiet, counted = [], 0

    for path in [*Path("services").rglob("*.py"), *Path("routes").rglob("*.py"), *Path("helpers").rglob("*.py")]:
        tree = ast.parse(path.read_text())

        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.Return, ast.Expr)):
                continue

            statement = ast.unparse(node)

            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call) or not isinstance(inner.func, ast.Attribute) or inner.func.attr != "order_by":
                    continue

                for argument in inner.args:
                    named = ast.unparse(argument).split(".desc")[0].split(".asc")[0]
                    counted += 1

                    # Saying it is either a predicate on the same column, or a filter that keeps every null out of the answer.
                    if named in nullable and f"{named}.is_(None)" not in statement and f"{named}.is_not(None)" not in statement:
                        quiet.append(f"{path}:{inner.lineno}: {named}")

    assert counted >= 20, f"the scan read only {counted} orderings, so it is proving nothing"
    assert sorted(set(quiet)) == [], f"these leave what a null means to the dialect: {sorted(set(quiet))}"


async def test_the_balance_a_movement_is_written_on_top_of_is_read_under_a_lock(db, member):
    """SQLite has no row lock, so the suite passes without one and production loses a movement every time two arrive together."""
    from sqlalchemy import event
    from sqlalchemy.dialects import mysql

    from helpers.db import async_engine
    from services.account import user_balance_service
    from tests.factories import make_currency

    currency = await make_currency(db)
    seen = []

    def note(conn, clause, multiparams, params, execution_options):
        seen.append(clause)

    event.listen(async_engine.sync_engine, "before_execute", note)

    try:
        await user_balance_service.held(db, member.id, currency.id)
    finally:
        event.remove(async_engine.sync_engine, "before_execute", note)

    written = [str(clause.compile(dialect=mysql.dialect())) for clause in seen if hasattr(clause, "compile")]

    assert written, "the read of the balance was not seen at all"
    assert any("FOR UPDATE" in statement for statement in written), "the balance is read without the lock the movement on top of it depends on"
