import pytest

from fastkit_core.errors.exceptions import FastKitError
from fastkit_storage.s3 import S3StorageProvider


async def test_put_get_stat(fake_s3_cls):
    store = S3StorageProvider(fake_s3_cls(), bucket="assets")

    stat = await store.put("docs/a.txt", b"hello", content_type="text/plain")
    assert stat.size_bytes == 5

    assert await store.get("docs/a.txt") == b"hello"
    assert await store.exists("docs/a.txt")

    described = await store.stat("docs/a.txt")
    assert described.content_type == "text/plain"


class FlakyClient:
    def __init__(self, failures):
        self.remaining_failures = failures
        self.puts = 0

    async def put_object(self, **kwargs):
        if self.remaining_failures > 0:
            self.remaining_failures -= 1

            raise ConnectionError("transient")

        self.puts += 1


async def _noop_sleep(_seconds):
    return None


async def test_put_retries_transient_failures():
    from fastkit_core.resilience import RetryPolicy

    client = FlakyClient(failures=2)
    store = S3StorageProvider(
        client,
        bucket="assets",
        retry_policy=RetryPolicy(max_attempts=3),
        sleep=_noop_sleep,
    )

    stat = await store.put("a.txt", b"data")

    assert stat.size_bytes == 4
    assert client.puts == 1


async def test_put_trips_circuit_after_persistent_failure():
    from fastkit_core.resilience import CircuitBreaker, CircuitOpenError, RetryPolicy

    breaker = CircuitBreaker(failure_threshold=2, reset_after_seconds=1000)
    store = S3StorageProvider(
        FlakyClient(failures=99),
        bucket="assets",
        breaker=breaker,
        retry_policy=RetryPolicy(max_attempts=2),
        sleep=_noop_sleep,
    )

    with pytest.raises(ConnectionError):
        await store.put("a.txt", b"data")

    with pytest.raises(CircuitOpenError):
        await store.put("b.txt", b"data")


async def test_get_missing_raises(fake_s3_cls):
    store = S3StorageProvider(fake_s3_cls(), bucket="assets")

    with pytest.raises(FastKitError, match="not found"):
        await store.get("missing.txt")

    with pytest.raises(FastKitError, match="not found"):
        await store.stat("missing.txt")

    assert not await store.exists("missing.txt")


async def test_delete_copy_move(fake_s3_cls):
    store = S3StorageProvider(fake_s3_cls(), bucket="assets")
    await store.put("a.txt", b"data")

    await store.copy("a.txt", "b.txt")
    assert await store.exists("b.txt")

    await store.move("b.txt", "c.txt")
    assert not await store.exists("b.txt")
    assert await store.exists("c.txt")

    await store.delete("c.txt")
    assert not await store.exists("c.txt")


async def test_presign(fake_s3_cls):
    store = S3StorageProvider(fake_s3_cls(), bucket="assets")

    download = await store.presign_download("a.txt", expires_in=120)
    assert download.method == "GET"
    assert "op=get_object" in download.url

    upload = await store.presign_upload("a.txt")
    assert upload.method == "PUT"


async def test_health(fake_s3_cls):
    healthy = S3StorageProvider(fake_s3_cls(), bucket="assets")
    assert (await healthy.health()).status.value == "healthy"

    unhealthy = S3StorageProvider(fake_s3_cls(fail_health=True), bucket="assets")
    assert (await unhealthy.health()).status.value == "unavailable"
