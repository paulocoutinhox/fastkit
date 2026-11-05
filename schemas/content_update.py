from schemas.common import as_optional
from schemas.content_create import ContentCreate

ContentUpdate = as_optional("ContentUpdate", ContentCreate)
