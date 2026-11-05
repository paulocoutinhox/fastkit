"""Where a stored file lives, whichever machine actually holds it."""

import os
import re
from uuid import uuid4

from enums.naming import Naming
from enums.storage_provider import StorageProvider
from helpers.dates import now
from helpers.filesystem_storage import FilesystemStorage
from helpers.s3_storage import S3Storage
from helpers.settings import settings
from helpers.storage_contract import Storage
from helpers.text import slugify

# A name long enough to break a key is cut, because a bucket has a limit and nobody reads past this anyway.
NAME_LIMIT = 80


# Every stored file carries a UUID in its key, and that is the only thing a row ever mentions of it.
NAMED = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


def uuids_in(value) -> set[str]:
    """Which stored files a value mentions, whether it is a key in a column of its own or a link inside the markup of a body."""
    return {found.group(0).lower() for found in NAMED.finditer(str(value))}


def readable_name(filename: str) -> str:
    """The name somebody uploaded, reduced to what a key may carry: no separator, no accent, no dot but the one before the extension, and no UUID of its own, because the one the key carries is how the file is found."""
    name = slugify(os.path.splitext(filename)[0], "file", NAME_LIMIT)

    # A name is cut to a slug before its UUIDs are looked for, because the slug is what turns underscores and dots into the dashes of one, and cutting one out can join what surrounds it into another.
    while NAMED.search(name):
        name = slugify(NAMED.sub("-", name), "file", NAME_LIMIT)

    return name


def build_key(folder: str, filename: str, naming: Naming = Naming.UUID) -> str:
    """Every stored file carries a UUID, so two uploads never collide and the orphan sweep can always tell whose it is."""
    extension = os.path.splitext(filename)[1].lower()
    today = now()
    token = uuid4()

    # The UUID becomes a folder rather than the name, so the address ends in the name the person knows it by.
    if naming == Naming.ORIGINAL:
        return f"{folder}/{today:%Y/%m/%d}/{token}/{readable_name(filename)}{extension}"

    return f"{folder}/{today:%Y/%m/%d}/{token}{extension}"


PROVIDERS: dict[StorageProvider, type[Storage]] = {StorageProvider.FILESYSTEM: FilesystemStorage, StorageProvider.S3: S3Storage}


storage: Storage = PROVIDERS[settings.storage.provider](settings.storage)
