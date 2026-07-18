from fastkit_admin.fields.base import AdminField


class PermissionMatrixField(AdminField):
    """Virtual field rendering permissions grouped by permission group as checkboxes.

    It is not persisted to the model. The frontend loads the grouped catalog and the
    current selection from the given endpoints and saves through ``save_url``.
    """

    field_type = "permission_matrix"

    def __init__(self, *args, groups_url: str, value_url: str, save_url: str, **kwargs):
        kwargs.setdefault("virtual", True)
        super().__init__(*args, **kwargs)
        self.groups_url = groups_url
        self.value_url = value_url
        self.save_url = save_url

    def to_schema(self) -> dict:
        schema = super().to_schema()
        schema["groups_url"] = self.groups_url
        schema["value_url"] = self.value_url
        schema["save_url"] = self.save_url

        return schema
