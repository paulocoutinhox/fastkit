from fastkit_admin.fields.base import AdminField


class RelationField(AdminField):
    """Select whose options are records of another table.

    Options are resolved server-side by the owning resource's ``options_<name>``
    handler, which builds each option label however it wants. When ``depends_on``
    is set, the field is a dependent select: its options are filtered by the current
    values of the listed parent fields, and it resets whenever a parent changes.
    """

    field_type = "relation"

    def __init__(
        self,
        *args,
        depends_on: list[str] | None = None,
        related: str | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.depends_on = list(depends_on or [])
        self.related = related

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["depends_on"] = self.depends_on
        schema["related"] = self.related

        return schema

    def parse_value(self, raw, locale: str = "en"):
        if raw is None or raw == "":
            return None

        try:
            return int(raw)
        except (TypeError, ValueError) as error:
            raise self._fail("validation.integer-invalid") from error
