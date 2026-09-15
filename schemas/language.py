from schemas.common import BaseSchema, Text, TimestampSchema, as_optional


class LanguageReference(BaseSchema):
    id: int
    name: str
    code_iso_639_1: str


class LanguageSchema(TimestampSchema):
    id: int
    name: str
    native_name: str
    code_iso_639_1: str
    code_iso_language: str
    active: bool


class LanguageCreate(BaseSchema):
    name: Text(255)
    native_name: Text(255)
    code_iso_639_1: Text(8)
    code_iso_language: Text(16)
    active: bool = True


LanguageUpdate = as_optional("LanguageUpdate", LanguageCreate)
