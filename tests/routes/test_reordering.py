"""The order an operator drags into place is written in one go, because a unique index refuses a swap done row by row."""

from sqlalchemy import select

from models.gallery import GalleryPhoto
from tests.factories import make_gallery, make_gallery_photo, make_product


async def photos(db, gallery):
    db.expunge_all()
    statement = select(GalleryPhoto.caption, GalleryPhoto.position).where(GalleryPhoto.gallery_id == gallery.id).order_by(GalleryPhoto.position)

    return [(caption, position) for caption, position in (await db.execute(statement)).all()]


async def test_reordering_photos_rewrites_every_position(client, db, admin_headers):
    """The photo carries a unique index over its position, so this is the case a row by row swap cannot do."""
    gallery = await make_gallery(db)
    filed = [await make_gallery_photo(db, gallery, caption=caption, position=position) for position, caption in enumerate(("One", "Two", "Three"))]

    response = await client.put("/api/gallery-photos/order", json={"ids": [filed[2].id, filed[0].id, filed[1].id]}, headers=admin_headers)

    assert response.status_code == 200
    assert [photo["caption"] for photo in response.json()] == ["Three", "One", "Two"]
    assert await photos(db, gallery) == [("Three", 0), ("One", 1), ("Two", 2)]


async def test_reordering_answers_the_records_in_their_new_order(client, db, tenant, admin_headers):
    gallery = await make_gallery(db, tenant)
    filed = [await make_gallery_photo(db, gallery, caption=f"Photo {index}", position=index) for index in range(3)]

    response = await client.put("/api/gallery-photos/order", json={"ids": [filed[1].id, filed[2].id, filed[0].id]}, headers=admin_headers)

    assert [photo["id"] for photo in response.json()] == [filed[1].id, filed[2].id, filed[0].id]

    db.expunge_all()

    assert [photo.position for photo in (await db.execute(select(GalleryPhoto).order_by(GalleryPhoto.position))).scalars()] == [0, 1, 2]


async def test_reordering_a_record_that_does_not_exist_is_not_found(client, db, tenant, admin_headers):
    photo = await make_gallery_photo(db, await make_gallery(db, tenant))

    assert (await client.put("/api/gallery-photos/order", json={"ids": [photo.id, 999999]}, headers=admin_headers)).status_code == 404


async def test_a_resource_with_no_position_offers_no_reordering(client, admin_headers):
    """The route is built from what the service declares, so a resource without an order never grows one."""
    assert (await client.put("/api/users/order", json={"ids": [1]}, headers=admin_headers)).status_code == 422


async def test_reordering_needs_the_administrator(client, db, tenant, member_headers):
    photo = await make_gallery_photo(db, await make_gallery(db, tenant))

    assert (await client.put("/api/gallery-photos/order", json={"ids": [photo.id]}, headers=member_headers)).status_code == 403


async def test_a_product_is_reordered_the_same_way(client, db, tenant, admin_headers):
    """The factory builds the route from `position_field`, so every resource that declares one answers the same call."""
    filed = [await make_product(db, tenant, name=f"Product {index}", position=index) for index in range(3)]

    response = await client.put("/api/products/order", json={"ids": [filed[2].id, filed[1].id, filed[0].id]}, headers=admin_headers)

    assert [product["id"] for product in response.json()] == [filed[2].id, filed[1].id, filed[0].id]


async def test_two_photos_may_sit_on_the_same_position(client, db, admin_headers):
    """A position that repeats decides nothing on its own, so refusing it stopped a photo from being added at all."""
    gallery = await make_gallery(db)

    first = await client.post("/api/gallery-photos", json={"galleryId": gallery.id, "image": "images/gallery/2026/08/19/one.webp", "position": 0}, headers=admin_headers)
    second = await client.post("/api/gallery-photos", json={"galleryId": gallery.id, "image": "images/gallery/2026/08/19/two.webp", "position": 0}, headers=admin_headers)

    assert first.status_code == 201
    assert second.status_code == 201

    listed = await client.get(f"/api/gallery-photos?galleryId={gallery.id}", headers=admin_headers)

    assert [row["id"] for row in listed.json()["items"]] == [first.json()["id"], second.json()["id"]]
