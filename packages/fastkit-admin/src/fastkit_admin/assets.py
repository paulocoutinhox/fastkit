from dataclasses import dataclass
from importlib.metadata import entry_points


@dataclass(frozen=True)
class AssetTag:
    """A resolved asset ready to render as a <link> or <script> with its own tag attributes."""

    kind: str
    url: str
    attrs: dict


class AssetRegistry:
    """Collects vendored front-end assets from installed providers so nothing loads from a CDN.

    A provider is any object exposing `MOUNT` (url prefix), `STATIC_DIR` (directory to serve) and
    `ASSETS` (a list of dicts with `kind`, `path`, `order` and optional `attrs`). Providers register
    themselves through the `fastkit.assets` entry point group, mirroring how apps are discovered.
    """

    def __init__(self, providers):
        self._providers = list(providers)

    @classmethod
    def discover(cls):
        return cls([entry_point.load() for entry_point in entry_points(group="fastkit.assets")])

    def mounts(self) -> list[tuple[str, object]]:
        return [(provider.MOUNT, provider.STATIC_DIR) for provider in self._providers]

    def _ordered(self):
        pairs = [(provider.MOUNT, asset) for provider in self._providers for asset in provider.ASSETS]

        return sorted(pairs, key=lambda pair: pair[1].get("order", 100))

    def tags(self, kind: str) -> list[AssetTag]:
        return [AssetTag(kind=asset["kind"], url=f"{mount}/{asset['path']}", attrs=asset.get("attrs", {})) for mount, asset in self._ordered() if asset["kind"] == kind]
