class RouterRegistry:
    """Collects FastAPI routers so the runtime can mount them in one place."""

    def __init__(self):
        self._routers: list[tuple] = []

    def include(
        self,
        router,
        prefix: str = "",
        tags: list[str] | None = None,
        source: str = "unknown",
    ) -> None:
        self._routers.append((router, prefix, tags or [], source))

    def all(self) -> list[tuple]:
        return list(self._routers)
