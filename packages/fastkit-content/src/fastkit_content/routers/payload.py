from pydantic import BaseModel

from fastkit_content.routers.entry import TranslationEntry


class TranslationsPayload(BaseModel):
    translations: list[TranslationEntry]
