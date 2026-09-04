import io

import pytest
from PIL import Image

from config.base import ImageSettings
from enums.upload import UploadPurpose
from helpers.errors import ValidationError
from helpers.settings import settings
from services.upload import upload_service


def build_image(width: int, height: int, mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), "red").save(buffer, "PNG")

    return buffer.getvalue()


def read(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def processed(data: bytes, rule: ImageSettings):
    """The bytes are decoded once and shaped after, which is the order the service does it in."""
    return upload_service.process_image(upload_service.open_image(data), rule)


def test_a_crop_fills_the_exact_box_it_declares():
    data, extension, content_type = processed(build_image(1200, 400), ImageSettings(width=300, height=300, crop=True, image_format="jpeg"))
    image = read(data)

    assert image.size == (300, 300)
    assert image.format == "JPEG"
    assert extension == ".jpg"
    assert content_type == "image/jpeg"


def test_without_a_crop_the_image_keeps_its_proportion():
    data, _, _ = processed(build_image(1200, 400), ImageSettings(width=600, height=600, image_format="webp"))

    assert read(data).size == (600, 200)


def test_a_side_left_out_follows_the_other_one():
    data, _, _ = processed(build_image(1000, 500), ImageSettings(width=200, image_format="webp"))

    assert read(data).size == (200, 100)


def test_an_image_already_smaller_is_never_blown_up():
    data, _, _ = processed(build_image(80, 40), ImageSettings(width=800, height=800, image_format="webp"))

    assert read(data).size == (80, 40)


def test_a_rule_without_a_size_only_changes_the_format():
    data, extension, _ = processed(build_image(120, 90), ImageSettings(image_format="webp"))
    image = read(data)

    assert image.size == (120, 90)
    assert image.format == "WEBP"
    assert extension == ".webp"


@pytest.mark.parametrize("image_format,expected,extension", [("jpeg", "JPEG", ".jpg"), ("png", "PNG", ".png"), ("webp", "WEBP", ".webp")])
def test_every_declared_format_is_written(image_format, expected, extension):
    data, suffix, content_type = processed(build_image(60, 60), ImageSettings(image_format=image_format))

    assert read(data).format == expected
    assert suffix == extension
    assert content_type == f"image/{image_format}"


def test_a_lower_quality_writes_a_smaller_file():
    source = build_image(600, 600)
    heavy, _, _ = processed(source, ImageSettings(image_format="jpeg", quality=95))
    light, _, _ = processed(source, ImageSettings(image_format="jpeg", quality=20))

    assert len(light) < len(heavy)


def test_transparency_is_flattened_for_a_format_that_holds_none():
    data, _, _ = processed(build_image(50, 50, mode="RGBA"), ImageSettings(image_format="jpeg"))

    assert read(data).mode == "RGB"


def test_what_is_not_an_image_is_refused():
    with pytest.raises(ValidationError):
        processed(b"not an image at all", ImageSettings())


@pytest.mark.parametrize("purpose", [UploadPurpose.IMAGE, UploadPurpose.AVATAR, UploadPurpose.BANNER, UploadPurpose.GALLERY_PHOTO, UploadPurpose.PRODUCT_IMAGE, UploadPurpose.PLAN_IMAGE])
def test_every_image_purpose_declares_how_it_is_treated(purpose):
    rule = settings.uploads[purpose].image

    assert rule is not None
    assert rule.image_format in ("jpeg", "png", "webp")
    assert 1 <= rule.quality <= 100
    assert rule.width is not None


@pytest.mark.parametrize("purpose", [UploadPurpose.PRODUCT_FILE])
def test_a_document_purpose_treats_nothing(purpose):
    assert settings.uploads[purpose].image is None


def test_a_product_image_comes_out_in_the_one_box_every_listing_draws():
    rule = settings.uploads[UploadPurpose.PRODUCT_IMAGE].image
    data, _, _ = processed(build_image(1000, 600), rule)

    assert read(data).size == (1280, 720)


@pytest.mark.parametrize("purpose,expected", [(UploadPurpose.AVATAR, (256, 256)), (UploadPurpose.PRODUCT_IMAGE, (1280, 720)), (UploadPurpose.IMAGE, (80, 80))])
def test_a_box_with_a_crop_fills_itself_and_one_without_leaves_a_small_image_alone(purpose, expected):
    """A listing needs the exact box, and a content image has no box to fill."""
    data, _unused, _also = processed(build_image(80, 80), settings.uploads[purpose].image)

    assert Image.open(io.BytesIO(data)).size == expected


class Sent:
    """What an upload looks like to the service, which never depends on how the bytes arrived."""

    def __init__(self, filename: str, data: bytes, content_type: str = "image/png"):
        self.filename = filename
        self.content_type = content_type
        self.body = io.BytesIO(data)

    async def read(self, size: int = -1) -> bytes:
        return self.body.read(size)


async def test_a_purpose_that_keeps_the_original_stores_the_bytes_that_arrived(db, monkeypatch):
    """Processing is what a rule asks for, and a rule may ask for exactly what was sent instead."""
    from helpers.storage import storage

    original = build_image(1200, 400)
    kept = settings.uploads[UploadPurpose.IMAGE].model_copy(update={"image": settings.uploads[UploadPurpose.IMAGE].image.model_copy(update={"store": "original"})})

    monkeypatch.setitem(settings.uploads, UploadPurpose.IMAGE, kept)

    stored = await upload_service.store(db, UploadPurpose.IMAGE, Sent("photo.png", original))

    assert stored["key"].endswith(".png")
    assert await storage.read(stored["key"]) == original
    assert stored["size"] == len(original)


async def test_a_purpose_that_keeps_the_original_still_refuses_what_is_not_an_image(db, monkeypatch):
    """The name claims an extension and the bytes are what they are, so the content is decoded whatever is stored."""
    kept = settings.uploads[UploadPurpose.IMAGE].model_copy(update={"image": settings.uploads[UploadPurpose.IMAGE].image.model_copy(update={"store": "original"})})

    monkeypatch.setitem(settings.uploads, UploadPurpose.IMAGE, kept)

    with pytest.raises(ValidationError) as refused:
        await upload_service.store(db, UploadPurpose.IMAGE, Sent("photo.png", b"not an image at all"))

    assert refused.value.code == "error.upload-not-an-image"


async def test_a_purpose_named_by_the_original_keeps_the_name_the_person_knows_it_by(db, monkeypatch):
    from enums.upload import Naming

    named = settings.uploads[UploadPurpose.IMAGE].model_copy(update={"naming": Naming.ORIGINAL})

    monkeypatch.setitem(settings.uploads, UploadPurpose.IMAGE, named)

    stored = await upload_service.store(db, UploadPurpose.IMAGE, Sent("Minha Foto (2024).PNG", build_image(60, 60)))

    assert stored["key"].endswith("/minha-foto-2024.webp")


async def test_a_purpose_named_by_a_token_carries_no_word_of_the_name_that_was_sent(db):
    stored = await upload_service.store(db, UploadPurpose.IMAGE, Sent("Minha Foto (2024).PNG", build_image(60, 60)))

    assert "minha" not in stored["key"]
    assert stored["key"].endswith(".webp")


async def test_every_key_carries_the_token_the_sweep_reads_whatever_it_is_named_by(db, monkeypatch):
    """The orphan sweep knows a file of ours by the uuid in its key, so a name a person chose is never the whole of one."""
    from enums.upload import Naming
    from helpers.storage import uuids_in

    for naming in Naming:
        monkeypatch.setitem(settings.uploads, UploadPurpose.IMAGE, settings.uploads[UploadPurpose.IMAGE].model_copy(update={"naming": naming}))

        stored = await upload_service.store(db, UploadPurpose.IMAGE, Sent("photo.png", build_image(40, 40)))

        assert uuids_in(stored["key"]), f"{naming} wrote a key the sweep cannot read"


def test_a_canvas_larger_than_this_instance_draws_is_refused_before_it_is_allocated():
    """A few hundred kilobytes can name a canvas of hundreds of megabytes, and decoding it is how one request kills the process."""
    bomb = build_image(9000, 9000, "L")

    assert len(bomb) < settings.image_max_pixels // 100

    with pytest.raises(ValidationError) as refused:
        upload_service.open_image(bomb)

    assert refused.value.code == "error.upload-image-too-large"


def test_a_canvas_past_what_the_decoder_itself_allows_is_a_refusal_and_never_a_crash():
    """Pillow raises past twice its own ceiling, and that error is not one a caller ever sees as anything but a refusal."""
    with pytest.raises(ValidationError):
        upload_service.open_image(build_image(14000, 14000, "L"))
