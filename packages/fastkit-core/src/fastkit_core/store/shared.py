class SharedKeyValueStore:
    """Routes every operation to the runtime's shared cache provider, resolved lazily.

    Lazy resolution keeps the caller decoupled from the cache app's bootstrap order: the provider is
    looked up on first use, after every app has registered its components.
    """

    def __init__(self, resolve):
        self._resolve = resolve

    async def get(self, key: str) -> bytes | None:
        return await self._resolve().get(key)

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        await self._resolve().set(key, value, ttl)

    async def delete(self, key: str) -> None:
        await self._resolve().delete(key)

    async def increment(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        return await self._resolve().increment(key, amount, ttl)
