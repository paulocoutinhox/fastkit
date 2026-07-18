from fastkit_admin.columns import Column
from fastkit_admin.fields import (
    LookupField,
    RelationField,
    TextField,
)
from fastkit_admin.filters import (
    LookupFilter,
    SelectFilter,
)
from fastkit_admin.resource import AdminResource, Fieldset
from app.geo import (
    city_options,
    country_options,
    district_options,
    grid_delay,
    state_options,
)
from app.models import (
    GeoSample,
)


class GeoSampleAdmin(AdminResource[GeoSample]):
    name = "geo-samples"
    label = "Geo samples"
    icon = "map-pin"
    model = GeoSample

    list_columns = [
        "id",
        "name",
        "sel_country",
        "sel_state",
        "sel_city",
        Column("created_at", type="datetime"),
    ]
    search_fields = ["name"]
    ordering = ["-created_at"]

    filters = [
        Fieldset(
            "Dependent selects",
            ["sel_country", "sel_state", "sel_city", "sel_district"],
        ),
        Fieldset(
            "Dependent lookups",
            ["look_country", "look_state", "look_city", "look_district"],
        ),
        SelectFilter("sel_country", options="sel_country", label="Country (select)"),
        SelectFilter(
            "sel_state",
            options="sel_state",
            depends_on=["sel_country"],
            label="State (select)",
        ),
        SelectFilter(
            "sel_city",
            options="sel_city",
            depends_on=["sel_state"],
            label="City (select)",
        ),
        SelectFilter(
            "sel_district",
            options="sel_district",
            depends_on=["sel_city"],
            label="District (select)",
        ),
        LookupFilter("look_country", options="look_country", label="Country (lookup)"),
        LookupFilter(
            "look_state",
            options="look_state",
            depends_on=["look_country"],
            label="State (lookup)",
        ),
        LookupFilter(
            "look_city",
            options="look_city",
            depends_on=["look_state"],
            label="City (lookup)",
        ),
        LookupFilter(
            "look_district",
            options="look_district",
            depends_on=["look_city"],
            label="District (lookup)",
        ),
    ]

    form_fields = [
        TextField("name", required=True, max_length=120),
        RelationField("sel_country", label="Country (select)"),
        RelationField("sel_state", label="State (select)", depends_on=["sel_country"]),
        RelationField("sel_city", label="City (select)", depends_on=["sel_state"]),
        RelationField(
            "sel_district", label="District (select)", depends_on=["sel_city"]
        ),
        LookupField("look_country", label="Country (lookup)"),
        LookupField("look_state", label="State (lookup)", depends_on=["look_country"]),
        LookupField("look_city", label="City (lookup)", depends_on=["look_state"]),
        LookupField(
            "look_district", label="District (lookup)", depends_on=["look_city"]
        ),
    ]

    fieldsets = [
        Fieldset("Details", ["name"]),
        Fieldset(
            "Dependent selects",
            ["sel_country", "sel_state", "sel_city", "sel_district"],
            description="A four-level country → state → city → district chain, each loaded from a deliberately slow remote source.",
        ),
        Fieldset(
            "Dependent lookups",
            ["look_country", "look_state", "look_city", "look_district"],
            description="The same four-level chain rendered as autocomplete lookups.",
        ),
    ]

    permissions = {
        "list": "products.view",
        "detail": "products.view",
        "create": "products.create",
        "update": "products.update",
        "delete": "products.delete",
    }

    options_sel_country = staticmethod(country_options())
    options_sel_state = staticmethod(state_options("sel_country"))
    options_sel_city = staticmethod(city_options("sel_state"))
    options_sel_district = staticmethod(district_options("sel_city"))
    options_look_country = staticmethod(country_options())
    options_look_state = staticmethod(state_options("look_country"))
    options_look_city = staticmethod(city_options("look_state"))
    options_look_district = staticmethod(district_options("look_city"))

    async def list(self, session, query, locale="en"):
        await grid_delay()

        return await super().list(session, query, locale)
