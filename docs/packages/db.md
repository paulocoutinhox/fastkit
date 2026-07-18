# fastkit-db

Async SQLAlchemy 2 engine, session factory, repository, unit of work, dialect capabilities, base +
mixins.

Full detail: [Database](../data/database.md), [Models and mixins](../data/models-and-mixins.md),
[Conventions](../data/conventions.md).

## Highlights

- Engine with `pool_pre_ping` + `pool_recycle`.
- `database.session_factory()` async sessions.
- `Base` + mixins (`PrimaryKeyMixin`, `TimestampMixin`, `TenantMixin`, `SoftDeleteMixin`,
  `VersionMixin`, `MetadataMixin`, `CreatedByMixin`/`UpdatedByMixin`, `ActiveFlagMixin`).
- `UnitOfWork` with after-commit hooks (always cleared in `finally`).
- SQLite enforces FKs (`PRAGMA foreign_keys=ON`); functional unique indexes over
  `coalesce(tenant_id, 0)` for global-tenant-safe uniqueness.

## App

`DbApp` (`fastkit.db`) registers the `database` component and creates tables for every registered
model.
