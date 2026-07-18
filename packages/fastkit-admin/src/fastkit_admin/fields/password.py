from fastkit_admin.fields.base import AdminField


class PasswordField(AdminField):
    field_type = "password"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("write_only", True)
        super().__init__(*args, **kwargs)
