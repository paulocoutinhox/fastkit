import pytest


class FakeS3Client:
    """In-memory async stand-in for an aioboto3 S3 client."""

    def __init__(self, fail_health=False):
        self.objects: dict[str, dict] = {}
        self.fail_health = fail_health

    async def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = {"body": Body, "content_type": ContentType}

    async def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)

        return {"Body": _Body(self.objects[Key]["body"])}

    async def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    async def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)

        record = self.objects[Key]

        return {"ContentLength": len(record["body"]), "ContentType": record["content_type"]}

    async def copy_object(self, Bucket, Key, CopySource):
        self.objects[Key] = dict(self.objects[CopySource["Key"]])

    async def generate_presigned_url(self, operation, Params, ExpiresIn):
        return f"https://s3.example.com/{Params['Key']}?op={operation}&exp={ExpiresIn}"

    async def head_bucket(self, Bucket):
        if self.fail_health:
            raise ConnectionError("bucket unreachable")


class _Body:
    def __init__(self, data):
        self._data = data

    async def read(self):
        return self._data


class Clock:
    def __init__(self):
        self.now = 1000

    def __call__(self):
        return self.now


@pytest.fixture
def fake_s3_cls():
    return FakeS3Client


@pytest.fixture
def clock():
    return Clock()
