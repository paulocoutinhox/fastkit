from enums.content_audience import ContentAudience
from models.content_group import ContentGroup
from models.user_group import UserGroup
from models.user_group_member import UserGroupMember
from tests.factories import make_content, make_tenant, save


async def members_only(db, tenant, member=None):
    """A page opened to one group, and that group holding the reader when one is given."""
    content = await make_content(db, tenant, title="Insider", tag="insider", audience=ContentAudience.MEMBERS)
    group = await save(db, UserGroup(code="insiders", name="Insiders", tenant_id=tenant.id))
    await save(db, ContentGroup(content_id=content.id, group_id=group.id))

    if member is not None:
        await save(db, UserGroupMember(group_id=group.id, user_id=member.id))

    return group


async def test_a_page_for_everyone_is_read_by_a_visitor_with_no_session(site, db, tenant):
    await make_content(db, tenant, title="Open", tag="open")

    answer = await site.get("/content/open")

    assert answer.status_code == 200
    assert "Open" in answer.text


async def test_a_page_for_signed_in_readers_sends_a_visitor_to_sign_in_and_back(site, db, tenant):
    await make_content(db, tenant, title="Inside", tag="inside", audience=ContentAudience.SIGNED_IN)

    answer = await site.get("/content/inside")

    assert answer.status_code == 303
    assert answer.headers["location"] == "/account/login?next=%2Fcontent%2Finside"


async def test_a_page_for_signed_in_readers_is_read_by_any_account(signed_in, db, tenant):
    await make_content(db, tenant, title="Inside", tag="inside", audience=ContentAudience.SIGNED_IN)

    assert (await signed_in.get("/content/inside")).status_code == 200


async def test_a_page_for_a_group_is_read_by_its_members_and_does_not_exist_for_anybody_else(signed_in, db, tenant, member):
    group = await members_only(db, tenant)

    assert (await signed_in.get("/content/insider")).status_code == 404

    await save(db, UserGroupMember(group_id=group.id, user_id=member.id))

    assert (await signed_in.get("/content/insider")).status_code == 200


async def test_a_page_for_a_group_that_names_no_group_is_read_by_nobody_and_never_sends_anybody_to_sign_in(site, signed_in, client, db, tenant, tenant_headers):
    await make_content(db, tenant, title="Nobody", tag="nobody", audience=ContentAudience.MEMBERS)

    assert (await signed_in.get("/content/nobody")).status_code == 404

    signed_in.cookies.clear()

    assert (await site.get("/content/nobody")).status_code == 404
    assert (await client.get("/api/contents/by-tag/nobody", headers=tenant_headers)).status_code == 404


async def test_a_group_of_a_brand_never_takes_the_code_of_a_group_every_brand_reaches(client, db, tenant, admin_headers):
    """A page opened to a group of no brand would otherwise be read by the members of a group a brand named the same."""
    await save(db, UserGroup(code="vip", name="VIP"))

    answer = await client.post("/api/user-groups", json={"name": "VIP", "tenantId": tenant.id}, headers=admin_headers)

    assert answer.status_code == 409
    assert answer.json()["errors"]["code"]


async def test_the_sitemap_offers_only_the_pages_anybody_reads(site, db, tenant):
    await make_content(db, tenant, title="Open", tag="open")
    await make_content(db, tenant, title="Inside", tag="inside", audience=ContentAudience.SIGNED_IN)

    body = (await site.get("/sitemap.xml")).text

    assert "/content/open" in body
    assert "/content/inside" not in body


async def test_the_api_answers_a_page_by_its_audience(client, db, tenant, member, tenant_headers, member_headers):
    await members_only(db, tenant, member)

    anonymous = await client.get("/api/contents/by-tag/insider", headers=tenant_headers)
    reader = await client.get("/api/contents/by-tag/insider", headers=tenant_headers | member_headers)

    assert anonymous.status_code == 401
    assert reader.status_code == 200
    assert reader.json()["audience"] == "members"
    assert "groups" not in reader.json()


async def test_the_api_hides_a_page_from_a_signed_in_reader_it_is_not_drawn_for(client, db, tenant, tenant_headers, member_headers):
    await members_only(db, tenant)

    assert (await client.get("/api/contents/by-tag/insider", headers=tenant_headers | member_headers)).status_code == 404


async def test_a_page_of_one_brand_is_opened_only_to_a_group_that_brand_reaches(client, db, tenant, admin_headers):
    other = await make_tenant(db, code="other", domain="other.test")
    content = await make_content(db, tenant, title="Insider", tag="insider", audience=ContentAudience.MEMBERS)
    foreign = await save(db, UserGroup(code="theirs", name="Theirs", tenant_id=other.id))
    shared = await save(db, UserGroup(code="everybody", name="Everybody"))

    refused = await client.post("/api/content-groups", json={"contentId": content.id, "groupId": foreign.id}, headers=admin_headers)
    accepted = await client.post("/api/content-groups", json={"contentId": content.id, "groupId": shared.id}, headers=admin_headers)

    assert refused.status_code == 422
    assert refused.json()["errors"]["groupId"]
    assert accepted.status_code == 201
    assert accepted.json()["group"]["code"] == "everybody"
