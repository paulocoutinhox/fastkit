from schemas.common import as_optional
from schemas.gallery_photo_create import GalleryPhotoCreate

GalleryPhotoUpdate = as_optional("GalleryPhotoUpdate", GalleryPhotoCreate)
