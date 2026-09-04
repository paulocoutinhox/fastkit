import asyncio
import importlib
import pkgutil
import re
from pathlib import Path
from xml.etree import ElementTree

import pytest
from sqlalchemy import func, select

from enums.upload import UploadPurpose
from helpers.errors import NotFoundError, ValidationError
from helpers.pagination import PageParams
from models.commerce import Product
from models.gallery import Gallery, GalleryPhoto
from models.subscription import Subscription
from models.tenant import Tenant
from services.commerce import product_service
from services.content import content_service
from services.crud import CrudService
from services.subscription import plan_service
from services.tenant import tenant_service
from tests.factories import make_benefit, make_entitlement, make_gallery, make_gallery_photo, make_plan, make_plan_entitlement, make_product, make_stored_file, make_subscription


async def test_get_raises_when_the_record_does_not_exist(db):
    with pytest.raises(NotFoundError):
        await tenant_service.get(db, 999999)


async def test_find_answers_nothing_when_the_record_does_not_exist(db):
    assert await tenant_service.find(db, 999999) is None


async def test_pagination_walks_the_result(db, tenant):
    for index in range(5):
        await tenant_service.create(db, {"name": f"Tenant {index}", "domain": f"t{index}.example.org"})

    total, first = await tenant_service.paginate(db, PageParams(limit=2, offset=0))
    _unused, second = await tenant_service.paginate(db, PageParams(limit=2, offset=2))

    assert total == 6
    assert len(first) == 2
    assert {item.id for item in first} & {item.id for item in second} == set()


async def test_a_filter_the_service_does_not_declare_is_ignored(db, tenant):
    total, _unused = await tenant_service.paginate(db, PageParams(), {"name": "nothing"})

    assert total == 1


async def test_lookup_labels_the_options(db, tenant):
    options = await tenant_service.lookup(db, None, 10)

    assert options == [{"id": tenant.id, "label": "Acme - acme"}]


async def test_lookup_narrows_by_search(db, tenant):
    assert await tenant_service.lookup(db, "acm", 10) != []
    assert await tenant_service.lookup(db, "nothing", 10) == []


async def test_build_label_falls_back_to_the_id(db):
    class Anonymous(CrudService):
        label_fields = ("missing",)

    class Row:
        id = 7
        missing = None

    assert Anonymous().build_label(Row()) == "#7"


async def test_apply_slug_keeps_an_untouched_code_on_an_edit(db, tenant):
    prepared = await tenant_service.prepare({"name": "Renamed"}, tenant)

    assert "code" not in prepared


async def test_apply_slug_regenerates_a_cleared_code(db, tenant):
    prepared = await tenant_service.prepare({"code": "", "name": "Renamed"}, tenant)

    assert prepared["code"] == "renamed"


async def test_apply_slug_falls_back_when_there_is_no_source(db):
    prepared = await tenant_service.prepare({"code": ""}, None)

    assert prepared["code"] == "tenant"


async def test_apply_slug_never_writes_more_than_the_column_holds(db, tenant):
    prepared = await plan_service.prepare({"tenant_id": tenant.id, "name": "meu plano enorme " * 20}, None)

    assert len(prepared["code"]) <= 64


@pytest.mark.parametrize("typed,stored", [("a&b<c", "a-b-c"), ("com/barra", "com-barra"), ("with space", "with-space"), ("Com Maiuscula", "com-maiuscula"), ("under_score", "under-score"), ("../../etc", "etc")])
async def test_a_typed_value_is_a_slug_exactly_like_a_derived_one(db, tenant, typed, stored):
    """What is typed reaches an address, a storage key and a template folder, so it is cut the same way a derived one is."""
    assert (await tenant_service.prepare({"code": typed, "name": "Whatever"}, None))["code"] == stored


async def test_a_typed_tag_never_makes_the_sitemap_unreadable(site, db, tenant, client, admin_headers):
    """One tag carrying an ampersand made the whole file unparseable, for every crawler and every page of the site."""
    created = await client.post("/api/contents", json={"tenantId": tenant.id, "title": "T", "tag": "a&b<c", "content": "x", "active": True}, headers=admin_headers)

    assert created.json()["tag"] == "a-b-c"

    ElementTree.fromstring((await site.get("/sitemap.xml")).text)


async def test_a_typed_tag_opens_the_page_the_listing_points_at(site, db, tenant, client, admin_headers):
    """A tag carrying a slash was listed by the card and answered nothing at the address that card opened."""
    await client.post("/api/contents", json={"tenantId": tenant.id, "title": "T", "tag": "com/barra", "content": "x", "active": True}, headers=admin_headers)

    assert (await site.get("/content/com-barra")).status_code == 200


async def test_a_long_name_produces_a_code_the_contract_accepts(client, tenant, admin_headers):
    name = "meu sadlksads d" * 12

    created = await client.post("/api/plans", json={"tenantId": tenant.id, "name": name, "resumeDeliveryPolicy": "same_cycle"}, headers=admin_headers)

    assert created.status_code == 201
    assert len(created.json()["code"]) <= 64

    # The record it wrote is one it can read back and save again.
    reopened = created.json()
    updated = await client.put(f"/api/plans/{reopened['id']}", json={"code": reopened["code"], "name": name}, headers=admin_headers)

    assert updated.status_code == 200


def capturing(monkeypatch) -> list[str]:
    """What the pass asked the storage to drop, in the order it asked."""
    removed = []

    async def capture(key):
        removed.append(key)

    monkeypatch.setattr("services.upload.storage.delete", capture)

    return removed


async def test_deleting_a_parent_takes_the_files_of_its_children(db, tenant, monkeypatch):
    removed = capturing(monkeypatch)

    image = await make_stored_file(db, UploadPurpose.PRODUCT_IMAGE, "images/product")
    asset = await make_stored_file(db, UploadPurpose.PRODUCT_FILE, "files/product", "pdf")
    photo = await make_stored_file(db, UploadPurpose.GALLERY_PHOTO, "images/gallery")

    await make_product(db, tenant, image=image, file=asset)
    await make_gallery_photo(db, await make_gallery(db, tenant), image=photo)

    await tenant_service.delete(db, tenant.id)

    assert sorted(removed) == sorted([image, asset, photo])


async def test_deleting_a_record_takes_the_file_its_markup_embedded(db, tenant, monkeypatch):
    """The editor writes a link inside the body rather than a key into a column, and a file is a file however the row came to mention it."""
    removed = capturing(monkeypatch)
    drawing = await make_stored_file(db, UploadPurpose.IMAGE, "images/content", "png")

    content = await content_service.create(db, {"title": "A Page", "tag": "a-page", "content": f'<p><img src="/media/{drawing}"></p>', "tenant_id": tenant.id})

    await content_service.delete(db, content.id)

    assert removed == [drawing]


async def test_a_body_that_stops_mentioning_a_file_discards_it(db, tenant, monkeypatch):
    """A picture the operator took out of the page is a picture nothing points at, and nothing else would ever come looking for it."""
    removed = capturing(monkeypatch)
    drawing = await make_stored_file(db, UploadPurpose.IMAGE, "images/content", "png")

    content = await content_service.create(db, {"title": "A Page", "tag": "a-page", "content": f'<p><img src="/media/{drawing}"></p>', "tenant_id": tenant.id})

    await content_service.update(db, content.id, {"content": "<p>no picture any more</p>"})

    assert removed == [drawing]


async def test_replacing_a_file_discards_the_previous_one(db, tenant, monkeypatch):
    removed = capturing(monkeypatch)

    first = await make_stored_file(db, UploadPurpose.PRODUCT_IMAGE, "images/product")
    second = await make_stored_file(db, UploadPurpose.PRODUCT_IMAGE, "images/product")
    product = await make_product(db, tenant, image=first)

    await product_service.update(db, product.id, {"image": second})

    assert removed == [first]


def test_every_declared_filter_resolves_to_something_the_table_has():
    """A filter naming a column that was dropped only fails when somebody uses it, which is the worst moment to find out."""
    import importlib
    import pathlib

    for path in sorted(pathlib.Path("services").glob("*.py")):
        if path.stem != "__init__":
            importlib.import_module(f"services.{path.stem}")

    broken = []
    checked = 0

    for service in every_service():
        if service.model is None:
            continue

        for name in service.filter_fields:
            checked += 1

            try:
                service().filter_column(name)
            except Exception:
                broken.append(f"{service.__name__}.{name}")

    assert checked >= 50, f"the scan resolved only {checked} filters, so it is proving nothing"
    assert broken == []


def every_service(base=CrudService) -> list:
    """The whole tree and not one level of it, because a base of its own is what a tagged resource subclasses."""
    return [subclass for child in base.__subclasses__() for subclass in (child, *every_service(child))]


def services_by_model() -> dict:
    for module in pkgutil.iter_modules(["services"]):
        if module.name != "seed":
            importlib.import_module(f"services.{module.name}")

    return {subclass.model: subclass for subclass in every_service() if getattr(subclass, "model", None) is not None}


def test_every_column_the_panel_writes_markup_into_is_a_column_its_service_reads():
    """A file lives inside the markup an editor writes, so a field the panel authors and the service does not read is a file nothing ever discards."""
    authored = re.findall(r'html\("([a-zA-Z]+)"', "\n".join(path.read_text() for path in Path("webapps/admin/src/resources").glob("*.js")))
    declared = {name for service in services_by_model().values() for name in service.markup_fields}

    assert len(authored) >= 5, f"the sweep found {len(authored)} editor fields, so it is proving nothing"
    assert sorted(set(authored) - declared) == [], "the panel authors markup into a column no service reads a file out of"


def unknown_columns(dependents, path: str) -> list[str]:
    found = []

    for dependent in dependents:
        where = f"{path}/{dependent.model.__name__}"

        if not hasattr(dependent.model, dependent.field):
            found.append(f"{where}.{dependent.field}")

        found += unknown_columns(dependent.dependents or (), where)

    return found


def test_every_dependent_names_a_column_its_model_still_has():
    """A column that was renamed leaves the cascade pointing at nothing, and the parent stops being deletable at all."""
    missing = []

    for service in services_by_model().values():
        missing += unknown_columns(getattr(service, "dependents", ()), service.__name__)
        missing += [f"{service.__name__}.{name}" for name in service.file_fields if not hasattr(service.model, name)]

    assert missing == []


def contradicted(dependents, path: str) -> list[str]:
    found = []

    for dependent in dependents:
        where = f"{path}/{dependent.model.__name__}"
        table = dependent.model.__table__
        key = next((fk for fk in table.foreign_keys if fk.parent.name == dependent.field), None)

        if key is not None and (key.ondelete or "").upper() != "CASCADE":
            found.append(f"{where}.{dependent.field} says {key.ondelete}")

        found += contradicted(dependent.dependents or (), where)

    return found


def test_every_child_a_service_deletes_is_a_child_the_database_would_delete_too():
    """A service deleting what its foreign key declares RESTRICT is walking around its own declaration, and one of the two is wrong."""
    owners = services_by_model()
    walked = 0
    contradictions = []

    for service in owners.values():
        walked += len(getattr(service, "dependents", ()))
        contradictions += contradicted(getattr(service, "dependents", ()), service.__name__)

    assert walked > 20
    assert contradictions == []


async def test_deleting_a_tenant_takes_the_whole_tree_it_owns(db, tenant, member, monkeypatch):
    """The cascade names its columns by string, so a rename only shows up when a tenant that owns one is deleted."""
    monkeypatch.setattr("services.upload.storage.delete", lambda key: asyncio.sleep(0))

    gallery = await make_gallery(db, tenant)

    await make_gallery_photo(db, gallery)
    await make_product(db, tenant)

    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)

    await make_plan_entitlement(db, plan, entitlement)
    await make_benefit(db, entitlement)
    await make_subscription(db, tenant, member, plan)

    await tenant_service.delete(db, tenant.id)

    for model in (Tenant, Product, Gallery, GalleryPhoto, Subscription):
        assert await db.scalar(select(func.count()).select_from(model)) == 0, model.__name__


async def test_paging_a_column_full_of_ties_answers_every_row_once(db, tenant):
    """A database is free to order ties however it likes, so without the key a row lands on two pages and another on none."""
    from helpers.pagination import PageParams
    from services.commerce import product_service
    from tests.factories import make_product

    for index in range(6):
        await make_product(db, tenant, name="Same name", position=0, slug=f"tied-{index}")

    seen = []

    for offset in (0, 2, 4):
        _, page = await product_service.paginate(db, PageParams(limit=2, offset=offset, ordering="name"), {"tenant_id": tenant.id})
        seen += [product.id for product in page]

    assert len(seen) == 6
    assert len(set(seen)) == 6


async def test_a_lookup_full_of_ties_never_offers_the_same_option_twice(db, tenant):
    from services.commerce import product_service
    from tests.factories import make_product

    for index in range(4):
        await make_product(db, tenant, name="Same name", slug=f"tied-lookup-{index}")

    options = await product_service.lookup(db, None, 4, {"tenant_id": tenant.id})

    assert len({option["id"] for option in options}) == 4


@pytest.mark.parametrize("key", ["images/banner/2026/08/19/other.webp", "../../data/app.db", "files/product/2026/08/19/thing.pdf", "anything"])
async def test_a_file_key_of_another_purpose_is_refused(db, tenant, key):
    """The column is the target of the next deletion, so a key pointing elsewhere erases whatever it points at on the following save."""
    with pytest.raises(ValidationError):
        await product_service.create(db, {"tenant_id": tenant.id, "name": "Deck", "slug": "deck", "image": key})


async def test_a_file_key_of_its_own_purpose_goes_through(db, tenant):
    created = await product_service.create(db, {"tenant_id": tenant.id, "name": "Deck", "slug": "deck", "image": "images/product/2026/08/19/deck.webp", "file": "files/product/2026/08/19/deck.pdf"})

    assert created.image == "images/product/2026/08/19/deck.webp"


async def test_a_deletion_a_key_refuses_is_a_conflict_and_never_a_crash(db, tenant, member):
    """The statement a foreign key refuses is often a child of this one, and a refusal that escapes the commit answers 500."""
    from enums.subscription import BenefitCadence, BenefitStatus, BenefitType
    from helpers.dates import now
    from helpers.errors import ConflictError
    from models.subscription import SubscriptionBenefit, UserEntitlement
    from services.subscription import entitlement_service
    from tests.factories import make_benefit, make_entitlement, make_plan, make_subscription, save

    entitlement = await make_entitlement(db, tenant)
    benefit = await make_benefit(db, entitlement)
    plan = await make_plan(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan)
    right = await save(db, UserEntitlement(subscription_id=subscription.id, entitlement_id=entitlement.id, meta={}))
    await save(db, SubscriptionBenefit(subscription_id=subscription.id, benefit_id=benefit.id, user_entitlement_id=right.id, status=BenefitStatus.ACTIVE, benefit_type=BenefitType.ACCESS, target="member", quantity=1, cadence=BenefitCadence.ON_ACTIVATION, anchor_at=now(), meta={}))

    with pytest.raises(ConflictError) as refused:
        await entitlement_service.delete(db, entitlement.id)

    assert refused.value.code == "error.record-still-referenced"


async def test_a_refused_deletion_leaves_the_file_of_the_row_that_survived(db, tenant):
    """A file goes only once the row that named it is gone, because a refused deletion leaves the row pointing at nothing otherwise."""
    from enums.subscription import BenefitType
    from helpers.errors import ConflictError
    from helpers.storage import storage
    from services.commerce import product_service
    from tests.factories import make_benefit, make_entitlement, make_product

    product = await make_product(db, tenant)
    key = await storage.save("images/product/2024/01/01/kept.webp", b"bytes", "image/webp")
    product.image = key
    await db.commit()

    entitlement = await make_entitlement(db, tenant)
    await make_benefit(db, entitlement, type=BenefitType.PRODUCT, product_id=product.id, target="handbook")

    with pytest.raises(ConflictError) as refused:
        await product_service.delete(db, product.id)

    assert refused.value.code == "error.record-still-referenced"
    # The rollback expired every object of the session, so the key is the one read before the refusal.
    assert await storage.read(key) == b"bytes"


def test_every_localised_resource_is_unique_on_the_key_it_is_addressed_by():
    """That key is an address, so two rows sharing it inside one language leave one of them open by nothing."""
    import models.registry  # noqa

    from services.crud import LocalizedService

    def descendants(base):
        for child in base.__subclasses__():
            yield child
            yield from descendants(child)

    wanted = [service for service in descendants(LocalizedService) if getattr(service, "model", None) is not None and service.localized_key]
    missing = []

    def covered(index, table) -> set:
        """A functional index reads back as `coalesce(column, :bind)` and a plain one as `table.column`, and the column is what either of them is about."""
        return {re.sub(r"^coalesce\(|,.*$|\)$", "", str(expression)).replace(f"{table.name}.", "") for expression in index.expressions}

    for service in wanted:
        table = service.model.__table__
        parts = {"tenant_id", service.localized_key} | ({"language_id"} if "language_id" in table.columns else set())

        if not any(index.unique and covered(index, table) == parts for index in table.indexes):
            missing.append(f"{service.__name__}: {table.name} is not unique on {sorted(parts)}")

    assert len(wanted) >= 3
    assert missing == []
