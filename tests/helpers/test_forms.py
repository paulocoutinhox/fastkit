import pathlib
import pkgutil
import re
from importlib import import_module

import pytest
from pydantic import BaseModel

import routes.site
from helpers.forms import validated


def site_schemas() -> list[type[BaseModel]]:
    """What the site validates a form with, read from the calls themselves so a schema declared elsewhere is read too."""
    found = {}

    for module in pkgutil.iter_modules(routes.site.__path__):
        loaded = import_module(f"routes.site.{module.name}")
        source = pathlib.Path(loaded.__file__).read_text()

        for name in re.findall(r"validated\((\w+),", source):
            model = getattr(loaded, name)
            found[model.__name__] = model

    return [found[name] for name in sorted(found)]


def test_the_suite_reads_every_form_the_site_validates_with():
    assert len(site_schemas()) >= 8


@pytest.mark.parametrize("model", site_schemas(), ids=lambda model: model.__name__)
def test_a_page_marks_the_field_by_the_name_it_drew_the_input_with(model: type[BaseModel]):
    """The wire name is camelCase and the input the page drew is not, so a refusal keyed by the alias is never shown."""
    refused = validated(model, {name: "x" * 400 for name in model.model_fields})[1]

    assert refused
    assert set(refused) <= set(model.model_fields)
