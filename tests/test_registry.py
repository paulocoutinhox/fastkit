"""The registry is what fills the metadata, so a table it forgets is a table no database ever gets."""

import models.registry
from helpers.db import Base


def test_every_mapped_model_is_named_by_the_registry():
    mapped = {mapper.class_.__name__ for mapper in Base.registry.mappers}

    assert mapped - set(models.registry.__all__) == set(), "a model missing here is a table create_schema never creates"


def test_everything_the_registry_names_is_a_model_it_imported():
    """The name lived in `__all__` without the import, and `from models.registry import *` would have failed on it."""
    missing = [name for name in models.registry.__all__ if not hasattr(models.registry, name)]

    assert missing == []
