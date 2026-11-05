from typing import Literal

from pydantic import BaseModel

from enums.image_format import ImageFormat


class ImageSettings(BaseModel):
    """What an uploaded image becomes before it is stored, so what reaches the storage never depends on what somebody sent."""

    width: int | None = None
    height: int | None = None
    crop: bool = False
    image_format: ImageFormat = ImageFormat.JPEG
    quality: int = 85

    # What is stored: the image this rule describes, or the bytes exactly as they arrived.
    # Either way the content is decoded first, so an extension can never lie about what the bytes are.
    store: Literal["processed", "original"] = "processed"
