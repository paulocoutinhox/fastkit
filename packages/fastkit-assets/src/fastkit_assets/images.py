import io
from dataclasses import dataclass

from PIL import Image, ImageOps

from fastkit_core.errors.exceptions import FastKitError
from fastkit_assets.errors import NOT_AN_IMAGE, TOO_MANY_PIXELS
from fastkit_assets.presets import ImageVariantSpec

_FORMAT_MAP = {"webp": "WEBP", "jpeg": "JPEG", "jpg": "JPEG", "png": "PNG"}
_MIME_MAP = {"WEBP": "image/webp", "JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif"}


@dataclass(frozen=True)
class ImageInfo:
    format: str
    mime_type: str
    width: int
    height: int


@dataclass(frozen=True)
class ProcessedVariant:
    data: bytes
    format: str
    mime_type: str
    width: int
    height: int
    size_bytes: int


def inspect(data: bytes) -> ImageInfo:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
    except Exception as error:
        raise FastKitError(NOT_AN_IMAGE, message="uploaded file is not a valid image") from error

    with Image.open(io.BytesIO(data)) as image:
        return ImageInfo(format=image.format, mime_type=_MIME_MAP.get(image.format, "application/octet-stream"), width=image.width, height=image.height)


def enforce_pixels(info: ImageInfo, max_pixels: int) -> None:
    if info.width * info.height > max_pixels:
        raise FastKitError(TOO_MANY_PIXELS, message="image has too many pixels")


def _resize(image: Image.Image, spec: ImageVariantSpec) -> Image.Image:
    width, height = spec.width, spec.height

    if spec.mode == "original" or (width is None and height is None):
        return image

    if spec.mode == "cover":
        return ImageOps.fit(image, (width, height), method=Image.LANCZOS)

    if spec.mode in ("contain", "fit"):
        copy = image.copy()
        copy.thumbnail((width, height), Image.LANCZOS)

        return copy

    if spec.mode == "pad":
        return ImageOps.pad(image, (width, height), method=Image.LANCZOS, color=(255, 255, 255))

    if spec.mode == "crop":
        return ImageOps.fit(image, (width, height), method=Image.LANCZOS, centering=(0.5, 0.5))

    if spec.mode == "max_width":
        ratio = width / image.width

        return image.resize((width, max(1, round(image.height * ratio))), Image.LANCZOS) if image.width > width else image

    if spec.mode == "max_height":
        ratio = height / image.height

        return image.resize((max(1, round(image.width * ratio)), height), Image.LANCZOS) if image.height > height else image

    raise FastKitError(NOT_AN_IMAGE, message=f"unknown resize mode '{spec.mode}'")


def process_variant(data: bytes, spec: ImageVariantSpec) -> ProcessedVariant:
    """Strip metadata, honour EXIF orientation, resize and re-encode a clean variant."""

    if spec.format not in _FORMAT_MAP:
        raise FastKitError(NOT_AN_IMAGE, message=f"unknown output format '{spec.format}'")

    pillow_format = _FORMAT_MAP[spec.format]

    try:
        with Image.open(io.BytesIO(data)) as source:
            oriented = ImageOps.exif_transpose(source)

            if pillow_format == "JPEG" and oriented.mode not in ("RGB", "L"):
                oriented = oriented.convert("RGB")

            resized = _resize(oriented, spec)
            buffer = io.BytesIO()
            save_kwargs = {"format": pillow_format}

            if pillow_format in ("JPEG", "WEBP"):
                save_kwargs["quality"] = spec.quality

            resized.save(buffer, **save_kwargs)
            payload = buffer.getvalue()
            width, height = resized.width, resized.height
    except FastKitError:
        raise
    except Exception as error:
        raise FastKitError(NOT_AN_IMAGE, message="uploaded file is not a valid image") from error

    return ProcessedVariant(data=payload, format=spec.format, mime_type=_MIME_MAP[pillow_format], width=width, height=height, size_bytes=len(payload))
