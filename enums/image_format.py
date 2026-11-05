from enum import StrEnum


class ImageFormat(StrEnum):
    """What an uploaded image becomes, which is also where the extension of its key comes from."""

    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"
