from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImageVariantSpec:
    name: str
    width: int | None = None
    height: int | None = None
    mode: str = "cover"
    format: str = "webp"
    quality: int = 85


@dataclass(frozen=True)
class ImagePreset:
    name: str
    variants: list[ImageVariantSpec] = field(default_factory=list)


AVATAR_PRESET = ImagePreset(
    name="avatar",
    variants=[
        ImageVariantSpec(name="large", width=1024, height=1024, mode="cover", format="webp", quality=88),
        ImageVariantSpec(name="thumb", width=256, height=256, mode="cover", format="webp", quality=82),
    ],
)
