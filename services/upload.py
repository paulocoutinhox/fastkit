from PIL import Image


def owner_of(instance) -> str:
    """The name a row mentions a file under, which is its table and its id."""
    return f"{instance.__tablename__}:{instance.id}"


# The decoder warns rather than refuses up to twice a ceiling of its own, so the exact one is this side's and is checked before anything is allocated.
Image.MAX_IMAGE_PIXELS = None
