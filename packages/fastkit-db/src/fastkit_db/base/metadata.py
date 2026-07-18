from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.types import PortableJSON


class MetadataMixin:
    meta: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
