from fastkit_db.capabilities import DatabaseCapabilities, capabilities_for

_URL_PREFIXES = {
    "sqlite": "sqlite",
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "mysql": "mysql",
    "mariadb": "mariadb",
}


def dialect_name_from_url(url: str) -> str:
    scheme = url.split(":", 1)[0].split("+", 1)[0].lower()

    return _URL_PREFIXES.get(scheme, "generic")


def capabilities_from_url(url: str) -> DatabaseCapabilities:
    return capabilities_for(dialect_name_from_url(url))
