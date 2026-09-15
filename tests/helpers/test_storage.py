import asyncio
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

import pytest

from config.base import StorageSettings
from enums.storage import StorageProvider
from helpers.storage import PROVIDERS, FilesystemStorage, S3Storage, build_key

LISTED_AT = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


class FakeBody:
    def __init__(self, data: bytes):
        self.data = data

    async def read(self) -> bytes:
        return self.data


class MissingKey(Exception):
    pass


class FakeClient:
    def __init__(self, store: dict):
        self.store = store
        self.exceptions = type("Exceptions", (), {"NoSuchKey": MissingKey})

    async def put_object(self, Bucket, Key, Body, ContentType, **options):
        self.store[Key] = Body

    async def get_object(self, Bucket, Key):
        if Key not in self.store:
            raise MissingKey()

        return {"Body": FakeBody(self.store[Key])}

    async def delete_object(self, Bucket, Key):
        self.store.pop(Key, None)

    def get_paginator(self, name):
        contents = [{"Key": key, "LastModified": LISTED_AT} for key in sorted(self.store)]

        return FakePaginator([{"Contents": contents[:1]}, {"Contents": contents[1:]}, {}])


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self, **options):
        async def stream():
            for page in self.pages:
                yield page

        return stream()


class FakeSession:
    def __init__(self, store: dict):
        self.store = store
        self.options = None

    def client(self, name, **options):
        self.options = options

        @asynccontextmanager
        async def scope():
            yield FakeClient(self.store)

        return scope()


@pytest.fixture
def remote(monkeypatch):
    store = {}
    session = FakeSession(store)

    instance = S3Storage(StorageSettings(provider=StorageProvider.S3, base_url="https://cdn.example.org", bucket="bucket", region="auto", endpoint_url="https://r2.example.org", access_key="key", secret_key="secret"))
    monkeypatch.setattr(instance, "session", session)

    return instance, store


def test_a_key_is_a_uuid_under_a_dated_folder():
    key = build_key("images/banner", "Minha Capa.PNG")
    folder, name = key.rsplit("/", 1)
    stem, extension = name.rsplit(".", 1)

    assert re.fullmatch(r"images/banner/\d{4}/\d{2}/\d{2}", folder)
    assert UUID(stem)
    assert extension == "png"


def test_a_key_never_repeats():
    assert build_key("images/banner", "capa.png") != build_key("images/banner", "capa.png")


@pytest.mark.parametrize("filename", ["Minha Capa.PNG", "book.EPUB", "one.Mp3"])
def test_a_key_lowercases_the_extension(filename):
    assert build_key("files", filename).endswith(filename.rsplit(".", 1)[1].lower())


def test_a_key_carries_nothing_the_person_typed():
    assert "capa" not in build_key("images/banner", "capa.png")
    assert "../" not in build_key("images/banner", "../../etc/passwd.png")


def test_a_key_without_a_name_has_no_extension():
    name = build_key("files", "").rsplit("/", 1)[1]

    assert UUID(name)


async def test_the_filesystem_provider_round_trips(tmp_path):
    instance = FilesystemStorage(StorageSettings(provider=StorageProvider.FILESYSTEM, base_url="/media/", root=tmp_path))

    key = await instance.save("images/one.png", b"data", "image/png")

    assert await instance.read(key) == b"data"
    assert instance.url(key) == "/media/images/one.png"

    await instance.delete(key)

    assert await instance.read(key) is None


async def test_the_filesystem_provider_ignores_deleting_what_is_gone(tmp_path):
    """The sweep and every replace delete by key, and a key already gone is the state they were after."""
    instance = FilesystemStorage(StorageSettings(provider=StorageProvider.FILESYSTEM, base_url="/media", root=tmp_path))

    await instance.delete("images/missing.png")

    assert await instance.read("images/missing.png") is None


async def test_the_remote_provider_round_trips(remote):
    instance, store = remote

    key = await instance.save("images/one.png", b"data", "image/png")

    assert store[key] == b"data"
    assert await instance.read(key) == b"data"
    assert instance.url(key) == "https://cdn.example.org/images/one.png"

    await instance.delete(key)

    assert await instance.read(key) is None


async def test_the_remote_provider_forwards_the_endpoint(remote):
    instance, _unused = remote

    await instance.save("images/one.png", b"data", "image/png")

    assert instance.session.options == {"endpoint_url": "https://r2.example.org"}


async def test_the_remote_provider_omits_an_empty_endpoint(monkeypatch):
    instance = S3Storage(StorageSettings(provider=StorageProvider.S3, base_url="https://cdn.example.org", bucket="bucket", region="auto", access_key="key", secret_key="secret"))
    session = FakeSession({})

    monkeypatch.setattr(instance, "session", session)
    await instance.save("images/one.png", b"data", "image/png")

    assert instance.session.options == {}


def test_the_provider_comes_from_the_configuration(tmp_path):
    assert PROVIDERS.keys() == set(StorageProvider), "a value of the enum nothing answers would be a storage nobody could build"
    assert PROVIDERS[StorageProvider.FILESYSTEM] is FilesystemStorage
    assert PROVIDERS[StorageProvider.S3] is S3Storage


async def test_the_filesystem_walk_names_every_file_by_its_key(tmp_path):
    instance = FilesystemStorage(StorageSettings(provider=StorageProvider.FILESYSTEM, base_url="/media", root=tmp_path))

    await instance.save("images/banner/2026/07/29/one.png", b"a", "image/png")
    await instance.save("images/gallery/2026/07/29/two.webp", b"b", "image/webp")

    listed = [key async for key, _ in instance.walk()]

    assert listed == ["images/banner/2026/07/29/one.png", "images/gallery/2026/07/29/two.webp"]


async def test_the_filesystem_walk_answers_when_each_file_was_written(tmp_path):
    instance = FilesystemStorage(StorageSettings(provider=StorageProvider.FILESYSTEM, base_url="/media", root=tmp_path))
    await instance.save("files/one.epub", b"a", "application/epub+zip")

    _, modified_at = [entry async for entry in instance.walk()][0]

    assert modified_at.tzinfo is not None


async def test_the_remote_walk_reads_every_page(remote):
    instance, store = remote

    for name in ("a.png", "b.png", "c.png"):
        await instance.save(name, b"x", "image/png")

    listed = [entry async for entry in instance.walk()]

    assert [key for key, _ in listed] == ["a.png", "b.png", "c.png"]
    assert listed[0][1] == LISTED_AT


def test_an_upload_never_names_an_acl():
    """A bucket made today owns its objects and refuses an upload that names one, so who may read it is the bucket to say."""
    written = {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def put_object(self, **kwargs):
            written.update(kwargs)

    storage = S3Storage(StorageSettings(provider=StorageProvider.S3, base_url="https://cdn.example.org", bucket="bucket", region="us-east-1", access_key="key", secret_key="secret"))
    storage.session = type("Session", (), {"client": lambda self, *a, **k: Client()})()

    asyncio.run(storage.save("images/x.jpg", b"x", "image/jpeg"))

    assert written["Key"] == "images/x.jpg"
    assert "ACL" not in written


def test_the_folder_of_every_purpose_is_public_facing_and_uses_dashes():
    """A storage path is a public address, so it never carries the underscore a python package would."""
    from helpers.settings import settings

    for purpose, rule in settings.uploads.items():
        assert "_" not in rule.folder, f"{purpose}: {rule.folder}"


def test_a_name_with_nothing_a_key_may_carry_still_answers_a_name():
    """A name written entirely in a script the key cannot hold would leave the file with no name at all."""
    from helpers.storage import readable_name

    assert readable_name("文件.pdf") == "file"
    assert readable_name("") == "file"
    assert readable_name("../../etc/passwd") == "etc-passwd"
    assert len(readable_name(f"{'a' * 200}.pdf")) == 80
