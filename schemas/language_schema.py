from schemas.timestamp_schema import TimestampSchema


class LanguageSchema(TimestampSchema):
    id: int
    name: str
    native_name: str
    code_iso_639_1: str
    code_iso_language: str
    active: bool
