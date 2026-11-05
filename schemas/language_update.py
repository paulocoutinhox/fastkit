from schemas.common import as_optional
from schemas.language_create import LanguageCreate

LanguageUpdate = as_optional("LanguageUpdate", LanguageCreate)
