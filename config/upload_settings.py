from pydantic import BaseModel

from config.image_settings import ImageSettings
from enums.naming import Naming


class UploadSettings(BaseModel):
    """One purpose: where it is stored, what it accepts, how big it may be, what it is called and what it becomes."""

    folder: str

    # Every extension the purpose accepts, by the type the stored file is served as.
    extensions: dict[str, str]
    max_bytes: int

    # A purpose with no image rule stores exactly the bytes that arrived.
    image: ImageSettings | None = None

    naming: Naming = Naming.UUID
