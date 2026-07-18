import pytest

from fastkit_core.errors.exceptions import FastKitError
from fastkit_storage.local import LocalStorageProvider
from fastkit_storage.paths import safe_key
from fastkit_storage.signing import sign, verify


def provider(tmp_path, clock):
    return LocalStorageProvider(
        str(tmp_path / "media"), base_url="/media", secret="s3cret", clock=clock
    )


def test_safe_key_rejects_traversal():
    assert safe_key("/a/b.txt") == "a/b.txt"

    with pytest.raises(FastKitError, match="empty object key"):
        safe_key("   ")

    with pytest.raises(FastKitError, match="'\\.\\.'"):
        safe_key("../etc/passwd")


def test_signing_roundtrip():
    signature = sign("secret", "a/b", 2000, "GET")

    assert verify("secret", "a/b", 2000, "GET", signature, now=1500)
    assert not verify("secret", "a/b", 2000, "GET", signature, now=2500)
    assert not verify("secret", "a/b", 2000, "GET", "tampered", now=1500)


async def test_put_get_stat_delete(tmp_path, clock):
    store = provider(tmp_path, clock)

    stat = await store.put("docs/a.txt", b"hello", content_type="text/plain")
    assert stat.size_bytes == 5
    assert stat.key == "docs/a.txt"

    assert await store.get("docs/a.txt") == b"hello"
    assert await store.exists("docs/a.txt")

    described = await store.stat("docs/a.txt")
    assert described.content_type == "text/plain"

    await store.delete("docs/a.txt")
    assert not await store.exists("docs/a.txt")


async def test_get_missing_raises(tmp_path, clock):
    store = provider(tmp_path, clock)

    with pytest.raises(FastKitError, match="not found"):
        await store.get("missing.txt")

    with pytest.raises(FastKitError, match="not found"):
        await store.stat("missing.txt")


async def test_copy_and_move(tmp_path, clock):
    store = provider(tmp_path, clock)
    await store.put("a.txt", b"data", content_type="text/plain")

    await store.copy("a.txt", "b.txt")
    assert await store.get("b.txt") == b"data"

    await store.move("b.txt", "c.txt")
    assert not await store.exists("b.txt")
    assert await store.get("c.txt") == b"data"


async def test_presign_urls_are_signed(tmp_path, clock):
    store = provider(tmp_path, clock)

    download = await store.presign_download("docs/a.txt", expires_in=60)
    assert download.method == "GET"
    assert "signature=" in download.url
    assert "expires=1060" in download.url

    upload = await store.presign_upload("docs/a.txt")
    assert upload.method == "PUT"


async def test_health_ok_and_failure(tmp_path, clock, monkeypatch):
    store = provider(tmp_path, clock)
    assert (await store.health()).status.value == "healthy"

    async def broken(*args, **kwargs):
        raise OSError("read only")

    monkeypatch.setattr("fastkit_storage.local.asyncio.to_thread", broken)
    assert (await store.health()).status.value == "unavailable"
