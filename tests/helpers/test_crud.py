import pytest

from helpers.crud import coerce
from models.tenant import Tenant
from models.user import User


@pytest.mark.parametrize("raw,expected", [("true", True), ("1", True), ("yes", True), ("false", False), ("0", False), ("no", False), ("", None)])
def test_a_boolean_filter_reads_the_usual_spellings(raw, expected):
    assert coerce(Tenant.active, raw) is expected


@pytest.mark.parametrize("raw,expected", [("7", 7), ("-7", -7), ("", None)])
def test_a_numeric_filter_only_accepts_digits(raw, expected):
    assert coerce(User.tenant_id, raw) == expected


@pytest.mark.parametrize("column,raw", [(Tenant.active, "maybe"), (User.tenant_id, "seven")])
def test_a_value_the_column_cannot_read_is_refused_and_never_dropped(column, raw):
    """Dropping it answers the whole list to somebody who believes the filter was applied."""
    with pytest.raises(ValueError):
        coerce(column, raw)


def test_a_text_filter_is_taken_as_it_is():
    assert coerce(Tenant.code, "acme") == "acme"
