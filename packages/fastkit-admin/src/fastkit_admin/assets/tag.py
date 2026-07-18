from dataclasses import dataclass


@dataclass(frozen=True)
class AssetTag:
    """A resolved asset ready to render as a <link> or <script> with its own tag attributes."""

    kind: str
    url: str
    attrs: dict
