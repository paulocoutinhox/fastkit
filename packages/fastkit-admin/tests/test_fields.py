from datetime import date, datetime
from decimal import Decimal

import pytest

from fastkit_core.errors.exceptions import ValidationError
from fastkit_admin.fields import (
    BooleanField,
    DateField,
    DateTimeField,
    DecimalField,
    EmailField,
    NumberField,
    PasswordField,
    SelectField,
    TextField,
)


def test_text_field_schema_and_validation():
    field = TextField("name", required=True, max_length=5)
    schema = field.to_schema()

    assert schema["type"] == "text"
    assert schema["max_length"] == 5

    field.validate("abc")

    with pytest.raises(ValidationError):
        field.validate("")

    with pytest.raises(ValidationError):
        field.validate("too-long-value")


def test_text_field_default_label():
    assert TextField("first_name").label == "First Name"


def test_email_field_type():
    assert EmailField("email").field_type == "email"


def test_password_field_is_write_only():
    assert PasswordField("password").write_only is True


def test_boolean_field_parse_and_format():
    field = BooleanField("active")

    assert field.parse_value("true") is True
    assert field.parse_value("0") is False
    assert field.parse_value(True) is True
    assert field.format_value(1) is True
    field.validate(None)


def test_number_field():
    field = NumberField("age")

    assert field.parse_value("42") == 42
    assert field.parse_value("") is None

    with pytest.raises(ValidationError):
        field.parse_value("abc")


def test_decimal_field():
    field = DecimalField("price", decimal_places=2)

    assert field.format_value(Decimal("1234.5"), "pt") == "1.234,50"
    assert field.format_value(None) is None
    assert field.parse_value("1.234,50", "pt") == Decimal("1234.50")
    assert field.parse_value("") is None

    with pytest.raises(ValidationError):
        field.parse_value("abc")


def test_date_field():
    field = DateField("due")

    assert field.format_value(date(2026, 7, 14), "pt") == "14/07/2026"
    assert field.format_value(None) is None
    assert field.parse_value("2026-07-14") == date(2026, 7, 14)
    assert field.parse_value("") is None

    with pytest.raises(ValidationError):
        field.parse_value("bad")


def test_datetime_field():
    field = DateTimeField("at")

    assert field.format_value(datetime(2026, 7, 14, 9, 5), "en") == "07/14/2026 09:05"
    assert field.format_value(None) is None
    assert field.parse_value("2026-07-14 09:05") == datetime(2026, 7, 14, 9, 5)
    assert field.parse_value("") is None

    with pytest.raises(ValidationError):
        field.parse_value("bad")


def test_select_field():
    field = SelectField(
        "status", choices=[("a", "Active"), ("i", "Inactive")], required=True
    )
    schema = field.to_schema()

    assert schema["choices"][0] == {"value": "a", "label": "Active"}
    field.validate("a")

    with pytest.raises(ValidationError):
        field.validate("x")

    with pytest.raises(ValidationError):
        field.validate("")


def test_temporal_and_decimal_fields_reject_non_string_input():
    from fastkit_admin.fields import TimeField

    for field in (DateField("d"), DateTimeField("dt"), TimeField("t")):
        with pytest.raises(ValidationError):
            field.parse_value([])

        with pytest.raises(ValidationError):
            field.parse_value(123)

    decimal_field = DecimalField("price")

    assert decimal_field.parse_value(9) == Decimal("9")

    with pytest.raises(ValidationError):
        decimal_field.parse_value(True)

    with pytest.raises(ValidationError):
        decimal_field.parse_value([])


def test_select_fields_reject_unhashable_values():
    from fastkit_admin.fields import MultiSelectField

    select = SelectField("status", choices=[("a", "Active")])

    with pytest.raises(ValidationError):
        select.validate([])

    multi = MultiSelectField("tags", choices=[("a", "A")])

    with pytest.raises(ValidationError):
        multi.validate([["nested"]])


def test_base_field_passthrough():
    field = TextField("note")

    assert field.format_value("x") == "x"
    assert field.parse_value("x") == "x"


def test_time_field():
    from datetime import time

    from fastkit_admin.fields import TimeField

    field = TimeField("start")

    assert field.format_value(time(9, 5), "en") == "09:05"
    assert field.format_value(None) is None
    assert field.parse_value("09:05") == time(9, 5)
    assert field.parse_value("") is None

    with pytest.raises(ValidationError):
        field.parse_value("nope")


def test_richtext_field_sanitizes():
    from fastkit_admin.fields import RichTextField

    field = RichTextField(
        "body",
        upload_url="/admin/api/uploads",
        sanitizer=lambda html: html.replace("<script>", ""),
    )
    schema = field.to_schema()

    assert schema["type"] == "richtext"
    assert schema["upload_url"] == "/admin/api/uploads"
    assert field.parse_value("<p>ok</p><script>") == "<p>ok</p>"
    assert field.parse_value("") == ""


def test_richtext_sanitizes_by_default():
    from fastkit_admin.fields import RichTextField

    cleaned = RichTextField("body").parse_value(
        '<p>ok</p><img src=x onerror="alert(1)"><script>alert(1)</script>'
    )

    assert "<p>ok</p>" in cleaned
    assert "onerror" not in cleaned
    assert "<script>" not in cleaned


def test_richtext_explicit_none_sanitizer_opts_out():
    from fastkit_admin.fields import RichTextField

    field = RichTextField("body", sanitizer=None)

    assert field.parse_value("<script>raw</script>") == "<script>raw</script>"


def test_json_field():
    from fastkit_admin.fields import JsonField

    field = JsonField("meta")

    assert field.format_value({"a": 1}) == '{\n  "a": 1\n}'
    assert field.format_value(None) is None
    assert field.parse_value('{"a": 1}') == {"a": 1}
    assert field.parse_value({"already": "dict"}) == {"already": "dict"}
    assert field.parse_value("") is None

    with pytest.raises(ValidationError):
        field.parse_value("{invalid")


def test_multiselect_field():
    from fastkit_admin.fields import MultiSelectField

    field = MultiSelectField("tags", choices=[("a", "A"), ("b", "B")], required=True)
    schema = field.to_schema()

    assert schema["choices"][0] == {"value": "a", "label": "A"}
    assert field.parse_value(["a", "b"]) == ["a", "b"]
    assert field.parse_value("") == []

    with pytest.raises(ValidationError):
        field.parse_value(5)

    field.validate(["a"])

    with pytest.raises(ValidationError):
        field.validate([])

    with pytest.raises(ValidationError):
        field.validate(["x"])


def test_relation_field():
    from fastkit_admin.fields import RelationField

    field = RelationField("owner_id")
    dependent = RelationField("subcategory_id", depends_on=["category_id"])

    assert field.to_schema()["depends_on"] == []
    assert dependent.to_schema()["depends_on"] == ["category_id"]
    assert field.parse_value("42") == 42
    assert field.parse_value("") is None
    assert field.format_value(7) == 7
    assert field.format_value(None) is None

    with pytest.raises(ValidationError):
        field.parse_value("not-an-int")


def test_color_field():
    from fastkit_admin.fields import ColorField

    field = ColorField("brand")

    field.validate("#4f46e5")
    field.validate(None)

    with pytest.raises(ValidationError):
        field.validate("red")


def test_image_and_file_fields():
    from fastkit_admin.fields import FileField, ImageField

    image = ImageField("avatar", upload_url="/u")
    file = FileField("doc", upload_url="/u")

    assert image.to_schema()["upload_url"] == "/u"
    assert file.to_schema()["type"] == "file"


def test_hide_label_flag_in_schema():
    from fastkit_admin.fields import TextField

    assert TextField("name").to_schema()["hide_label"] is False
    assert TextField("name", hide_label=True).to_schema()["hide_label"] is True


def test_email_field_validation():
    from fastkit_core.errors.exceptions import ValidationError
    from fastkit_admin.fields import EmailField

    field = EmailField("email")
    field.validate("a@b.co")
    field.validate("")

    with pytest.raises(ValidationError):
        field.validate("not-an-email")


def test_url_field_validation():
    from fastkit_core.errors.exceptions import ValidationError
    from fastkit_admin.fields import URLField

    field = URLField("site")
    field.validate("https://example.com/path")

    with pytest.raises(ValidationError):
        field.validate("ftp://nope")


def test_masked_field_validation_and_schema():
    from fastkit_core.errors.exceptions import ValidationError
    from fastkit_admin.fields import MaskedField

    field = MaskedField(
        "cpf", mask="###.###.###-##", pattern=r"\d{3}\.\d{3}\.\d{3}-\d{2}"
    )
    schema = field.to_schema()

    assert schema["type"] == "masked"
    assert schema["mask"] == "###.###.###-##"

    field.validate("123.456.789-00")

    with pytest.raises(ValidationError):
        field.validate("123")


def test_lookup_field_schema():
    from fastkit_admin.fields import LookupField

    field = LookupField(
        "owner_id",
        depends_on=["team_id"],
        min_chars=2,
        initial_limit=3,
        search_limit=25,
    )
    schema = field.to_schema()

    assert schema["type"] == "lookup"
    assert schema["depends_on"] == ["team_id"]
    assert schema["min_chars"] == 2
    assert schema["initial_limit"] == 3
    assert schema["search_limit"] == 25


def test_lookup_field_schema_defaults():
    from fastkit_admin.fields import LookupField

    schema = LookupField("owner_id").to_schema()

    assert schema["min_chars"] == 0
    assert schema["initial_limit"] == 10
    assert schema["search_limit"] == 20


def test_translations_field_schema():
    from fastkit_admin.fields import TranslationsField

    field = TranslationsField(
        "translations",
        languages_url="/content/languages",
        value_url="/content/{id}/translations",
        save_url="/content/{id}/translations",
    )
    schema = field.to_schema()

    assert field.virtual is True
    assert schema["type"] == "translations"
    assert schema["languages_url"] == "/content/languages"


def test_permission_matrix_field_schema():
    from fastkit_admin.fields import PermissionMatrixField

    field = PermissionMatrixField(
        "permissions_matrix",
        groups_url="/meta/permissions",
        value_url="/roles/{id}/permissions",
        save_url="/roles/{id}/permissions",
    )
    schema = field.to_schema()

    # the matrix is virtual, so it is never persisted as a model column
    assert field.virtual is True
    assert schema["type"] == "permission_matrix"
    assert schema["virtual"] is True
    assert schema["groups_url"] == "/meta/permissions"
    assert schema["value_url"] == "/roles/{id}/permissions"
    assert schema["save_url"] == "/roles/{id}/permissions"
