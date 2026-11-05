from schemas.banner_create import BannerCreate
from schemas.common import as_optional

BannerUpdate = as_optional("BannerUpdate", BannerCreate)
