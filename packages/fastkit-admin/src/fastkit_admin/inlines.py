from sqlalchemy import select


class InlineResource:
    """A repeatable child sub-form rendered inside a parent resource's form.

    The parent form serializes each inline's rows into a nested payload
    (`{<inline_name>: [{...}, ...]}`) and the parent resource persists them in the same
    transaction: rows carrying a persisted `pk_field` are updated, new rows are inserted and
    rows no longer present are deleted (an id-diff formset, so child references survive an edit).
    """

    def __init__(self, name: str, form_fields: list, model: type, fk_field: str, label: str | None = None, min_items: int = 0, max_items: int | None = None, pk_field: str = "id"):
        self.name = name
        self.form_fields = form_fields
        self.model = model
        self.fk_field = fk_field
        self.label = label or name.replace("_", " ").title()
        self.min_items = min_items
        self.max_items = max_items
        self.pk_field = pk_field

    def schema(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "fields": [field.to_schema() for field in self.form_fields],
            "min_items": self.min_items,
            "max_items": self.max_items,
        }

    def serialize(self, child, locale: str) -> dict:
        data = {self.pk_field: str(getattr(child, self.pk_field))}

        for admin_field in self.form_fields:
            data[admin_field.name] = admin_field.format_value(getattr(child, admin_field.name, None), locale)

        return data

    async def load(self, session, parent_id, locale: str) -> list[dict]:
        column = getattr(self.model, self.fk_field)
        pk = getattr(self.model, self.pk_field)
        children = (await session.execute(select(self.model).where(column == parent_id).order_by(pk))).scalars().all()

        return [self.serialize(child, locale) for child in children]

    async def save(self, session, parent_id, rows: list, locale: str) -> None:
        column = getattr(self.model, self.fk_field)
        existing = {getattr(child, self.pk_field): child for child in (await session.execute(select(self.model).where(column == parent_id))).scalars()}
        seen = set()

        for item in rows:
            child = existing.get(_match(item.get(self.pk_field)))

            if child is None:
                child = self.model(**{self.fk_field: parent_id})
                session.add(child)
            else:
                seen.add(getattr(child, self.pk_field))

            for admin_field in self.form_fields:
                if admin_field.virtual or admin_field.readonly:
                    continue

                value = admin_field.parse_value(item.get(admin_field.name), locale)
                admin_field.validate(value)
                setattr(child, admin_field.name, value)

        for child_id, child in existing.items():
            if child_id not in seen:
                await session.delete(child)

        await session.flush()


def _match(raw):
    if isinstance(raw, str) and raw.lstrip("-").isdigit():
        return int(raw)

    return raw
