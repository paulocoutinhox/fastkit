from dataclasses import dataclass


class ModelRegistry:
    """Collects mapped model classes contributed by installed apps."""

    def __init__(self):
        self._models: dict[str, tuple[type, str]] = {}

    def register(self, model: type, source: str = "unknown") -> None:
        key = f"{model.__module__}.{model.__qualname__}"

        if key in self._models:
            existing = self._models[key][1]
            raise ValueError(f"model '{key}' already registered by '{existing}', now by '{source}'")

        self._models[key] = (model, source)

    def all(self) -> list[type]:
        return [model for model, _ in self._models.values()]

    def sources(self) -> dict[str, str]:
        return {key: source for key, (_, source) in self._models.items()}


class RouterRegistry:
    """Collects FastAPI routers so the runtime can mount them in one place."""

    def __init__(self):
        self._routers: list[tuple] = []

    def include(self, router, prefix: str = "", tags: list[str] | None = None, source: str = "unknown") -> None:
        self._routers.append((router, prefix, tags or [], source))

    def all(self) -> list[tuple]:
        return list(self._routers)


@dataclass(frozen=True)
class TemplateDirectory:
    path: str
    priority: int
    source: str


@dataclass(frozen=True)
class TemplatePackage:
    package: str
    directory: str
    priority: int
    source: str


class TemplateRegistry:
    """Stores template locations with priority so consumers can build a resolving loader."""

    def __init__(self):
        self._directories: list[TemplateDirectory] = []
        self._packages: list[TemplatePackage] = []
        self.overrides: dict[str, str] = {}

    def add_directory(self, path: str, priority: int = 0, source: str = "unknown") -> None:
        self._directories.append(TemplateDirectory(str(path), priority, source))

    def add_package(self, package: str, directory: str = "templates", priority: int = 0, source: str = "unknown") -> None:
        self._packages.append(TemplatePackage(package, directory, priority, source))

    def add_override(self, template_key: str, target: str) -> None:
        self.overrides[template_key] = target

    def directories(self) -> list[TemplateDirectory]:
        return sorted(self._directories, key=lambda item: -item.priority)

    def packages(self) -> list[TemplatePackage]:
        return sorted(self._packages, key=lambda item: -item.priority)
