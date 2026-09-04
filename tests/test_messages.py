"""Every catalog and the code say the same thing, or a message rots into a key nobody sees until a screen shows it raw."""

import json
import re
from pathlib import Path

from enums.consent import ConsentCategory
from helpers.settings import settings
from routes.meta import CATALOG

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ("services", "helpers", "routes", "models", "schemas", "jobs", "enums")

KEY = re.compile(r"[\"']((?:error|validation|email|site)\.[a-z0-9-]+)[\"']")


def catalog(language: str) -> dict:
    return json.loads((ROOT / "locale" / f"{language}.json").read_text(encoding="utf-8"))


# What the consent page is handed rather than writing down, which is checked by walking the categories instead. The necessary one is written on the page itself, because nobody is asked about it.
BUILT = {key for category in ConsentCategory if category != ConsentCategory.NECESSARY for key in (f"site.cookies-{category}", f"site.cookies-{category}-lead")}


def written(language: str) -> set[str]:
    """The labels of an enum are asked for by a key built at render time, so they answer to their own check."""
    return {key for key in catalog(language) if not key.startswith("enum.") and key not in BUILT}


def asked_for() -> set[str]:
    """What the code and the templates name, which together are every place a key is written."""
    files = [path for folder in SOURCE for path in (ROOT / folder).rglob("*.py")] + list((ROOT / "templates").rglob("*.html"))

    # A key a page builds from a value reaches here as the half that was written down, and it answers to its own check.
    return {key for path in files for key in KEY.findall(path.read_text(encoding="utf-8")) if not key.endswith("-")}


def test_every_catalog_carries_exactly_the_same_keys():
    """A language this instance offers with a key the others have is a page that answers half in the wrong one."""
    english = set(catalog("en"))
    missing = {language: sorted(english.symmetric_difference(catalog(language))) for language in settings.languages}

    assert missing == {language: [] for language in settings.languages}


def test_every_key_the_code_names_is_a_message_every_catalog_has():
    """A key with no message reaches the client raw, and the client shows it to a reader as it is."""
    assert sorted(asked_for() - written("en")) == []


def test_no_catalog_carries_a_message_nothing_names():
    """A rule that was removed leaves its message behind, and the next reader takes it for something that still happens."""
    assert sorted(written("en") - asked_for()) == []


def test_every_enum_value_the_api_publishes_is_named_in_every_catalog():
    """A page builds the key from the value, so one a catalog never learned reaches the reader as the raw word the database stores."""
    missing = []

    for language in settings.languages:
        named = catalog(language)
        missing += [f"{language}: enum.{name}.{member.value}" for name, enum in CATALOG.items() for member in enum if f"enum.{name}.{member.value}" not in named]

    assert missing == []


def test_no_catalog_names_an_enum_value_the_api_no_longer_publishes():
    published = {f"enum.{name}.{member.value}" for name, enum in CATALOG.items() for member in enum}
    orphans = []

    for language in settings.languages:
        orphans += [f"{language}: {key}" for key in catalog(language) if key.startswith("enum.") and key not in published]

    assert orphans == []


def test_every_category_a_visitor_is_asked_about_is_named_and_explained():
    """The page builds these keys from the categories the environment offers, so nothing else would catch one that is missing."""
    missing = []

    for language in settings.languages:
        named = catalog(language)
        missing += [f"{language}: {key}" for category in ConsentCategory for key in (f"site.cookies-{category}", f"site.cookies-{category}-lead") if key not in named]

    assert missing == []


def test_no_catalog_explains_a_category_that_is_not_one():
    """A category removed from the enum leaves its explanation behind, and the next reader takes it for one somebody is asked about."""
    explained = re.compile(r"^site\.cookies-(.+)-lead$")
    named = {str(category) for category in ConsentCategory}
    orphans = []

    for language in settings.languages:
        found = ((key, explained.match(key)) for key in catalog(language))
        orphans += [f"{language}: {key}" for key, match in found if match and match.group(1) not in named]

    assert orphans == []


def test_every_message_names_the_same_values_in_every_language():
    """A caller passes one set of values, so a translation naming another is a KeyError for whoever reads that language."""
    slots = re.compile(r"\{(\w+)\}")
    catalogs = {language: catalog(language) for language in settings.languages}
    differing, counted = [], 0

    for key in sorted(catalogs[settings.default_language]):
        shapes = {language: frozenset(slots.findall(written.get(key, ""))) for language, written in catalogs.items()}
        counted += 1

        if len(set(shapes.values())) > 1:
            differing.append(f"{key}: " + ", ".join(f"{language}={sorted(named)}" for language, named in sorted(shapes.items())))

    assert counted >= 300, f"the scan read only {counted} messages, so it is proving nothing"
    assert differing == [], f"these name different values in different languages: {differing}"
