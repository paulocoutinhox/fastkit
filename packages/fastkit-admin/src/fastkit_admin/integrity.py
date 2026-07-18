from sqlalchemy import UniqueConstraint

from fastkit_db.integrity import IntegrityViolation


def _attribute_columns(model: type, attribute_name: str) -> list[str]:
    attribute = getattr(model, attribute_name, None)
    property_ = getattr(attribute, "property", None)

    return [column.name for column in getattr(property_, "columns", ())]


def _column_field_map(model: type, field_names: list[str]) -> dict[str, str]:
    result = {field_name: field_name for field_name in field_names}

    for field_name in field_names:
        for column_name in _attribute_columns(model, field_name):
            result[column_name] = field_name

    return result


def _constraint_columns(table, constraint_name: str | None) -> list[str]:
    if not constraint_name:
        return []

    for constraint in table.constraints:
        if constraint.name == constraint_name:
            return [column.name for column in constraint.columns]

    for index in table.indexes:
        if index.name == constraint_name:
            return [column.name for column in index.columns]

    if constraint_name in table.columns:
        return [constraint_name]

    return []


def integrity_fields(
    model: type, field_names: list[str], violation: IntegrityViolation
) -> list[str]:
    table = getattr(model, "__table__", None)

    if table is None:
        return []

    column_names = violation.columns or _constraint_columns(table, violation.constraint)

    if not column_names and violation.kind == "foreign_key":
        column_names = [foreign_key.parent.name for foreign_key in table.foreign_keys]

    field_map = _column_field_map(model, field_names)

    return list(
        dict.fromkeys(
            field_map[column_name]
            for column_name in column_names
            if column_name in field_map
        )
    )


def unique_field_groups(
    model: type, field_names: list[str], excluded_attributes: list[str]
) -> list[list[str]]:
    table = getattr(model, "__table__", None)

    if table is None:
        return []

    field_map = _column_field_map(model, field_names)
    excluded_columns = {
        column
        for attribute in excluded_attributes
        for column in _attribute_columns(model, attribute)
    }
    groups = []

    candidates = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    candidates.extend(index for index in table.indexes if index.unique)

    for candidate in candidates:
        columns = [column.name for column in candidate.columns]

        if not columns or any(
            column not in field_map and column not in excluded_columns
            for column in columns
        ):
            continue

        group = list(
            dict.fromkeys(
                field_map[column] for column in columns if column in field_map
            )
        )

        if group and group not in groups:
            groups.append(group)

    return groups
