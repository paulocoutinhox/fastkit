from schemas.common import as_optional
from schemas.product_create import ProductCreate

ProductUpdate = as_optional("ProductUpdate", ProductCreate)
