import pytest

from fastkit_core.errors.exceptions import ValidationError
from fastkit_admin.helpers import read_upload


class _FakeUpload:
    def __init__(self, data: bytes):
        self._data = data

    async def read(self, size: int = -1) -> bytes:
        return self._data if size < 0 else self._data[:size]


async def test_read_upload_returns_data_within_the_cap():
    assert await read_upload(_FakeUpload(b"small"), max_bytes=10) == b"small"


async def test_read_upload_rejects_an_oversized_file():
    with pytest.raises(ValidationError) as exc:
        await read_upload(_FakeUpload(b"x" * 11), max_bytes=10)

    assert exc.value.field_errors[0].code == "validation.file-too-large"
