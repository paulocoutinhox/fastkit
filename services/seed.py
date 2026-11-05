from helpers.storage import storage


async def discard_media() -> int:
    """A database built from nothing leaves every file the old one pointed at orphaned, so the storage of this machine is emptied with it."""
    discarded = 0

    async for key in storage.walk():
        await storage.delete(key)
        discarded += 1

    return discarded
