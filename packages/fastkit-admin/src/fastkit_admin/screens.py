def _field_with_value(field: dict, value) -> dict:
    item = dict(field)
    item["value"] = value

    return item


def form_context(schema: dict, values: dict | None, label: str, mode: str, path: str, resource: str, record_id=None, inline_data: dict | None = None) -> dict:
    fieldsets = []

    for fieldset in schema["fieldsets"]:
        fields = [_field_with_value(field, (values or {}).get(field["name"]) if values else field.get("default")) for field in fieldset["fields"]]

        if fields:
            fieldsets.append({"title": fieldset["title"], "description": fieldset["description"], "fields": fields})

    inlines = []

    for inline in schema.get("inlines", []):
        rows = [[_field_with_value(field, row.get(field["name"])) for field in inline["fields"]] for row in (inline_data or {}).get(inline["name"], [])]
        inlines.append({
            "name": inline["name"],
            "label": inline["label"],
            "fields": inline["fields"],
            "min_items": inline["min_items"],
            "max_items": inline["max_items"],
            "rows": rows,
        })

    return {
        "resource": resource,
        "label": label,
        "mode": mode,
        "record_id": record_id,
        "path": path,
        "base_url": f"{path}/{resource}",
        "fieldsets": fieldsets,
        "inlines": inlines,
    }


def profile_context(profile: dict, path: str, api_path: str) -> dict:
    return {
        "path": path,
        "api_path": api_path,
        "email": profile.get("email") or "",
        "display_name": profile.get("display_name") or "",
        "first_name": profile.get("first_name") or "",
        "last_name": profile.get("last_name") or "",
        "avatar_url": profile.get("avatar_url"),
        "initials": (profile.get("display_name") or profile.get("email") or "?")[:2].upper(),
        "identifiers": profile.get("identifiers", []),
        "identifier_types": profile.get("identifier_types", []),
    }


def report_context(report: dict, name: str, path: str, api_path: str, query: str = "") -> dict:
    filters = [dict(item) for item in report.get("filters", [])]

    return {
        "name": name,
        "title": report["title"],
        "path": path,
        "api_path": api_path,
        "base_url": f"{path}/reports/{name}",
        "columns": report["columns"],
        "rows": report["rows"],
        "formats": report["formats"],
        "filters": filters,
        "filter_groups": _filter_groups(filters, []),
        "has_filters": bool(filters),
        "query": query,
    }


def detail_context(schema: dict, data: dict, label: str, path: str, resource: str, record_id, flags: dict) -> dict:
    html = data.get("_html", {})
    fieldsets = []

    for fieldset in schema["fieldsets"]:
        fields = []

        for field in fieldset["fields"]:
            item = dict(field)
            item["value"] = data.get(field["name"])
            item["html"] = html.get(field["name"])
            fields.append(item)

        if fields:
            fieldsets.append({"title": fieldset["title"], "description": fieldset["description"], "fields": fields})

    return {
        "resource": resource,
        "label": label,
        "display": data.get("_display"),
        "record_id": record_id,
        "path": path,
        "base_url": f"{path}/{resource}",
        "fieldsets": fieldsets,
        "flags": flags,
    }


def _page_window(page: int, total_pages: int, span: int = 2) -> list[int]:
    low = max(1, page - span)
    high = min(total_pages, page + span)

    return list(range(low, high + 1))


def _filter_groups(filters: list, fieldsets: list) -> list:
    by_field = {item["field"]: item for item in filters}
    groups = []
    used = set()

    for fieldset in fieldsets:
        members = [by_field[name] for name in fieldset["fields"] if name in by_field]
        used.update(fieldset["fields"])

        if members:
            groups.append({"title": fieldset["title"], "filters": members})

    remaining = [item for item in filters if item["field"] not in used]

    if remaining:
        groups.insert(0, {"title": None, "filters": remaining})

    return groups


def list_context(schema: dict, result: dict, path: str, search: str | None, sort: str | None, applied_filters: dict | None = None) -> dict:
    applied = applied_filters or {}
    filters = []

    for item in schema["filters"]:
        entry = dict(item)
        value = applied.get(item["field"])

        if item["type"] == "date_range":
            entry["value_from"] = value.get("from") if isinstance(value, dict) else None
            entry["value_to"] = value.get("to") if isinstance(value, dict) else None
        else:
            entry["value"] = value if not isinstance(value, dict) else None

        filters.append(entry)

    default_sort = schema["default_sort"]
    active = sort or (default_sort[0] if default_sort else "")
    active_name = active[1:] if active.startswith("-") else active
    active_desc = active.startswith("-")

    columns = []

    for column in schema["columns"]:
        item = dict(column)

        if column["sortable"]:
            is_active = column["name"] == active_name
            item["sort_active"] = is_active
            item["sort_desc"] = is_active and active_desc
            item["sort_value"] = f"-{column['name']}" if is_active and not active_desc else column["name"]

        columns.append(item)

    bulk_actions = [action for action in schema["actions"] if action.get("scope") == "bulk"]
    collection_actions = [action for action in schema["actions"] if action.get("scope") == "collection"]
    has_bulk = bool(bulk_actions) or schema["flags"].get("can_delete", False)
    pagination = result["pagination"]
    count = len(result["rows"])
    first = (pagination["page"] - 1) * pagination["page_size"] + 1 if count else 0

    return {
        "resource": schema["resource"],
        "label": schema["label"],
        "columns": columns,
        "rows": result["rows"],
        "pagination": pagination,
        "page_numbers": _page_window(pagination["page"], pagination["total_pages"]),
        "flags": schema["flags"],
        "bulk_actions": bulk_actions,
        "collection_actions": collection_actions,
        "search_fields": schema["search_fields"],
        "search": search or "",
        "sort": active,
        "path": path,
        "base_url": f"{path}/{schema['resource']}",
        "has_bulk": has_bulk,
        "showing_from": first,
        "showing_to": first + count - 1 if count else 0,
        "showing_total": pagination["total_items"],
        "filters": filters,
        "filter_groups": _filter_groups(filters, schema["filter_fieldsets"]),
        "has_filters": bool(filters),
    }
