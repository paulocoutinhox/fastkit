class ModelRegistry:
    """Collects mapped model classes contributed by installed apps."""

    def __init__(self):
        self._models: dict[str, tuple[type, str]] = {}

    def register(self, model: type, source: str = "unknown") -> None:
        key = f"{model.__module__}.{model.__qualname__}"

        if key in self._models:
            existing = self._models[key][1]
            raise ValueError(
                f"model '{key}' already registered by '{existing}', now by '{source}'"
            )

        self._models[key] = (model, source)

    def all(self) -> list[type]:
        return [model for model, _ in self._models.values()]

    def sources(self) -> dict[str, str]:
        return {key: source for key, (_, source) in self._models.items()}
