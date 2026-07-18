from pydantic import BaseModel


class TranslationEntry(BaseModel):
    language: str
    title: str | None = None
    summary: str | None = None
    body: str | None = None
