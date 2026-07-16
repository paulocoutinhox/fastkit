from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseCapabilities:
    supports_returning: bool
    supports_skip_locked: bool
    supports_native_json: bool
    supports_native_uuid: bool
    supports_partial_indexes: bool
    supports_advisory_locks: bool
    supports_deferrable_constraints: bool
    supports_select_for_update: bool


GENERIC = DatabaseCapabilities(
    supports_returning=False,
    supports_skip_locked=False,
    supports_native_json=False,
    supports_native_uuid=False,
    supports_partial_indexes=False,
    supports_advisory_locks=False,
    supports_deferrable_constraints=False,
    supports_select_for_update=False,
)

SQLITE = DatabaseCapabilities(
    supports_returning=True,
    supports_skip_locked=False,
    supports_native_json=True,
    supports_native_uuid=False,
    supports_partial_indexes=True,
    supports_advisory_locks=False,
    supports_deferrable_constraints=True,
    supports_select_for_update=False,
)

POSTGRESQL = DatabaseCapabilities(
    supports_returning=True,
    supports_skip_locked=True,
    supports_native_json=True,
    supports_native_uuid=True,
    supports_partial_indexes=True,
    supports_advisory_locks=True,
    supports_deferrable_constraints=True,
    supports_select_for_update=True,
)

MYSQL = DatabaseCapabilities(
    supports_returning=False,
    supports_skip_locked=True,
    supports_native_json=True,
    supports_native_uuid=False,
    supports_partial_indexes=False,
    supports_advisory_locks=True,
    supports_deferrable_constraints=False,
    supports_select_for_update=True,
)

_BY_DIALECT = {"sqlite": SQLITE, "postgresql": POSTGRESQL, "mysql": MYSQL, "mariadb": MYSQL}


def capabilities_for(dialect_name: str) -> DatabaseCapabilities:
    return _BY_DIALECT.get(dialect_name, GENERIC)
