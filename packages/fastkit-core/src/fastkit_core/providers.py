class ProviderRegistry:
    """Named factories for a swappable backend (cache, storage, mail…).

    Ships the framework's built-in providers and lets a consumer register its own by name, so a
    project selects a backend through settings without editing the framework.
    """

    def __init__(self, kind: str):
        self._kind = kind
        self._factories: dict[str, object] = {}

    def register(self, name: str, factory) -> None:
        self._factories[name] = factory

    def build(self, name: str, *args):
        factory = self._factories.get(name)

        if factory is None:
            raise ValueError(f"unknown {self._kind} provider '{name}'")

        return factory(*args)
