from sqlalchemy import select

from fastkit_core.errors.exceptions import FieldError, ValidationError


class InlineResource:
    """A repeatable child sub-form rendered inside a parent resource's form.

    The parent form serializes each inline's rows into a nested payload
    (`{<inline_name>: [{...}, ...]}`) and the parent resource persists them in the same
    transaction: rows carrying a persisted `pk_field` are updated, new rows are inserted and
    rows no longer present are deleted (an id-diff formset, so child references survive an edit).
    """

    def __init__(
        self,
        name: str,
        form_fields: list,
        model: type,
        fk_field: str,
        label: str | None = None,
        min_items: int = 0,
        max_items: int | None = None,
        pk_field: str = "id",
        unique_fields: list[str] | None = None,
    ):
        self.name = name
        self.form_fields = form_fields
        self.model = model
        self.fk_field = fk_field
        self.label = label or name.replace("_", " ").title()
        self.min_items = min_items
        self.max_items = max_items
        self.pk_field = pk_field
        self.unique_fields = list(unique_fields or [])

    def schema(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "fields": [field.to_schema() for field in self.form_fields],
            "min_items": self.min_items,
            "max_items": self.max_items,
        }

    def serialize(self, child, locale: str) -> dict:
        data = {"id": str(getattr(child, self.pk_field))}

        for admin_field in self.form_fields:
            data[admin_field.name] = admin_field.format_value(
                getattr(child, admin_field.name, None), locale
            )

        return data

    async def load(self, session, parent_id, locale: str) -> list[dict]:
        column = getattr(self.model, self.fk_field)
        pk = getattr(self.model, self.pk_field)
        children = (
            (
                await session.execute(
                    select(self.model).where(column == parent_id).order_by(pk)
                )
            )
            .scalars()
            .all()
        )

        return [self.serialize(child, locale) for child in children]

    def validate(self, rows: list, locale: str, errors: list) -> list | None:
        if not all(isinstance(item, dict) for item in rows):
            return None

        parsed = []

        for index, item in enumerate(rows):
            values = {}

            for admin_field in self.form_fields:
                if admin_field.virtual or admin_field.readonly:
                    continue

                try:
                    value = admin_field.parse_value(item.get(admin_field.name), locale)
                    admin_field.validate(value)
                except ValidationError as error:
                    for field_error in error.field_errors:
                        field_error.path = [self.name, index, admin_field.name]
                        errors.append(field_error)
                    continue

                values[admin_field.name] = value

            parsed.append((item.get("id"), values))

        self._flag_duplicates(parsed, errors)

        return parsed

    def _flag_duplicates(self, parsed: list, errors: list) -> None:
        if not self.unique_fields:
            return

        seen = set()

        for index, (_, values) in enumerate(parsed):
            key = tuple(values.get(name) for name in self.unique_fields)

            if any(part is None for part in key):
                continue

            if key in seen:
                for name in self.unique_fields:
                    errors.append(
                        FieldError(
                            name, "validation.unique", path=[self.name, index, name]
                        )
                    )
            else:
                seen.add(key)

    async def persist(self, session, parent_id, parsed: list) -> None:
        column = getattr(self.model, self.fk_field)
        existing = {
            getattr(child, self.pk_field): child
            for child in (
                await session.execute(select(self.model).where(column == parent_id))
            ).scalars()
        }
        seen = set()

        for raw_id, values in parsed:
            child = existing.get(_match(raw_id))

            if child is None:
                child = self.model(**{self.fk_field: parent_id})
                session.add(child)
            else:
                seen.add(getattr(child, self.pk_field))

            for name, value in values.items():
                setattr(child, name, value)

        for child_id, child in existing.items():
            if child_id not in seen:
                await session.delete(child)

        await session.flush()


def _match(raw):
    if isinstance(raw, str) and raw.lstrip("-").isdigit():
        return int(raw)

    return raw
