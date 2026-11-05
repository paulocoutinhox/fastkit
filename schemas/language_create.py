from schemas.base_schema import BaseSchema
from schemas.common import Text


class LanguageCreate(BaseSchema):
    name: Text(255)
    native_name: Text(255)
    code_iso_639_1: Text(8)
    code_iso_language: Text(16)
    active: bool = True
