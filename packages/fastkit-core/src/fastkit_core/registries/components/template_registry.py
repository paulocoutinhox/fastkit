from fastkit_core.registries.components.template_directory import TemplateDirectory
from fastkit_core.registries.components.template_package import TemplatePackage


class TemplateRegistry:
    """Stores template locations with priority so consumers can build a resolving loader."""

    def __init__(self):
        self._directories: list[TemplateDirectory] = []
        self._packages: list[TemplatePackage] = []
        self.overrides: dict[str, str] = {}

    def add_directory(
        self, path: str, priority: int = 0, source: str = "unknown"
    ) -> None:
        self._directories.append(TemplateDirectory(str(path), priority, source))

    def add_package(
        self,
        package: str,
        directory: str = "templates",
        priority: int = 0,
        source: str = "unknown",
    ) -> None:
        self._packages.append(TemplatePackage(package, directory, priority, source))

    def add_override(self, template_key: str, target: str) -> None:
        self.overrides[template_key] = target

    def directories(self) -> list[TemplateDirectory]:
        return sorted(self._directories, key=lambda item: -item.priority)

    def packages(self) -> list[TemplatePackage]:
        return sorted(self._packages, key=lambda item: -item.priority)
