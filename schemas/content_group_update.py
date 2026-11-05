from schemas.common import as_optional
from schemas.content_group_create import ContentGroupCreate

ContentGroupUpdate = as_optional("ContentGroupUpdate", ContentGroupCreate)
