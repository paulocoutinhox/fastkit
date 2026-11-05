from enum import StrEnum


class UploadPurpose(StrEnum):
    """What a file is being stored for, which is what decides the folder, the limits and what the bytes become."""

    IMAGE = "image"
    AVATAR = "avatar"
    BANNER = "banner"
    GALLERY_PHOTO = "gallery-photo"
    PRODUCT_IMAGE = "product-image"
    PRODUCT_FILE = "product-file"
    PLAN_IMAGE = "plan-image"
