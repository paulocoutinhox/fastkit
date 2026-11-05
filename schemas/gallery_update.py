from schemas.common import as_optional
from schemas.gallery_create import GalleryCreate

GalleryUpdate = as_optional("GalleryUpdate", GalleryCreate)
