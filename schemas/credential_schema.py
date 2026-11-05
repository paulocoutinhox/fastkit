from schemas.base_schema import BaseSchema


class CredentialSchema(BaseSchema):
    field: str
    label: str
    hint: str
