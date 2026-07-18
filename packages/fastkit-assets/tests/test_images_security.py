import pytest

from fastkit_core.errors.exceptions import FastKitError
from fastkit_assets.images import ImageInfo, enforce_pixels, inspect, process_variant
from fastkit_assets.presets import ImageVariantSpec
from fastkit_assets.security import (
    ALLOWED_IMAGE_MIME,
    checksum,
    enforce_mime,
    enforce_size,
    random_object_key,
)


def test_inspect_valid_image(image_factory):
    info = inspect(image_factory(width=100, height=50))

    assert info.width == 100
    assert info.height == 50
    assert info.mime_type == "image/png"


def test_inspect_rejects_non_image():
    with pytest.raises(FastKitError, match="not a valid image"):
        inspect(b"this is not an image")


def test_enforce_pixels():
    info = ImageInfo(format="PNG", mime_type="image/png", width=100, height=100)

    enforce_pixels(info, max_pixels=20000)

    with pytest.raises(FastKitError, match="too many pixels"):
        enforce_pixels(info, max_pixels=5000)


def test_checksum_and_key():
    assert checksum(b"a") == checksum(b"a")
    key = random_object_key(5, "PNG!")
    assert key.startswith("5/")
    assert key.endswith(".png")
    assert random_object_key(None, "").endswith(".bin")


def test_enforce_size_and_mime():
    enforce_size(b"12345", 10)

    with pytest.raises(FastKitError, match="maximum allowed size"):
        enforce_size(b"12345678901", 10)

    enforce_mime("image/png", ALLOWED_IMAGE_MIME)

    with pytest.raises(FastKitError, match="not allowed"):
        enforce_mime("application/x-msdownload", ALLOWED_IMAGE_MIME)


@pytest.mark.parametrize("mode", ["cover", "contain", "fit", "pad", "crop", "original"])
def test_process_variant_modes(image_factory, mode):
    spec = ImageVariantSpec(name="v", width=64, height=64, mode=mode, format="webp", quality=80)
    variant = process_variant(image_factory(width=200, height=120), spec)

    assert variant.mime_type == "image/webp"
    assert variant.size_bytes > 0


def test_process_variant_rejects_unknown_format(image_factory):
    spec = ImageVariantSpec(name="v", width=64, height=64, mode="cover", format="avif")

    with pytest.raises(FastKitError, match="unknown output format"):
        process_variant(image_factory(width=64, height=64), spec)


def test_process_variant_rejects_a_non_image():
    spec = ImageVariantSpec(name="v", width=64, height=64, mode="cover", format="webp")

    with pytest.raises(FastKitError, match="not a valid image"):
        process_variant(b"this is not an image", spec)


def test_process_variant_max_width_and_height(image_factory):
    data = image_factory(width=400, height=200)

    wide = process_variant(data, ImageVariantSpec(name="w", width=100, mode="max_width", format="png"))
    assert wide.width == 100

    tall = process_variant(data, ImageVariantSpec(name="h", height=50, mode="max_height", format="png"))
    assert tall.height == 50


def test_process_variant_max_width_no_upscale(image_factory):
    data = image_factory(width=80, height=40)
    result = process_variant(data, ImageVariantSpec(name="w", width=200, mode="max_width", format="png"))

    assert result.width == 80


def test_process_variant_jpeg_converts_mode(image_factory):
    variant = process_variant(image_factory(fmt="PNG"), ImageVariantSpec(name="j", width=32, height=32, mode="cover", format="jpeg"))

    assert variant.mime_type == "image/jpeg"


def test_process_variant_unknown_mode(image_factory):
    with pytest.raises(FastKitError, match="unknown resize mode"):
        process_variant(image_factory(), ImageVariantSpec(name="x", width=10, height=10, mode="warp", format="png"))


def test_process_variant_rgba_to_jpeg():
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGBA", (64, 64), (10, 20, 30, 128)).save(buffer, format="PNG")

    variant = process_variant(buffer.getvalue(), ImageVariantSpec(name="j", width=32, height=32, mode="cover", format="jpeg"))

    assert variant.mime_type == "image/jpeg"


def test_aware_helper():
    from datetime import datetime, timezone

    from fastkit_assets.service import _aware

    aware = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert _aware(aware) is aware
    assert _aware(datetime(2026, 1, 1)).tzinfo is timezone.utc
