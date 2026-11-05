"""Works against S3 and any compatible endpoint, which is how r2 is reached."""

from typing import BinaryIO

import aioboto3
from botocore.config import Config

from config.storage_settings import StorageSettings
from helpers.storage_contract import Storage

# Between two reads of one answer, so a large file is bounded by a silent bucket and never by its size.
TIMEOUT = 15.0


class S3Storage(Storage):
    def __init__(self, config: StorageSettings):
        self.bucket = config.bucket
        self.base_url = config.base_url.rstrip("/")
        self.session = aioboto3.Session(aws_access_key_id=config.access_key, aws_secret_access_key=config.secret_key, region_name=config.region)
        self.endpoint = {"endpoint_url": config.endpoint_url} if config.endpoint_url else {}

    def client(self):
        """A bucket that accepts the connection and then says nothing is waited for as long as this side chose, and never the library's minute."""
        return self.session.client("s3", config=Config(connect_timeout=TIMEOUT, read_timeout=TIMEOUT), **self.endpoint)

    async def save(self, key: str, data: bytes | BinaryIO, content_type: str) -> str:
        """Who may read an object is the bucket to say, and an upload that names an acl is refused by a bucket made today."""
        async with self.client() as client:
            await client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

        return key

    async def delete(self, key: str) -> None:
        async with self.client() as client:
            await client.delete_object(Bucket=self.bucket, Key=key)

    async def walk(self):
        async with self.client() as client:
            paginator = client.get_paginator("list_objects_v2")

            async for page in paginator.paginate(Bucket=self.bucket):
                for item in page.get("Contents", []):
                    yield item["Key"]
