from schemas.base_schema import BaseSchema


class LanguageReference(BaseSchema):
    id: int
    name: str
    code_iso_639_1: str
