from fastkit_admin.fields.base import AdminField


class TranslationsField(AdminField):
    """Virtual field editing a record's per-language content (title/body).

    The frontend loads the active languages and the current translations from the
    given URLs and saves them through ``save_url``. Not persisted as a model column.
    """

    field_type = "translations"

    def __init__(
        self, *args, languages_url: str, value_url: str, save_url: str, **kwargs
    ):
        kwargs.setdefault("virtual", True)
        super().__init__(*args, **kwargs)
        self.languages_url = languages_url
        self.value_url = value_url
        self.save_url = save_url

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["languages_url"] = self.languages_url
        schema["value_url"] = self.value_url
        schema["save_url"] = self.save_url

        return schema
