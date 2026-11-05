from schemas.common import as_optional
from schemas.external_product_create import ExternalProductCreate

ExternalProductUpdate = as_optional("ExternalProductUpdate", ExternalProductCreate)
