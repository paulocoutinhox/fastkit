import pytest_asyncio
from sqlalchemy import select

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_tenancy.app import TenancyApp
from fastkit_accounts.app import AccountsApp
from fastkit_auth.app import AuthApp
from fastkit_permissions.app import PermissionsApp
from fastkit_i18n.app import I18nApp
from fastkit_admin.app import AdminApp
from fastkit_admin.filters import (
    BooleanFilter,
    ChoiceFilter,
    DateRangeFilter,
    ExactFilter,
    MultiChoiceFilter,
    NumberFilter,
    TextFilter,
)
from fastkit_admin.site import AdminSite


def _compiled(query):
    return str(query.compile(compile_kwargs={"literal_binds": True}))


def test_text_filter(product_model):
    base = select(product_model)

    assert "WHERE" not in _compiled(TextFilter("name").apply(base, product_model, ""))
    assert (
        "lower"
        in _compiled(TextFilter("name").apply(base, product_model, "abc")).lower()
    )


def test_exact_filter(product_model):
    base = select(product_model)

    assert "WHERE" not in _compiled(
        ExactFilter("category").apply(base, product_model, "")
    )
    assert "= 'x'" in _compiled(ExactFilter("category").apply(base, product_model, "x"))


def test_boolean_filter(product_model):
    base = select(product_model)

    assert "WHERE" not in _compiled(
        BooleanFilter("is_active").apply(base, product_model, "")
    )

    truthy = _compiled(BooleanFilter("is_active").apply(base, product_model, "true"))
    falsy = _compiled(BooleanFilter("is_active").apply(base, product_model, "false"))

    assert "is_active" in truthy and "WHERE" in truthy
    assert "is_active" in falsy and truthy != falsy


def test_number_filter(product_model):
    base = select(product_model)

    assert "WHERE" not in _compiled(
        NumberFilter("price").apply(base, product_model, "")
    )
    assert "= 10" in _compiled(NumberFilter("price").apply(base, product_model, 10))


def test_choice_filter(product_model):
    filt = ChoiceFilter("category", choices=[("a", "A"), ("b", "B")])
    base = select(product_model)

    assert filt.to_schema()["choices"][0] == {"value": "a", "label": "A"}
    assert "WHERE" not in _compiled(filt.apply(base, product_model, ""))
    assert "= 'a'" in _compiled(filt.apply(base, product_model, "a"))


def test_string_column_filters_skip_a_non_scalar_value(product_model):
    base = select(product_model)

    # a range/list shape (e.g. filter[category][from]=x) on an equality/choice/multichoice filter over a
    # string column must be skipped, never compiled into `column == {...}` which would 500 at the driver
    assert "WHERE" not in _compiled(
        ExactFilter("category").apply(base, product_model, {"from": "x"})
    )
    assert "WHERE" not in _compiled(
        ChoiceFilter("category", choices=[("a", "A")]).apply(
            base, product_model, {"from": "x"}
        )
    )
    assert "WHERE" not in _compiled(
        MultiChoiceFilter("category", choices=[("a", "A")]).apply(
            base, product_model, {"from": "x"}
        )
    )


def test_date_range_filter(product_model):
    filt = DateRangeFilter("created_at")
    base = select(product_model)

    assert "WHERE" not in _compiled(filt.apply(base, product_model, None))
    assert "WHERE" not in _compiled(filt.apply(base, product_model, {}))

    both = _compiled(
        filt.apply(base, product_model, {"from": "2026-01-01", "to": "2026-12-31"})
    )
    assert ">=" in both and "<=" in both

    only_from = _compiled(filt.apply(base, product_model, {"from": "2026-01-01"}))
    assert ">=" in only_from

    only_to = _compiled(filt.apply(base, product_model, {"to": "2026-12-31"}))
    assert "<=" in only_to

    empty_range = _compiled(filt.apply(base, product_model, {"other": "x"}))
    assert "WHERE" not in empty_range

    flat_value = _compiled(filt.apply(base, product_model, "abc"))
    assert "WHERE" not in flat_value


def test_coerce_for_column_by_type():
    from datetime import date, datetime, time
    from decimal import Decimal

    from sqlalchemy import (
        Boolean,
        Column,
        Date,
        DateTime,
        Float,
        Integer,
        Numeric,
        String,
        Time,
    )

    from fastkit_admin.filters import _SKIP, _coerce_for_column

    assert _coerce_for_column(Column("x", Integer()), "5") == 5
    assert _coerce_for_column(Column("x", Float()), "1.5") == 1.5
    assert _coerce_for_column(Column("x", Numeric()), "2.5") == Decimal("2.5")
    assert _coerce_for_column(Column("x", Boolean()), "true") is True
    assert _coerce_for_column(Column("x", Date()), "2026-01-02") == date(2026, 1, 2)
    assert _coerce_for_column(Column("x", Time()), "10:30:00") == time(10, 30)
    assert _coerce_for_column(
        Column("x", DateTime()), "2026-01-02T10:30:00"
    ) == datetime(2026, 1, 2, 10, 30)
    assert _coerce_for_column(Column("x", String()), "kept") == "kept"
    assert _coerce_for_column(Column("x", Integer()), 7) == 7
    assert _coerce_for_column(Column("x", Integer()), "bad") is _SKIP
    # a non-scalar (a range/list shape) is skipped on any column type, including string, so it never reaches the driver
    assert _coerce_for_column(Column("x", String()), {"from": "a"}) is _SKIP
    assert _coerce_for_column(Column("x", String()), ["a", "b"]) is _SKIP


def test_coerce_for_column_falls_back_when_no_python_type():
    from fastkit_admin.filters import _coerce_for_column

    class _NoType:
        @property
        def python_type(self):
            raise NotImplementedError

    class _Column:
        type = _NoType()

    assert _coerce_for_column(_Column(), "as-is") == "as-is"


def test_typed_filters_ignore_unparseable_values(product_model):
    from fastkit_admin.filters import NumberFilter

    base = select(product_model)

    assert "WHERE" not in _compiled(
        NumberFilter("price").apply(base, product_model, "abc")
    )
    assert "12.5" in _compiled(NumberFilter("price").apply(base, product_model, "12.5"))
    assert ">=" in _compiled(
        DateRangeFilter("created_at").apply(
            base, product_model, {"from": "2026-01-01", "to": "bad"}
        )
    )


def test_multichoice_filter_drops_unparseable_entries(product_model):
    from fastkit_admin.filters import MultiChoiceFilter

    base = select(product_model)
    flt = MultiChoiceFilter("price", choices=[("1", "One")])

    assert "WHERE" not in _compiled(flt.apply(base, product_model, ["abc"]))


def test_base_filter_is_noop(product_model):
    from fastkit_admin.filters import Filter

    base = select(product_model)

    assert _compiled(Filter("name").apply(base, product_model, "x")) == _compiled(base)


def test_filter_schema():
    assert TextFilter("name", label="Name").to_schema() == {
        "field": "name",
        "type": "text",
        "label": "Name",
    }


class Settings:
    class app:
        name = "Demo"
        environment = "test"
        secret_key = "demo-secret"

    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        echo = False

    class auth:
        password_min_length = 12
        password_max_length = 128
        jwt_algorithm = "HS256"
        access_token_ttl_seconds = 3600
        max_failed_logins = 5
        lockout_seconds = 900
        rate_limit_per_minute = 10

        class captcha:
            provider = "disabled"
            site_key = ""
            secret_key = ""
            action = "admin_login"
            minimum_score = 0.5
            allowed_hostnames = []
            timeout_seconds = 5
            image_length = 5
            challenge_ttl_seconds = 300

    class admin:
        enabled = True
        path = "/admin"
        api_path = "/admin/api"
        theme = "tabler"
        page_size = 25
        page_size_options = [10, 25]

    class i18n:
        default_locale = "en"
        supported_locales = ["en", "pt", "es"]

    installed_apps = [
        "fastkit.core",
        "fastkit.db",
        "fastkit.tenancy",
        "fastkit.accounts",
        "fastkit.auth",
        "fastkit.permissions",
        "fastkit.i18n",
        "fastkit.admin",
    ]


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {
            "fastkit.core": CoreApp,
            "fastkit.db": DbApp,
            "fastkit.tenancy": TenancyApp,
            "fastkit.accounts": AccountsApp,
            "fastkit.auth": AuthApp,
            "fastkit.permissions": PermissionsApp,
            "fastkit.i18n": I18nApp,
            "fastkit.admin": AdminApp,
        },
    )
    runtime = Runtime(settings=Settings(), installed_apps=list(Settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_admin_app_registers_site(runtime):
    site = runtime.component("admin_site")

    assert isinstance(site, AdminSite)
    assert site.api_path == "/admin/api"


def test_date_time_datetime_filters(product_model):
    from fastkit_admin.filters import DateFilter, DateTimeFilter, TimeFilter

    base = select(product_model)

    for filter_cls in (DateFilter, TimeFilter, DateTimeFilter):
        flt = filter_cls("created_at")
        assert "WHERE" not in _compiled(flt.apply(base, product_model, ""))
        assert "created_at" in _compiled(flt.apply(base, product_model, "2026-01-01"))


def test_enum_filter(product_model):
    from fastkit_admin.filters import EnumFilter

    flt = EnumFilter("category", choices=[("a", "A"), ("b", "B")])
    base = select(product_model)

    assert flt.to_schema()["choices"][0] == {"value": "a", "label": "A"}
    assert "WHERE" not in _compiled(flt.apply(base, product_model, ""))
    assert "= 'a'" in _compiled(flt.apply(base, product_model, "a"))


def test_multichoice_filter(product_model):
    from fastkit_admin.filters import MultiChoiceFilter

    flt = MultiChoiceFilter("category", choices=[("a", "A"), ("b", "B")])
    base = select(product_model)

    assert flt.to_schema()["choices"][1]["value"] == "b"
    assert "WHERE" not in _compiled(flt.apply(base, product_model, []))
    assert "IN" in _compiled(flt.apply(base, product_model, ["a", "b"])).upper()
    assert "IN" in _compiled(flt.apply(base, product_model, "a")).upper()


def test_select_filter(product_model):
    from fastkit_admin.filters import SelectFilter

    flt = SelectFilter(
        "category",
        choices=[("a", "A")],
        options="category_options",
        depends_on=["parent"],
    )
    base = select(product_model)
    schema = flt.to_schema()

    assert schema["type"] == "select"
    assert schema["choices"] == [{"value": "a", "label": "A"}]
    assert schema["options"] == "category_options"
    assert schema["depends_on"] == ["parent"]
    assert "WHERE" not in _compiled(flt.apply(base, product_model, ""))
    assert "= 'a'" in _compiled(flt.apply(base, product_model, "a"))


def test_lookup_filter(product_model):
    from fastkit_admin.filters import LookupFilter

    flt = LookupFilter(
        "category",
        options="category_options",
        depends_on=["parent"],
        min_chars=2,
        initial_limit=5,
        search_limit=15,
    )
    base = select(product_model)
    schema = flt.to_schema()

    assert schema["type"] == "lookup"
    assert schema["options"] == "category_options"
    assert schema["depends_on"] == ["parent"]
    assert schema["min_chars"] == 2
    assert schema["initial_limit"] == 5
    assert schema["search_limit"] == 15
    assert "WHERE" not in _compiled(flt.apply(base, product_model, ""))
    assert "= 'a'" in _compiled(flt.apply(base, product_model, "a"))
