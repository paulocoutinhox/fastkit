import re

from fastkit_admin.resource import GridQuery

_FILTER_KEY = re.compile(
    r"^filter\[(?P<field>[a-zA-Z0-9_]+)\](?:\[(?P<part>from|to)\])?$"
)


def parse_grid_query(params) -> GridQuery:
    """Build a GridQuery from request query parameters, supporting range filters."""

    filters: dict = {}

    for key, value in params.multi_items():
        match = _FILTER_KEY.match(key)

        if match is None:
            continue

        field = match.group("field")
        part = match.group("part")

        if part is None:
            filters[field] = value
        else:
            bucket = filters.get(field)

            if not isinstance(bucket, dict):
                bucket = filters[field] = {}

            bucket[part] = value

    return GridQuery(
        page=_to_int(params.get("page"), 1),
        page_size=_to_int(params.get("page_size"), 25),
        search=params.get("search") or None,
        sort=params.get("sort") or None,
        filters=filters,
    )


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
