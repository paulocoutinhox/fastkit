"""What a value read by a person looks like, and what one typed by a person is worth."""

import re
import unicodedata

SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
DIGITS_PATTERN = re.compile(r"\D")
NUMBER_PATTERN = re.compile(r"(\d+)")


def alphabetical(value: str) -> tuple:
    """A sort key that ignores accents and case and reads a run of digits as a number."""
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()

    return tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in NUMBER_PATTERN.split(normalized) if part)


def slugify(value: str, fallback: str = "item", max_length: int | None = None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    slug = SLUG_PATTERN.sub("-", normalized.lower()).strip("-")

    if max_length is not None:
        slug = slug[:max_length].rstrip("-")

    return slug or fallback


def only_digits(value: str | None) -> str:
    if not value:
        return ""

    return DIGITS_PATTERN.sub("", value)


def is_valid_cpf(value: str | None) -> bool:
    digits = only_digits(value)

    if len(digits) != 11 or digits == digits[0] * 11:
        return False

    numbers = [int(digit) for digit in digits]

    for position in (9, 10):
        weighted = sum(numbers[index] * (position + 1 - index) for index in range(position))
        check = (weighted * 10) % 11 % 10

        if check != numbers[position]:
            return False

    return True


def display_name(user) -> str:
    """The one name every surface calls an account by, falling through what it has that is safe to put on a screen."""
    chosen = (user.nickname or "").strip()

    if chosen:
        return chosen

    full = " ".join(part for part in ((user.first_name or "").strip(), (user.last_name or "").strip()) if part)

    # A phone number and a document name the person to whoever reads them, and a whole address is one more place to write to, so of an address only the part before the at sign is drawn.
    return full or user.username or (user.email or "").split("@")[0] or f"#{user.id}"
