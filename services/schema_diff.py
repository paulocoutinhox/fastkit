"""What the database should be, against what it is, without anybody having to remember since when."""

import asyncio
import pathlib
import secrets
import socket
import subprocess
import time
from urllib.parse import unquote, urlsplit

from sqlalchemy import text
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import AddConstraint, CreateIndex, CreateTable, UniqueConstraint

import models.registry  # noqa: F401
from helpers.schema import SCHEMAS
from helpers.settings import settings

OUTPUT = pathlib.Path("extras/schema")
IMAGE = "mysql:8"
CONTAINER = "fastkit-schema"
FRESH = "esquema_do_zero"
CURRENT = "esquema_atual"

COLUMNS = "SELECT table_name, column_name, column_type, is_nullable, IFNULL(column_default, ''), extra FROM information_schema.columns WHERE table_schema = :schema"
INDEXES = "SELECT table_name, index_name, non_unique, GROUP_CONCAT(column_name ORDER BY seq_in_index), IFNULL(GROUP_CONCAT(expression ORDER BY seq_in_index), '') FROM information_schema.statistics WHERE table_schema = :schema GROUP BY table_name, index_name, non_unique"
KEYS = "SELECT k.table_name, k.column_name, k.referenced_table_name, k.referenced_column_name, r.delete_rule FROM information_schema.key_column_usage k JOIN information_schema.referential_constraints r ON r.constraint_schema = k.table_schema AND r.constraint_name = k.constraint_name WHERE k.table_schema = :schema"
TABLES = "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"


def target() -> dict:
    """The database this run is about, taken from the configuration the environment selected."""
    parts = urlsplit(settings.database.url)

    # The URL carries the credentials escaped, and a client handed the escaped form is a client with the wrong password.
    return {"host": parts.hostname, "port": parts.port or 3306, "user": unquote(parts.username or ""), "password": unquote(parts.password or ""), "name": (parts.path or "/").lstrip("/")}


def docker(*arguments: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *arguments], capture_output=True, text=True, check=check)


def start_container() -> int:
    """A throwaway server, because the only trustworthy shape of a fresh schema is one a server built."""
    docker("rm", "-f", CONTAINER, check=False)

    port = 33000 + secrets.randbelow(2000)
    docker("run", "-d", "--name", CONTAINER, "-e", "MYSQL_ROOT_PASSWORD=schema", "-e", f"MYSQL_DATABASE={FRESH}", "-p", f"{port}:3306", IMAGE)

    # The entrypoint answers on a temporary server before it restarts the real one, so readiness is a connection through the port this run will use.
    for _ in range(120):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            asyncio.run(answers(port))

            return port
        except Exception:
            time.sleep(1)

    raise RuntimeError("the throwaway mysql did not answer in two minutes")


async def answers(port: int) -> None:
    engine = create_async_engine(f"mysql+aiomysql://root:schema@127.0.0.1:{port}/{FRESH}")

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


async def build_fresh(port: int) -> None:
    """Built from the very list the application creates, or a table it owns elsewhere reads as one the database has over."""
    engine = create_async_engine(f"mysql+aiomysql://root:schema@127.0.0.1:{port}/{FRESH}")

    async with engine.begin() as connection:
        for metadata in SCHEMAS:
            await connection.run_sync(metadata.create_all)

    await engine.dispose()


def reachable(host: str) -> str:
    """The dump runs inside the container, where this machine is not localhost."""
    if host == "container":
        return "127.0.0.1"

    return "host.docker.internal" if host in ("127.0.0.1", "localhost", "::1") else host


def dump(where: dict, schema: str, path: pathlib.Path) -> None:
    """The dump is written by the client of the server itself, so nothing here writes ddl by hand."""
    done = docker("exec", CONTAINER, "mysqldump", "--no-data", "--skip-comments", "--skip-set-charset", f"-h{reachable(where['host'])}", f"-P{where['port']}", f"-u{where['user']}", f"-p{where['password']}", schema, check=False)

    if done.returncode != 0:
        raise RuntimeError(f"mysqldump refused {schema}: {done.stderr.strip().splitlines()[-1] if done.stderr else 'no reason given'}")

    path.write_text(done.stdout)


async def read_shape(url: str, schema: str) -> dict:
    engine = create_async_engine(url)

    async with engine.connect() as connection:
        shape = {name: {tuple(row) for row in (await connection.execute(text(query), {"schema": schema})).all()} for name, query in (("tables", TABLES), ("columns", COLUMNS), ("indexes", INDEXES), ("keys", KEYS))}

    await engine.dispose()

    return shape


def difference(fresh: dict, current: dict) -> dict:
    return {name: {"missing": sorted(fresh[name] - current[name]), "extra": sorted(current[name] - fresh[name])} for name in fresh}


def filling(column) -> str | None:
    """The value the rows already there receive, which is the one the application would have written."""
    default = column.default

    if default is None or not default.is_scalar:
        return None

    value = default.arg

    if isinstance(value, bool):
        return str(int(value))

    if isinstance(value, (int, float)):
        return str(value)

    return f"'{getattr(value, 'value', value)}'"


def adding(dialect, table, column) -> list[str]:
    """A mandatory column arriving on a table that already has rows fills them, and MySQL filling it with an empty string writes a value no enum has."""
    declaration = dialect.ddl_compiler(dialect, None).get_column_specification(column)

    if column.nullable:
        return [f"ALTER TABLE {table.name} ADD COLUMN {declaration};"]

    value = filling(column)

    if value is None:
        return [f"-- a human decides: {table.name}.{column.name} is required and has no default, so somebody says what the rows of today hold", f"-- ALTER TABLE {table.name} ADD COLUMN {declaration} DEFAULT <value>;", f"-- ALTER TABLE {table.name} ALTER COLUMN {column.name} DROP DEFAULT;"]

    # The default leaves once it has filled, because a schema built from scratch carries none.
    return [f"ALTER TABLE {table.name} ADD COLUMN {declaration} DEFAULT {value};", f"ALTER TABLE {table.name} ALTER COLUMN {column.name} DROP DEFAULT;"]


def reshaped(shapes: dict) -> set:
    """An index that kept its name and changed its columns is one thing changing, and creating it before dropping it collides."""
    return {(row[0], row[1]) for row in shapes["indexes"]["missing"]} & {(row[0], row[1]) for row in shapes["indexes"]["extra"]}


def statements_for(shapes: dict) -> list[str]:
    """The ddl is compiled from the metadata in the dialect of the target, and never written from memory."""
    dialect = mysql.dialect()
    tables = {row[0] for row in shapes["tables"]["missing"]}
    columns = [row for row in shapes["columns"]["missing"] if row[0] not in tables]
    indexes = {(row[0], row[1]) for row in shapes["indexes"]["missing"] if row[0] not in tables}
    keys = {(row[0], row[1]) for row in shapes["keys"]["missing"] if row[0] not in tables}
    mutated = reshaped(shapes)
    lines = []

    # Read from the same list the application creates, or a table it owns elsewhere is one the report misses and nothing proposes.
    for table in [table for metadata in SCHEMAS for table in metadata.sorted_tables]:
        if table.name in tables:
            lines.append(f"{str(CreateTable(table).compile(dialect=dialect)).strip()};")

            # A table arrives with its primary key and its uniques inlined and with nothing else, so without this it arrives without the indexes that answer the queries it exists for.
            lines.extend(f"{str(CreateIndex(index).compile(dialect=dialect)).strip()};" for index in sorted(table.indexes, key=lambda index: index.name))

            continue

        pending = set()

        for name in [column_name for table_name, column_name, *_ in columns if table_name == table.name and column_name in table.columns]:
            written = adding(dialect, table, table.columns[name])
            pending |= {name} if written[0].startswith("--") else set()
            lines.extend(written)

        # An index over a column somebody still has to decide about cannot run, and MySQL stops at the first statement that cannot.
        for index in [index for index in table.indexes if (table.name, index.name) in indexes]:
            if {column.name for column in index.columns} & pending:
                lines.append(f"-- waits on the decision above: CREATE INDEX {index.name} ON {table.name}")

                continue

            if (table.name, index.name) in mutated:
                lines.append(f"DROP INDEX {index.name} ON {table.name};")

            lines.append(f"{str(CreateIndex(index).compile(dialect=dialect)).strip()};")

        # A uniqueness the model declares as a constraint is an index to the database, and only the model calls it something else.
        for unique in [constraint for constraint in table.constraints if isinstance(constraint, UniqueConstraint) and (table.name, constraint.name) in indexes]:
            if {column.name for column in unique.columns} & pending:
                lines.append(f"-- waits on the decision above: UNIQUE {unique.name} on {table.name}")

                continue

            lines.append(f"{str(AddConstraint(unique).compile(dialect=dialect)).strip()};")

        for constraint in [constraint for constraint in table.foreign_key_constraints if any((table.name, column.name) in keys for column in constraint.columns)]:
            if {column.name for column in constraint.columns} & pending:
                lines.append(f"-- waits on the decision above: FOREIGN KEY {', '.join(column.name for column in constraint.columns)} on {table.name}")

                continue

            lines.append(f"{str(AddConstraint(constraint).compile(dialect=dialect)).strip()};")

    return lines


def report(shapes: dict) -> None:
    titles = {"tables": "TABLES", "columns": "COLUMNS", "indexes": "INDEXES", "keys": "FOREIGN KEYS"}

    for name, title in titles.items():
        missing, extra = shapes[name]["missing"], shapes[name]["extra"]

        print(f"\n{title}: {len(missing)} to create, {len(extra)} to remove")

        for row in missing:
            print(f"   MISSING {' | '.join(str(part) for part in row)}")

        for row in extra:
            print(f"   EXTRA   {' | '.join(str(part) for part in row)}")


def restore(path: pathlib.Path) -> None:
    """A dump somebody took on the server is the same shape as a connection to it, without needing to reach the server."""
    docker("exec", CONTAINER, "mysql", "-uroot", "-pschema", "-e", f"DROP DATABASE IF EXISTS {CURRENT}; CREATE DATABASE {CURRENT};")

    done = subprocess.run(["docker", "exec", "-i", CONTAINER, "mysql", "-uroot", "-pschema", CURRENT], input=path.read_text(), capture_output=True, text=True)

    if done.returncode != 0:
        raise RuntimeError(f"the dump was refused: {done.stderr.strip().splitlines()[-1] if done.stderr else 'no reason given'}")


def run_command(current_file: str | None = None) -> int:
    where = target()

    if current_file is None and where["host"] is None:
        print("this configuration does not point at a server, so there is nothing to compare")

        return 1

    compared = current_file or f"{where['user']}@{where['host']}:{where['port']}/{where['name']}"

    print(f"comparing {compared} against the schema of the code")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    port = start_container()

    try:
        asyncio.run(build_fresh(port))
        dump({"host": "container", "port": 3306, "user": "root", "password": "schema"}, FRESH, OUTPUT / "schema-from-scratch.sql")

        if current_file is None:
            dump(where, where["name"], OUTPUT / "schema-in-place.sql")
            current = asyncio.run(read_shape(settings.database.url, where["name"]))
        else:
            restore(pathlib.Path(current_file))
            current = asyncio.run(read_shape(f"mysql+aiomysql://root:schema@127.0.0.1:{port}/{CURRENT}", CURRENT))

        fresh = asyncio.run(read_shape(f"mysql+aiomysql://root:schema@127.0.0.1:{port}/{FRESH}", FRESH))
    finally:
        docker("rm", "-f", CONTAINER, check=False)

    shapes = difference(fresh, current)
    report(shapes)

    proposed = statements_for(shapes)

    # A removal loses data and a rename reads as one removal plus one addition, so neither is ever proposed.
    mutated = reshaped(shapes)
    warnings = [f"-- a human decides: {' | '.join(str(part) for part in row)}" for name in ("columns", "indexes", "keys") for row in shapes[name]["extra"] if (row[0], row[1]) not in mutated]

    (OUTPUT / "proposal.sql").write_text("\n".join([*proposed, "", *warnings]) + "\n")

    print(f"\nwritten in {OUTPUT}/: schema-from-scratch.sql, schema-in-place.sql, proposal.sql")
    print(f"the proposal covers {len(proposed)} creation(s), and what the database has over is listed as a decision and never generated")

    return 0
