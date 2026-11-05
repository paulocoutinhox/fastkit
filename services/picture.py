from io import BytesIO


class Picture:
    """The bytes of a picture kept beside the seed, shaped as what the upload service takes, so a seeded file is stored exactly as an operator's upload is."""

    def __init__(self, filename: str, body: bytes):
        self.filename = filename
        self.stream = BytesIO(body)

    async def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)
