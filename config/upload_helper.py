from config.image_settings import ImageSettings
from config.upload_settings import UploadSettings
from enums.naming import Naming
from enums.upload_purpose import UploadPurpose

MEGABYTE = 1024 * 1024


# What a purpose accepts, with the type each extension is served as, declared here because the table of the machine differs from one image to the next and a slim one names nothing for `.epub`.
# SVG is left out on purpose: it carries markup, and an editor renders whatever it carries.
IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}


DOCUMENT_TYPES = {".pdf": "application/pdf", ".epub": "application/epub+zip", ".zip": "application/zip", ".mp3": "audio/mpeg", ".mp4": "video/mp4"}


class UploadHelper:
    @staticmethod
    def image_upload(folder: str, max_bytes: int, image: ImageSettings) -> UploadSettings:
        return UploadSettings(folder=folder, extensions=IMAGE_TYPES, max_bytes=max_bytes, image=image)

    @staticmethod
    def default_uploads() -> dict[UploadPurpose, UploadSettings]:
        return {
            UploadPurpose.IMAGE: UploadHelper.image_upload("images/content", 10 * MEGABYTE, ImageSettings(width=1600, image_format="webp", quality=82)),
            UploadPurpose.AVATAR: UploadHelper.image_upload("images/user/avatar", 5 * MEGABYTE, ImageSettings(width=256, height=256, crop=True, image_format="webp", quality=85)),
            UploadPurpose.BANNER: UploadHelper.image_upload("images/banner", 10 * MEGABYTE, ImageSettings(width=1920, height=1080, crop=True, image_format="webp", quality=82)),
            UploadPurpose.GALLERY_PHOTO: UploadHelper.image_upload("images/gallery", 10 * MEGABYTE, ImageSettings(width=1600, height=900, crop=True, image_format="webp", quality=82)),
            UploadPurpose.PRODUCT_IMAGE: UploadHelper.image_upload("images/product", 10 * MEGABYTE, ImageSettings(width=1280, height=720, crop=True, image_format="webp", quality=85)),
            UploadPurpose.PLAN_IMAGE: UploadHelper.image_upload("images/plan", 10 * MEGABYTE, ImageSettings(width=1280, height=720, crop=True, image_format="webp", quality=85)),
            UploadPurpose.PRODUCT_FILE: UploadSettings(folder="files/product", extensions=DOCUMENT_TYPES, max_bytes=512 * MEGABYTE, naming=Naming.ORIGINAL),
        }
