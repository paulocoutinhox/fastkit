from config.image_settings import ImageSettings
from config.upload_settings import UploadSettings
from enums.naming import Naming
from enums.upload_purpose import UploadPurpose

MEGABYTE = 1024 * 1024


# SVG is left out on purpose: it carries markup, and an editor renders whatever it carries.
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


DOCUMENT_EXTENSIONS = frozenset({".pdf", ".epub", ".zip", ".mp3", ".mp4"})


class UploadHelper:
    @staticmethod
    def image_upload(folder: str, max_bytes: int, image: ImageSettings) -> UploadSettings:
        return UploadSettings(folder=folder, extensions=IMAGE_EXTENSIONS, max_bytes=max_bytes, image=image)

    @staticmethod
    def default_uploads() -> dict[UploadPurpose, UploadSettings]:
        return {
            UploadPurpose.IMAGE: UploadHelper.image_upload("images/content", 10 * MEGABYTE, ImageSettings(width=1600, image_format="webp", quality=82)),
            UploadPurpose.AVATAR: UploadHelper.image_upload("images/user/avatar", 5 * MEGABYTE, ImageSettings(width=256, height=256, crop=True, image_format="webp", quality=85)),
            UploadPurpose.BANNER: UploadHelper.image_upload("images/banner", 10 * MEGABYTE, ImageSettings(width=1920, height=1080, crop=True, image_format="webp", quality=82)),
            UploadPurpose.GALLERY_PHOTO: UploadHelper.image_upload("images/gallery", 10 * MEGABYTE, ImageSettings(width=1600, height=900, crop=True, image_format="webp", quality=82)),
            UploadPurpose.PRODUCT_IMAGE: UploadHelper.image_upload("images/product", 10 * MEGABYTE, ImageSettings(width=1280, height=720, crop=True, image_format="webp", quality=85)),
            UploadPurpose.PLAN_IMAGE: UploadHelper.image_upload("images/plan", 10 * MEGABYTE, ImageSettings(width=1280, height=720, crop=True, image_format="webp", quality=85)),
            UploadPurpose.PRODUCT_FILE: UploadSettings(folder="files/product", extensions=DOCUMENT_EXTENSIONS, max_bytes=512 * MEGABYTE, naming=Naming.ORIGINAL),
        }
