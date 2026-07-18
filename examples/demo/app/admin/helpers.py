from sqlalchemy import select

from app.models import (
    Category,
    Subcategory,
)

IMAGE_UPLOAD_URL = "/api/uploads/image"

FILE_UPLOAD_URL = "/api/uploads/file"

STATUS_CHOICES = [
    ("draft", "Draft"),
    ("published", "Published"),
    ("archived", "Archived"),
]

TAG_CHOICES = [
    ("new", "New"),
    ("sale", "Sale"),
    ("featured", "Featured"),
    ("limited", "Limited"),
]

STATUS_TONES = {
    "succeeded": "green",
    "running": "azure",
    "retrying": "yellow",
    "pending": "secondary",
    "failed": "red",
    "cancelled": "secondary",
}


def lookup_limit(params):
    return max(1, min(int(params.get("limit", 20)), 50))


async def category_options(session, params, locale):
    query = select(Category).where(Category.is_active.is_(True))

    if params.get("value"):
        query = query.where(Category.id == int(params["value"]))
    elif params.get("q"):
        query = query.where(Category.name.ilike(f"%{params['q']}%"))

    rows = (
        (
            await session.execute(
                query.order_by(Category.name).limit(lookup_limit(params))
            )
        )
        .scalars()
        .all()
    )

    return [{"value": row.id, "label": row.name} for row in rows]


async def subcategory_options(session, params, locale):
    if params.get("value"):
        rows = (
            (
                await session.execute(
                    select(Subcategory).where(Subcategory.id == int(params["value"]))
                )
            )
            .scalars()
            .all()
        )

        return [{"value": row.id, "label": row.name} for row in rows]

    category_id = params.get("category_id")

    if not category_id:
        return []

    query = select(Subcategory).where(Subcategory.category_id == int(category_id))

    if params.get("q"):
        query = query.where(Subcategory.name.ilike(f"%{params['q']}%"))

    rows = (
        (
            await session.execute(
                query.order_by(Subcategory.name).limit(lookup_limit(params))
            )
        )
        .scalars()
        .all()
    )

    return [{"value": row.id, "label": row.name} for row in rows]


def cover_thumb(value):
    if not value:
        return None

    return f'<img src="{value}" alt="cover" style="height:2rem;width:2rem;object-fit:cover;border-radius:6px">'


def status_badge(value):
    tone = STATUS_TONES.get(value, "secondary")

    return f'<span class="badge bg-{tone}-lt">{value}</span>'
