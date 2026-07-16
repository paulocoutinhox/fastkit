# fastkit-db

Async SQLAlchemy 2 foundation for FastKit: engine and session management,
portable column types, reusable model mixins, a generic repository, an explicit
transaction boundary, a Unit of Work and a dialect capability matrix.

## Installation

```bash
pip install fastkit-db
pip install "fastkit-db[postgresql]"
pip install "fastkit-db[mysql]"
```

## Database

```python
from fastkit_db.engine import Database
from fastkit_db.base import Base

database = Database(url="sqlite+aiosqlite:///./data/app.db")
await database.create_all(Base.metadata)
```

`database.capabilities` returns a `DatabaseCapabilities` snapshot for the active
dialect (SQLite, PostgreSQL, MySQL/MariaDB, or a conservative generic default).

## Models and mixins

`Base` uses a stable naming convention. Opt-in mixins: `PrimaryKeyMixin`,
`TimestampMixin`, `TenantMixin`, `SoftDeleteMixin` (opt-in, never global),
`VersionMixin`, `MetadataMixin`, `CreatedByMixin`, `UpdatedByMixin`,
`ActiveFlagMixin`.

`PrimaryKeyMixin` gives every model an autoincrementing `bigint` primary key
(`BigInteger` on server engines, `Integer` on SQLite, which only autoincrements
`INTEGER PRIMARY KEY`). Foreign keys reference it with `BigInteger`.

Portable types: `GUID` (application-generated UUID stored as hex) and
`PortableJSON` (JSON stored as text).

## Repository and transactions

```python
from fastkit_db.repository import Repository
from fastkit_db.session import transaction

repo = Repository(User, session)

async with transaction(session):
    await repo.add(User(...))
```

`UnitOfWork` provides a commit/rollback boundary with explicit after-commit
hooks (sync or async).

## Testing

100% branch coverage.

```bash
pytest packages/fastkit-db --cov=fastkit_db --cov-branch
```
