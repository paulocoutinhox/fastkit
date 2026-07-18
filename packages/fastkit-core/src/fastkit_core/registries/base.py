from dataclasses import dataclass
from typing import Generic, Iterator, TypeVar

T = TypeVar("T")


class RegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistryEntry(Generic[T]):
    key: str
    value: T
    source: str
    priority: int


class Registry(Generic[T]):
    """Ordered registry with duplicate detection, source tracking and freeze support."""

    def __init__(self, name: str, allow_override: bool = False):
        self.name = name
        self.allow_override = allow_override

        self._entries: dict[str, RegistryEntry[T]] = {}
        self._frozen = False

    def register(
        self, key: str, value: T, source: str = "unknown", priority: int = 0
    ) -> None:
        if self._frozen:
            raise RegistryError(
                f"registry '{self.name}' is frozen and cannot accept '{key}'"
            )

        existing = self._entries.get(key)

        if existing is not None and not self.allow_override:
            raise RegistryError(
                f"duplicate key '{key}' in registry '{self.name}' (existing source: {existing.source}, new source: {source})"
            )

        self._entries[key] = RegistryEntry(
            key=key, value=value, source=source, priority=priority
        )

    def get(self, key: str) -> T:
        entry = self._entries.get(key)

        if entry is None:
            raise RegistryError(f"key '{key}' not found in registry '{self.name}'")

        return entry.value

    def try_get(self, key: str) -> T | None:
        entry = self._entries.get(key)

        return entry.value if entry is not None else None

    def contains(self, key: str) -> bool:
        return key in self._entries

    def keys(self) -> list[str]:
        return list(self._entries.keys())

    def entries(self) -> list[RegistryEntry[T]]:
        return sorted(
            self._entries.values(), key=lambda item: (-item.priority, item.key)
        )

    def values(self) -> list[T]:
        return [entry.value for entry in self.entries()]

    def freeze(self) -> None:
        self._frozen = True

    @property
    def frozen(self) -> bool:
        return self._frozen

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[T]:
        return iter(self.values())
