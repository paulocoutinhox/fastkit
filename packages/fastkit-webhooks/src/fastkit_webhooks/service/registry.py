class WebhookRegistry:
    def __init__(self):
        self._providers: dict[str, object] = {}

    def register(self, provider) -> None:
        if provider.name in self._providers:
            raise ValueError(
                f"webhook provider '{provider.name}' is already registered"
            )

        self._providers[provider.name] = provider

    def get(self, name: str):
        provider = self._providers.get(name)

        if provider is None:
            raise KeyError(f"webhook provider '{name}' is not registered")

        return provider
