from sqlalchemy import BigInteger, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_db.base import Base, PrimaryKeyMixin
from fastkit_admin.fields import TextField
from fastkit_admin.inlines import InlineResource
from fastkit_admin.resource import AdminResource


class Order(PrimaryKeyMixin, Base):
    __tablename__ = "inline_orders"

    name: Mapped[str] = mapped_column(String(80), nullable=False)


class OrderLine(PrimaryKeyMixin, Base):
    __tablename__ = "inline_order_lines"

    sku: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("inline_orders.id", ondelete="CASCADE"), nullable=False, index=True)


class OrderAdmin(AdminResource[Order]):
    name = "orders"
    label = "Orders"
    model = Order

    form_fields = [TextField("name", required=True)]
    inlines = [
        InlineResource(
            "lines",
            [TextField("sku", required=True, max_length=40), TextField("note", readonly=True)],
            model=OrderLine,
            fk_field="order_id",
        )
    ]

    permissions = {}


async def _lines(session, order_id):
    rows = (await session.execute(select(OrderLine).where(OrderLine.order_id == order_id).order_by(OrderLine.id))).scalars().all()

    return [(row.id, row.sku) for row in rows]


async def test_create_persists_inline_children(session):
    admin = OrderAdmin()

    order = await admin.create(session, {"name": "First", "lines": [{"sku": "A"}, {"sku": "B"}]}, "en")

    assert [sku for _, sku in await _lines(session, order.id)] == ["A", "B"]


async def test_inline_values_serializes_existing_children(session):
    admin = OrderAdmin()
    order = await admin.create(session, {"name": "First", "lines": [{"sku": "A"}]}, "en")

    values = await admin.inline_values(session, order, "en")
    child_id = (await _lines(session, order.id))[0][0]

    assert values == {"lines": [{"id": str(child_id), "sku": "A", "note": ""}]}


async def test_update_diffs_inline_children_by_id(session):
    admin = OrderAdmin()
    order = await admin.create(session, {"name": "First", "lines": [{"sku": "A"}, {"sku": "B"}]}, "en")
    original = await _lines(session, order.id)

    kept_id = original[0][0]
    await admin.update(session, order.id, {"name": "First", "lines": [{"id": str(kept_id), "sku": "A2"}, {"sku": "C"}]}, "en")

    result = await _lines(session, order.id)
    assert [sku for _, sku in result] == ["A2", "C"]
    assert result[0][0] == kept_id


async def test_update_without_inline_key_leaves_children_untouched(session):
    admin = OrderAdmin()
    order = await admin.create(session, {"name": "First", "lines": [{"sku": "A"}]}, "en")

    await admin.update(session, order.id, {"name": "Renamed"}, "en", partial=True)

    assert [sku for _, sku in await _lines(session, order.id)] == ["A"]


async def test_update_with_empty_inline_removes_all_children(session):
    admin = OrderAdmin()
    order = await admin.create(session, {"name": "First", "lines": [{"sku": "A"}]}, "en")

    await admin.update(session, order.id, {"name": "First", "lines": []}, "en")

    assert await _lines(session, order.id) == []
