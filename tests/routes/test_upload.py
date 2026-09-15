import io
from uuid import UUID

import pytest
from PIL import Image

from helpers.errors import ValidationError
from helpers.settings import settings
from helpers.storage import storage
from services.upload import upload_service


def build_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")

    return buffer.getvalue()


PNG = build_png()


async def test_administrator_stores_an_image(client, admin_headers):
    response = await client.post("/api/uploads/image", files={"file": ("cover.png", PNG, "image/png")}, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["key"].startswith("images/content/")

    stored = await storage.read(response.json()["key"])

    assert response.json()["size"] == len(stored)
    assert Image.open(io.BytesIO(stored)).format == "WEBP"


async def test_the_stored_url_is_built_from_the_configured_base(client, admin_headers):
    response = await client.post("/api/uploads/image", files={"file": ("cover.png", PNG, "image/png")}, headers=admin_headers)

    assert response.json()["url"] == f"{settings.storage.base_url}/{response.json()['key']}"


async def test_the_stored_name_is_a_uuid_with_a_lowercase_extension(client, admin_headers):
    response = await client.post("/api/uploads/image", files={"file": ("Minha Capa.PNG", PNG, "image/png")}, headers=admin_headers)

    stem, extension = response.json()["key"].rsplit("/", 1)[1].rsplit(".", 1)

    assert UUID(stem)
    assert extension == "webp"
    assert "minha" not in response.json()["key"]


async def test_a_file_that_only_pretends_to_be_an_image_is_refused(client, admin_headers):
    response = await client.post("/api/uploads/image", files={"file": ("cover.png", b"not an image at all", "image/png")}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.upload-not-an-image"


async def test_markup_dressed_as_an_image_is_refused(client, admin_headers):
    payload = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"

    assert (await client.post("/api/uploads/image", files={"file": ("x.svg", payload, "image/svg+xml")}, headers=admin_headers)).status_code == 422
    assert (await client.post("/api/uploads/image", files={"file": ("x.png", payload, "image/png")}, headers=admin_headers)).status_code == 422


async def test_a_document_is_not_decoded_as_an_image(client, admin_headers):
    response = await client.post("/api/uploads/product-file", files={"file": ("book.epub", b"PK\x03\x04 not really a zip", "application/epub+zip")}, headers=admin_headers)

    assert response.status_code == 201


async def test_an_extension_outside_the_rule_is_refused(client, admin_headers):
    response = await client.post("/api/uploads/image", files={"file": ("book.epub", PNG, "application/epub+zip")}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.upload-type-not-allowed"


async def test_an_empty_file_is_refused(client, admin_headers):
    response = await client.post("/api/uploads/image", files={"file": ("cover.png", b"", "image/png")}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.upload-empty"


async def test_a_file_above_the_rule_is_refused(client, admin_headers):
    oversized = b"0" * (10 * 1024 * 1024 + 1)

    response = await client.post("/api/uploads/image", files={"file": ("cover.png", oversized, "image/png")}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.upload-too-large"


async def test_a_normal_account_stores_nothing_through_here(client, member_headers):
    """The picture of an account goes through its own route, and everything this one holds is a record an operator fills in."""
    for purpose in ("avatar", "product-image"):
        refused = await client.post(f"/api/uploads/{purpose}", files={"file": ("me.png", PNG, "image/png")}, headers=member_headers)

        assert refused.status_code == 403


async def test_an_unknown_purpose_is_refused(client, admin_headers):
    response = await client.post("/api/uploads/whatever", files={"file": ("cover.png", PNG, "image/png")}, headers=admin_headers)

    assert response.status_code == 422


async def test_uploading_requires_a_token(client):
    assert (await client.post("/api/uploads/image", files={"file": ("cover.png", PNG, "image/png")})).status_code == 401


@pytest.mark.parametrize("purpose,name", [("product-file", "book.epub"), ("gallery-photo", "photo.png"), ("product-image", "product.png"), ("plan-image", "plan.png"), ("banner", "promo.png")])
async def test_every_purpose_has_its_folder(client, admin_headers, purpose, name):
    response = await client.post(f"/api/uploads/{purpose}", files={"file": (name, PNG, "application/octet-stream")}, headers=admin_headers)

    assert response.status_code == 201


async def test_discarding_a_key_removes_the_file(client, admin_headers):
    stored = await client.post("/api/uploads/image", files={"file": ("cover.png", PNG, "image/png")}, headers=admin_headers)

    await storage.delete(stored.json()["key"])

    assert await storage.read(stored.json()["key"]) is None


async def test_a_body_over_the_limit_stops_being_read():
    read = []

    class Endless:
        async def read(self, size):
            read.append(size)

            return b"x" * size

    with pytest.raises(ValidationError):
        await upload_service.spool_within(Endless(), 200 * 1024)

    assert sum(read) < 1024 * 1024


async def test_a_body_inside_the_limit_is_read_whole():
    class Body:
        def __init__(self, data):
            self.data = data
            self.offset = 0

        async def read(self, size):
            chunk = self.data[self.offset : self.offset + size]
            self.offset += len(chunk)

            return chunk

    body, size = await upload_service.spool_within(Body(b"abc" * 1000), 1024 * 1024)

    assert size == 3000
    assert body.read() == b"abc" * 1000


async def test_a_body_bigger_than_the_spool_never_sits_whole_in_memory():
    """An audiobook is half a gigabyte, and holding one in the process is how a couple of uploads take the server down."""

    class Body:
        def __init__(self, data):
            self.data = data
            self.offset = 0

        async def read(self, size):
            chunk = self.data[self.offset : self.offset + size]
            self.offset += len(chunk)

            return chunk

    body, size = await upload_service.spool_within(Body(b"x" * (5 * 1024 * 1024)), 512 * 1024 * 1024)

    assert size == 5 * 1024 * 1024
    assert body._rolled is True


async def test_a_purpose_named_by_the_original_answers_the_name_the_person_will_read(client, admin_headers):
    """A product file is downloaded by whoever bought it, and `manual.pdf` is what they expect the browser to save."""
    response = await client.post("/api/uploads/product-file", files={"file": ("Manual do Usuário.PDF", b"%PDF-1.4 pretend", "application/pdf")}, headers=admin_headers)

    key = response.json()["key"]
    folder, name = key.rsplit("/", 1)

    assert response.status_code == 201
    assert name == "manual-do-usuario.pdf"

    # The token is still in the key, one segment up, because that is what the orphan sweep knows a file of ours by.
    assert UUID(folder.rsplit("/", 1)[1])
