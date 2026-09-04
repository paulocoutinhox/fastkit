"""The public site is what a crawler and a visitor both read, so every page answers whole HTML and a real status."""

import pathlib
import re
from decimal import Decimal

import pytest
from sqlalchemy import event

from helpers.db import async_engine
from tests.conftest import opened
from tests.factories import make_language, make_plan

PUBLIC = ["/", "/contact", "/plans", "/products", "/gallery", "/newsletter"]


@pytest.mark.parametrize("path", PUBLIC)
async def test_every_public_page_answers_a_whole_document(site, path):
    answer = await site.get(path)

    assert answer.status_code == 200
    assert answer.headers["content-type"].startswith("text/html")
    assert answer.text.startswith("<!doctype html>")
    assert "<h1" in answer.text


async def test_about_is_a_named_address_for_the_content_written_under_that_tag(site, db, tenant):
    """An address with a name for one tag, because `/about` is what a person types and an operator still edits it like any other page."""
    from tests.factories import make_content

    assert (await site.get("/about")).status_code == 404

    await make_content(db, tenant, tag="about", title="Who we are", content="<p>We build things.</p>")

    answer = await site.get("/about")

    assert answer.status_code == 200
    assert "Who we are" in answer.text

    # The same page at two addresses is what a crawler reads as two pages, so the other one points here.
    moved = await site.get("/content/about", follow_redirects=False)

    assert moved.status_code == 301
    assert moved.headers["location"] == "/about"


async def test_the_root_is_the_home_and_never_a_hop_to_one(site):
    answer = await site.get("/", follow_redirects=False)

    assert answer.status_code == 200
    assert "<h1" in answer.text


async def test_a_page_is_written_in_the_language_the_browser_asked_for(site):
    english = await site.get("/plans")
    portuguese = await site.get("/plans", headers={"accept-language": "pt-BR,pt;q=0.9"})

    assert "Plans" in english.text
    assert "Planos" in portuguese.text


async def test_the_language_that_was_chosen_outranks_the_one_the_browser_asked_for(site):
    site.cookies.set("fastkit_language", "en")
    answer = await site.get("/plans", headers={"accept-language": "pt-BR,pt;q=0.9"})

    assert "Plans" in answer.text


async def test_choosing_a_language_keeps_it_for_the_pages_that_come_after(site):
    token = await opened(site, "/plans")
    chosen = await site.post("/language", data={"csrf_token": token, "language": "pt", "next": "/plans"}, follow_redirects=False)

    assert chosen.status_code == 303
    assert chosen.headers["location"] == "/plans"
    assert "Planos" in (await site.get("/plans")).text


async def test_a_page_is_drawn_in_the_palette_the_browser_chose(site):
    """The server writes the class it read, so a page never draws light and then turns dark in front of the reader."""
    assert "data-theme=" not in (await site.get("/plans")).text

    site.cookies.set("fastkit_theme", "dark")

    assert 'data-theme="black"' in (await site.get("/plans")).text


async def test_choosing_a_palette_keeps_it_for_the_pages_that_come_after(site):
    token = await opened(site, "/plans")
    chosen = await site.post("/theme", data={"csrf_token": token, "theme": "dark", "next": "/plans"}, follow_redirects=False)

    assert chosen.status_code == 303
    assert chosen.headers["location"] == "/plans"
    assert 'data-theme="black"' in (await site.get("/plans")).text


async def test_one_button_carries_the_whole_choice(site):
    """It is one press from what the device says to light, from light to dark, and from dark back to the device."""
    token = await opened(site, "/plans")

    for chosen, following in (("light", "dark"), ("dark", "system"), ("system", "light")):
        await site.post("/theme", data={"csrf_token": token, "theme": chosen, "next": "/plans"}, follow_redirects=False)
        answer = await site.get("/plans")

        assert f'name="theme" value="{following}"' in answer.text


async def test_a_palette_nobody_draws_is_not_a_choice(site):
    token = await opened(site, "/plans")
    answer = await site.post("/theme", data={"csrf_token": token, "theme": "neon", "next": "/plans"})

    assert answer.status_code == 404


async def test_the_palette_outlives_the_visit_only_where_it_was_allowed_to(site):
    """A palette is a preference like the language, and a preference nobody allowed lives for this visit and no longer."""
    token = await opened(site, "/plans")
    answer = await site.post("/theme", data={"csrf_token": token, "theme": "dark", "next": "/plans"}, follow_redirects=False)

    assert "max-age" not in answer.headers["set-cookie"].lower()

    await site.post("/cookies", data={"csrf_token": await opened(site, "/cookies"), "action": "accept"}, follow_redirects=False)
    allowed = await site.post("/theme", data={"csrf_token": await opened(site, "/plans"), "theme": "light", "next": "/plans"}, follow_redirects=False)

    assert "max-age" in allowed.headers["set-cookie"].lower()


async def test_a_language_nobody_offers_is_not_a_choice(site):
    token = await opened(site, "/plans")
    answer = await site.post("/language", data={"csrf_token": token, "language": "de", "next": "/plans"})

    assert answer.status_code == 404


async def test_a_choice_never_sends_the_visitor_off_this_site(site):
    token = await opened(site, "/plans")
    answer = await site.post("/language", data={"csrf_token": token, "language": "pt", "next": "//evil.test/steal"}, follow_redirects=False)

    assert answer.headers["location"] == "/"


async def test_every_page_offers_the_languages_it_answers_in(site):
    answer = await site.get("/plans")

    assert 'action="/language"' in answer.text

    for code in ("en", "pt", "es"):
        assert f'name="language" value="{code}"' in answer.text


async def test_a_path_that_names_nothing_answers_a_drawn_page_with_the_status_of_one(site):
    answer = await site.get("/nothing-here")

    assert answer.status_code == 404
    assert "<!doctype html>" in answer.text


async def test_every_page_names_the_address_it_is_the_original_of(site):
    """The address of the page and never the one somebody arrived at, or every share with a tracking parameter is a page of its own."""
    plain = (await site.get("/plans")).text
    tracked = (await site.get("/plans", params={"utm_source": "twitter", "fbclid": "abc"})).text

    assert 'rel="canonical" href="http://acme.test/plans"' in plain
    assert 'rel="canonical" href="http://acme.test/plans"' in tracked
    assert 'property="og:url" content="http://acme.test/plans"' in tracked


async def test_the_home_carries_what_a_search_engine_reads_about_the_organization(site, tenant):
    answer = await site.get("/")

    assert '<script type="application/ld+json">' in answer.text
    assert f'"name": "{tenant.name}"' in answer.text


async def test_the_site_never_reveals_where_the_panel_is(site):
    from helpers.settings import settings

    for path in PUBLIC:
        assert settings.admin_path.strip("/") not in (await site.get(path)).text


async def test_a_content_answers_by_its_tag(site, db, tenant):
    from tests.factories import make_content

    await make_content(db, tenant, title="Terms of use", tag="terms", content="<p>What you agree to.</p>")

    answer = await site.get("/content/terms")

    assert answer.status_code == 200
    assert "Terms of use" in answer.text
    assert "What you agree to." in answer.text


async def test_a_tag_no_content_carries_is_not_a_page(site):
    assert (await site.get("/content/nothing")).status_code == 404


async def test_a_gallery_answers_every_photo_it_holds(site, db, tenant):
    from tests.factories import make_gallery, make_gallery_photo

    gallery = await make_gallery(db, tenant, title="Our office", tag="office")
    await make_gallery_photo(db, gallery, caption="Reception", position=0)

    listed = await site.get("/gallery")
    read = await site.get("/gallery/office")

    assert "Our office" in listed.text
    assert "Reception" in read.text


async def test_a_gallery_page_costs_the_same_however_many_galleries_there_are(site, db, tenant):
    """A cover read per gallery is a query per gallery on the two pages a crawler reads most."""
    from tests.factories import make_gallery, make_gallery_photo

    counted = []

    def count(*arguments):
        counted.append(1)

    event.listen(async_engine.sync_engine, "before_cursor_execute", count)

    try:
        for index in range(2):
            await make_gallery_photo(db, await make_gallery(db, tenant, tag=f"few-{index}"), position=0)

        counted.clear()
        await site.get("/gallery")
        few = len(counted)

        for index in range(12):
            await make_gallery_photo(db, await make_gallery(db, tenant, tag=f"many-{index}"), position=0)

        counted.clear()
        await site.get("/gallery")
        many = len(counted)
    finally:
        event.remove(async_engine.sync_engine, "before_cursor_execute", count)

    assert few == many


async def test_a_product_answers_by_its_slug(site, db, tenant):
    from tests.factories import make_product

    await make_product(db, tenant, name="The Handbook", slug="handbook")

    listed = await site.get("/products")
    read = await site.get("/products/handbook")

    assert "The Handbook" in listed.text
    assert read.status_code == 200
    assert (await site.get("/products/nothing")).status_code == 404


async def test_the_plans_are_offered_with_what_they_cost(site, db, tenant):
    from tests.factories import make_plan

    await make_plan(db, tenant, name="Monthly")

    answer = await site.get("/plans")

    assert "Monthly" in answer.text
    assert "19.90" in answer.text


async def test_robots_points_at_the_sitemap(site):
    answer = await site.get("/robots.txt")

    assert answer.status_code == 200
    assert "Sitemap: http://acme.test/sitemap.xml" in answer.text


async def test_every_page_that_answers_the_same_to_everybody_is_offered_to_a_crawler(site, db, tenant):
    """A page nothing lists is a page nothing finds, and the newsletter and the cookie policy were both missing."""
    from tests.factories import make_content

    body = (await site.get("/sitemap.xml")).text

    for path in ("/", "/contact", "/plans", "/products", "/gallery", "/newsletter", "/cookies"):
        assert f"<loc>http://acme.test{path}</loc>" in body, path

    assert "<loc>http://acme.test/about</loc>" not in body, "nothing was written under that tag yet"

    await make_content(db, tenant, tag="about")

    assert "<loc>http://acme.test/about</loc>" in (await site.get("/sitemap.xml")).text


async def test_the_sitemap_lists_every_public_page_once(site, db, tenant):
    from tests.factories import make_content, make_product

    await make_content(db, tenant, tag="terms")
    await make_product(db, tenant, slug="handbook")

    answer = await site.get("/sitemap.xml")

    assert answer.headers["content-type"].startswith("application/xml")
    assert answer.text.count("<loc>http://acme.test/plans</loc>") == 1
    assert "<loc>http://acme.test/content/about</loc>" not in answer.text
    assert answer.text.count("<loc>http://acme.test/content/terms</loc>") == 1
    assert answer.text.count("<loc>http://acme.test/products/handbook</loc>") == 1
    assert "hreflang" not in answer.text
    assert len(re.findall(r"<url>", answer.text)) == len(re.findall(r"</url>", answer.text))


async def test_a_host_no_tenant_answers_for_is_not_a_site(app, db, tenant, monkeypatch):
    """An instance that names no default is one where the host has to match, and a host that matches nothing has no site."""
    from httpx import ASGITransport, AsyncClient

    from helpers.settings import settings

    monkeypatch.setattr(settings.site, "default_tenant", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://nobody.test") as client:
        answer = await client.get("/")

    assert answer.status_code == 404


async def test_a_tenant_name_can_never_close_the_script_block_it_is_written_into(site, db, tenant):
    """The organization is JSON rendered inside a script tag, and a name carrying a closing tag would turn the rest of the page into markup."""
    tenant.name = "Acme </script><img src=x onerror=alert(1)>"
    await db.commit()

    body = (await site.get("/")).text

    assert "</script><img" not in body
    assert "\\u003c/script\\u003e" in body


async def test_a_page_named_after_the_admin_is_still_a_page_of_the_site(site):
    """The admin owns its own path and not every path that starts like it, so `/administrators` is a page and never a json error."""
    answer = await site.get("/administrators")

    assert answer.status_code == 404
    assert "text/html" in answer.headers["content-type"]


@pytest.mark.parametrize("path, marked", [("/plans", "site.plans"), ("/products", "site.products"), ("/gallery", "site.gallery"), ("/contact", "site.contact")])
async def test_the_menu_marks_the_section_the_reader_is_in(site, path, marked):
    answer = await site.get(path)
    current = re.findall(r'<a href="([^"]+)"[^>]*aria-current="page"', answer.text)

    assert current == [path]


async def test_a_page_below_a_section_marks_that_section(site):
    """A product is read inside products, so the menu says where the reader is and not only which address they typed."""
    answer = await site.get("/gallery/office")

    assert 'href="/gallery" class="transition hover:text-primary text-primary" aria-current="page"' in answer.text


async def test_the_home_marks_nothing_of_the_menu(site):
    """Every page is below the home, so it is the one address that only marks itself, which is the name in the corner."""
    answer = await site.get("/")
    current = re.findall(r'<a href="([^"]+)"[^>]*aria-current="page"', answer.text)

    assert current == ["/"]


async def test_a_page_no_menu_item_opens_marks_none_of_them(site):
    answer = await site.get("/cookies")

    assert 'aria-current="page"' not in answer.text


async def test_the_name_in_the_corner_is_marked_only_on_the_home(site):
    assert 'aria-current="page"' not in (await site.get("/plans")).text.split("<nav")[0]


async def test_the_menu_marks_the_account_of_whoever_is_reading_it(signed_in):
    answer = await signed_in.get("/account/purchases")
    current = re.findall(r'<a href="([^"]+)"[^>]*aria-current="page"', answer.text)

    assert current == ["/account"]


async def test_signing_in_is_marked_while_it_is_the_page_being_read(site):
    answer = await site.get("/account/login")

    assert 'href="/account/login"' in answer.text
    assert 'aria-current="page"' in answer.text


async def test_the_plans_page_is_priced_in_the_currency_of_whoever_reads_it(site, db, tenant):
    """The same plan is sold once per market, and the page draws the one written for the reader."""
    english = await make_language(db, code_iso_639_1="en", name="English")
    portuguese = await make_language(db, code_iso_639_1="pt", name="Português")

    await make_plan(db, tenant, language_id=english.id, name="Monthly", currency="USD", price=Decimal("19.90"))
    await make_plan(db, tenant, language_id=portuguese.id, name="Mensal", currency="BRL", price=Decimal("99.90"))

    brazilian = await site.get("/plans", headers={"accept-language": "pt-BR,pt;q=0.9"})

    # The amount is written the way somebody reading this language writes one, which is what the comma is doing here.
    assert "BRL 99,90" in brazilian.text
    assert "USD" not in brazilian.text

    reader = await site.get("/plans", headers={"accept-language": "en"})

    assert "USD 19.90" in reader.text
    assert "BRL" not in reader.text


def test_every_piece_a_page_is_built_from_is_one_a_page_uses():
    """A piece nothing is shaped like is a piece nobody maintains, and the markup it would give ends up copied instead."""
    partials = list(pathlib.Path("templates/global/site/partials").glob("*.html"))
    declared = {found.group(1) for path in partials for found in re.finditer(r"\{%\s*macro\s+(\w+)\(", path.read_text())}
    everything = [path.read_text() for path in pathlib.Path("templates").rglob("*.html")]

    # A piece drawn by a page or by another piece is drawn, and the declaration itself is the one mention a piece nothing calls has.
    unused = sorted(name for name in declared if sum(len(re.findall(rf"\b{name}\(", body)) for body in everything) <= 1)

    assert len(declared) > 10, "the guard read too few pieces to claim anything"
    assert unused == [], f"these are declared and nothing is shaped like them: {unused}"


def test_the_surface_of_a_card_is_written_once():
    """Changing the look of a card has to be one edit, which is the whole reason the piece exists."""
    piece = pathlib.Path("templates/global/site/partials/ui.html").read_text()

    # The shape refused is read off the piece itself, because one copied into the guard is one that outlives what the piece gives.
    given = re.search(r"\{% macro card\([^)]*\) %\}\s*(<section class=\"[^\"{]+)", piece)

    assert given is not None, "the card piece is not shaped the way this guard reads it"

    shape = given.group(1).strip()
    pages = [path for path in pathlib.Path("templates/global/site").rglob("*.html") if "partials" not in str(path)]

    # A card of another element or with a margin of its own is another thing, so only the very shape the piece gives is refused.
    copied = [str(path) for path in pages if shape in path.read_text()]

    assert copied == [], f"these draw the card by hand instead of calling it: {copied}"


@pytest.mark.parametrize("path", ["/account/login", "/account/signup", "/account/password-recovery", "/contact", "/newsletter", "/cookies"])
async def test_every_control_of_a_form_is_named_by_a_label(site, path):
    """A legend names a group and a label names a control, and a reader who cannot see the page hears only the second."""
    body = (await site.get(path)).text
    controls = re.findall(r'<(?:input|select|textarea)\b(?![^>]*type="hidden")[^>]*\bid="([^"]+)"', body)
    labelled = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', body))
    anonymous = re.findall(r'<(?:input|select|textarea)\b(?![^>]*type="hidden")(?![^>]*\bid=)(?![^>]*aria-label)[^>]*>', body)

    assert controls, f"{path} draws no control this reads"
    assert [name for name in controls if name not in labelled] == []
    assert anonymous == [], f"{path} draws a control with neither an id nor a label"


async def test_a_control_the_page_refused_says_so_and_points_at_why(site):
    """A red border is the half a reader who cannot see the page never gets, so the control says it was refused and names the message that says why."""
    body = (await site.post("/account/signup", data={"csrf_token": await opened(site, "/account/signup"), "first_name": "A", "email": "not-an-address", "password": "short"})).text

    refused = re.findall(r'<(?:input|select|textarea)\b[^>]*\baria-invalid="true"[^>]*>', body)
    named = set(re.findall(r'<span\b[^>]*\bid="([^"]+)"', body))

    assert len(refused) >= 2, f"the page refused nothing this reads, so it proves nothing: {len(refused)}"

    for control in refused:
        described = re.search(r'aria-describedby="([^"]+)"', control)

        assert described is not None, f"a refused control names no message: {control[:120]}"
        assert described.group(1) in named, f"a refused control points at a message the page never drew: {described.group(1)}"


@pytest.mark.parametrize("path", ["/", "/plans", "/contact", "/nothing-here"])
async def test_a_keyboard_reaches_the_content_without_walking_the_whole_menu(site, path):
    """Every page draws the same six links before the content, and a keyboard would walk them all on every one of them."""
    body = (await site.get(path)).text

    assert body.index('href="#content"') < body.index("<header"), f"{path} draws the skip before nothing"
    assert 'id="content"' in body, f"{path} names a place to skip to and does not draw it"


def linked(body: str) -> set:
    """Every address of this site the page points a reader at, which is what a crawler follows and a person clicks."""
    from urllib.parse import urlsplit

    found = set()

    for raw in re.findall(r'href="([^"]+)"', body) + re.findall(r'src="([^"]+)"', body):
        parts = urlsplit(raw)

        if parts.scheme or parts.netloc or raw.startswith(("#", "mailto:", "data:")):
            continue

        found.add(parts.path)

    return found


async def test_every_address_the_site_points_at_answers(site, db, tenant):
    """A dead link on a site that exists to be found is the cheapest defect to have and the dearest not to see."""
    from xml.etree import ElementTree

    from tests.factories import make_content, make_content_category, make_gallery, make_product

    category = await make_content_category(db)
    await make_content(db, tenant, category_id=category.id, tag="about")
    await make_gallery(db, tenant)
    await make_product(db, tenant)
    await db.commit()

    seen = {}
    queue = ["/"]

    while queue:
        path = queue.pop(0)

        if path in seen or path.startswith(("/media/", "/static/", "/account", "/checkout")):
            continue

        answer = await site.get(path, follow_redirects=False)
        seen[path] = answer.status_code

        assert answer.status_code < 400, f"{path} answers {answer.status_code} and a page of this site points at it"

        if answer.status_code < 300 and "html" in answer.headers.get("content-type", ""):
            queue += sorted(linked(answer.text))

    listed = ElementTree.fromstring((await site.get("/sitemap.xml")).text)
    addresses = [node.text for node in listed.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]

    assert len(seen) >= 10, "the walk read too few pages to claim anything"
    assert len(addresses) >= 8, "the sitemap named too few addresses to claim anything"

    for address in addresses:
        path = address.split(tenant.domain, 1)[-1]

        assert (await site.get(path, follow_redirects=False)).status_code == 200, f"the sitemap names {path} and it does not answer"


async def test_the_sitemap_never_names_a_page_that_only_exists_once_somebody_wrote_it(site, db, tenant):
    """A fresh installation has no content, and offering a crawler an address that answers 404 is worse than offering none."""
    from xml.etree import ElementTree

    listed = ElementTree.fromstring((await site.get("/sitemap.xml")).text)
    addresses = [node.text.split(tenant.domain, 1)[-1] for node in listed.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]

    assert len(addresses) >= 6, "the sitemap named too few addresses to claim anything"

    for path in addresses:
        assert (await site.get(path, follow_redirects=False)).status_code == 200, f"nothing was written yet and the sitemap already names {path}"


@pytest.mark.parametrize("language", ["en", "pt", "es"])
async def test_every_public_page_is_drawn_whole_in_every_language_this_instance_offers(site, db, tenant, language):
    """A translation naming a placeholder the caller does not pass raises for the readers of that language and for nobody else."""
    from tests.factories import make_content, make_gallery, make_language, make_product

    offered = await make_language(db, code_iso_639_1=language) if language != "en" else None
    await make_content(db, tenant, tag="about", language_id=offered.id if offered else None)
    await make_gallery(db, tenant, language_id=offered.id if offered else None)
    await make_product(db, tenant)
    await db.commit()

    for path in [*PUBLIC, "/about", "/cookies"]:
        answer = await site.get(path, headers={"Accept-Language": language})

        assert answer.status_code == 200, f"{path} answers {answer.status_code} in {language}"
        assert answer.text.startswith("<!doctype html>"), path


async def test_an_instance_no_brand_answers_for_says_so_where_an_operator_reads_it(app, caplog):
    """Every page is dark in this state, so the answer stays quiet and the log is what names the host nothing matched."""
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://nobody.example") as stranger:
        with caplog.at_level("WARNING"):
            answer = await stranger.get("/")

    assert answer.status_code == 404
    assert "nobody.example" not in answer.text
    assert any("no active brand answers for nobody.example" in record.getMessage() for record in caplog.records)


async def test_a_content_with_nothing_written_in_it_draws_a_page_and_not_the_word_none(site, db, tenant):
    """The body is what a page is, and it is optional at the form, so the page has to read as empty rather than as a value."""
    from tests.factories import make_content

    await make_content(db, tenant, title="Bare", tag="bare", content=None)

    answer = await site.get("/content/bare")

    assert answer.status_code == 200
    assert "Bare" in answer.text
    assert ">None<" not in answer.text
    assert "prose" not in answer.text


async def test_the_site_publishes_the_address_it_declares_and_never_the_host_it_was_asked_by(app, tenant):
    """Every absolute address a crawler reads comes from the brand, so a request naming another host cannot make the site say it lives there."""
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://10.0.3.7") as stranger:
        page = await stranger.get("/plans")
        robots = await stranger.get("/robots.txt")
        listed = await stranger.get("/sitemap.xml")
        home = await stranger.get("/")

    assert page.status_code == 200
    assert "10.0.3.7" not in page.text
    assert f'rel="canonical" href="http://{tenant.domain}/plans"' in page.text
    assert f'property="og:url" content="http://{tenant.domain}/plans"' in page.text
    assert robots.text.strip().endswith(f"Sitemap: http://{tenant.domain}/sitemap.xml")
    assert "10.0.3.7" not in listed.text
    assert f"<loc>http://{tenant.domain}/</loc>" in listed.text
    assert f'"url": "http://{tenant.domain}/"' in home.text


async def test_a_host_no_brand_answers_for_is_offered_no_crawler_file_either(app):
    """These two say where this site lives, so an instance that is not a site has neither to give."""
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://nobody.example") as stranger:
        assert (await stranger.get("/robots.txt")).status_code == 404
        assert (await stranger.get("/sitemap.xml")).status_code == 404


async def test_a_page_that_breaks_is_still_a_page_and_never_a_body_written_for_a_client(app, tenant, monkeypatch):
    """A visitor reads pages, so a bug on one of them cannot answer the shape an application parses."""
    from httpx import ASGITransport, AsyncClient

    from services.content import content_service

    async def broken(*arguments, **options):
        raise RuntimeError("something a bug would do")

    monkeypatch.setattr(content_service, "find_by_tag", broken)

    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url=f"http://{tenant.domain}") as visitor:
        page = await visitor.get("/content/anything")
        answered = await visitor.get("/api/content/anything")

    assert page.status_code == 500
    assert page.headers["content-type"].startswith("text/html")
    assert page.text.startswith("<!doctype html>")
    assert "error.internal" not in page.text

    # What a client parses is still what a client gets, because the shape of an answer belongs to who reads it.
    assert answered.headers["content-type"].startswith("application/json")


async def test_every_address_the_signed_in_area_points_at_answers(signed_in, db, tenant, member):
    """The walk that proves the site has no dead link starts at the home, and the half a reader only sees once signed in was left out of it."""
    from tests.factories import make_currency, make_plan, make_product, make_purchase, make_subscription

    product = await make_product(db, tenant)
    await make_purchase(db, tenant, member, product)
    await make_subscription(db, tenant, member, await make_plan(db, tenant))
    await make_currency(db, tenant)
    await db.commit()

    seen = {}
    queue = ["/account"]

    while queue:
        path = queue.pop(0)

        if path in seen or path.startswith(("/media/", "/static/", "/account/logout")):
            continue

        answer = await signed_in.get(path, follow_redirects=False)
        seen[path] = answer.status_code

        assert answer.status_code < 400, f"{path} answers {answer.status_code} and a page of the account points at it"

        if answer.status_code < 300 and "html" in answer.headers.get("content-type", ""):
            queue += sorted(linked(answer.text))

    assert len(seen) >= 15, f"the walk read only {len(seen)} pages of the account, so it is proving nothing"
