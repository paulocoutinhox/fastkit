from dataclasses import dataclass, field

from fastkit_files.presets.spec import ImageVariantSpec


@dataclass(frozen=True)
class ImagePreset:
    name: str
    variants: list[ImageVariantSpec] = field(default_factory=list)


AVATAR_PRESET = ImagePreset(
    name="avatar",
    variants=[
        ImageVariantSpec(
            name="large",
            width=1024,
            height=1024,
            mode="cover",
            format="webp",
            quality=88,
        ),
        ImageVariantSpec(
            name="thumb", width=256, height=256, mode="cover", format="webp", quality=82
        ),
    ],
)
