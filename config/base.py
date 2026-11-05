from pathlib import Path

from helpers.text import slugify

BASE_DIR = Path(__file__).resolve().parent.parent


# Everything a running instance writes on disk lives under one directory, so nothing of the developer machine lands in the repository root.
DATA_DIR = BASE_DIR / "data"

# What the product is called, written once and read by the api, the admin and the mailer.
NAME = "FastKit"


# The same name where it has to be an identifier rather than a title: every cookie this site writes, and the throwaway container the schema diff builds in.
# It is derived so that a product started from this template carries its own name on day one instead of writing somebody else's on the browsers of its readers.
SLUG = slugify(NAME)
