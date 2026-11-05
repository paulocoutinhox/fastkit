from schemas.common import as_optional
from schemas.content_category_create import ContentCategoryCreate

ContentCategoryUpdate = as_optional("ContentCategoryUpdate", ContentCategoryCreate)
