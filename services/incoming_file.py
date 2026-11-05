from typing import Protocol


class IncomingFile(Protocol):
    """What storing a file actually needs, so this layer never depends on how the bytes arrived."""

    filename: str | None

    async def read(self, size: int = -1) -> bytes: ...
