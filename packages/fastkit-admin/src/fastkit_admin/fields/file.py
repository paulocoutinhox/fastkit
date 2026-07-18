from fastkit_admin.fields.base import AdminField


class FileField(AdminField):
    field_type = "file"

    def __init__(self, *args, upload_url: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.upload_url = upload_url

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["upload_url"] = self.upload_url

        return schema
