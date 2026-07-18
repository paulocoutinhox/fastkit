import asyncio

from fastkit_core.errors.exceptions import FastKitError
from fastkit_core.resilience import CircuitBreaker, RetryPolicy, run_with_retry
from fastkit_storage.errors import OBJECT_NOT_FOUND
from fastkit_storage.paths import safe_key
from fastkit_storage.provider import (
    ObjectStat,
    PresignedUrl,
    StorageHealth,
    StorageStatus,
)


class S3StorageProvider:
    """S3-compatible storage operating over an injected async client (aioboto3-style).

    Mutating operations retry transient failures with exponential backoff and trip a
    circuit breaker so a persistently unreachable bucket fails fast and recovers on its own.
    """

    def __init__(
        self,
        client,
        bucket: str,
        breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep=asyncio.sleep,
    ):
        self._client = client
        self._bucket = bucket
        self._breaker = breaker or CircuitBreaker()
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep

    async def _call(self, name: str, operation):
        return await run_with_retry(
            operation,
            self._retry_policy,
            breaker=self._breaker,
            sleep=self._sleep,
            name=f"s3.{name}",
        )

    async def put(
        self, key: str, data: bytes, content_type: str | None = None
    ) -> ObjectStat:
        normalized = safe_key(key)
        await self._call(
            "put",
            lambda: self._client.put_object(
                Bucket=self._bucket,
                Key=normalized,
                Body=data,
                ContentType=content_type or "application/octet-stream",
            ),
        )

        return ObjectStat(
            key=normalized, size_bytes=len(data), content_type=content_type
        )

    async def get(self, key: str) -> bytes:
        try:
            response = await self._client.get_object(
                Bucket=self._bucket, Key=safe_key(key)
            )
        except Exception as error:
            raise FastKitError(
                OBJECT_NOT_FOUND, message=f"object '{key}' not found"
            ) from error

        return await response["Body"].read()

    async def delete(self, key: str) -> None:
        await self._call(
            "delete",
            lambda: self._client.delete_object(Bucket=self._bucket, Key=safe_key(key)),
        )

    async def exists(self, key: str) -> bool:
        try:
            await self._client.head_object(Bucket=self._bucket, Key=safe_key(key))

            return True
        except Exception:
            return False

    async def stat(self, key: str) -> ObjectStat:
        try:
            head = await self._client.head_object(
                Bucket=self._bucket, Key=safe_key(key)
            )
        except Exception as error:
            raise FastKitError(
                OBJECT_NOT_FOUND, message=f"object '{key}' not found"
            ) from error

        return ObjectStat(
            key=safe_key(key),
            size_bytes=head["ContentLength"],
            content_type=head.get("ContentType"),
        )

    async def copy(self, source: str, destination: str) -> None:
        await self._call(
            "copy",
            lambda: self._client.copy_object(
                Bucket=self._bucket,
                Key=safe_key(destination),
                CopySource={"Bucket": self._bucket, "Key": safe_key(source)},
            ),
        )

    async def move(self, source: str, destination: str) -> None:
        await self.copy(source, destination)
        await self.delete(source)

    async def presign_upload(self, key: str, expires_in: int = 3600) -> PresignedUrl:
        url = await self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": safe_key(key)},
            ExpiresIn=expires_in,
        )

        return PresignedUrl(url=url, method="PUT", expires_in=expires_in)

    async def presign_download(self, key: str, expires_in: int = 3600) -> PresignedUrl:
        url = await self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": safe_key(key)},
            ExpiresIn=expires_in,
        )

        return PresignedUrl(url=url, method="GET", expires_in=expires_in)

    async def health(self) -> StorageHealth:
        try:
            await self._client.head_bucket(Bucket=self._bucket)

            return StorageHealth(StorageStatus.healthy)
        except Exception as error:
            return StorageHealth(StorageStatus.unavailable, detail=str(error))
