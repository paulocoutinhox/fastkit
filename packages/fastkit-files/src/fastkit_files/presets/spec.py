from dataclasses import dataclass


@dataclass(frozen=True)
class ImageVariantSpec:
    name: str
    width: int | None = None
    height: int | None = None
    mode: str = "cover"
    format: str = "webp"
    quality: int = 85
