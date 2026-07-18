import pytest
from sqlalchemy import BigInteger, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_core.errors.exceptions import ValidationError
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


class Ticket(Base):
    __tablename__ = "inline_tickets"

    ref: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(40), nullable=False)
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
        ),
        InlineResource("tickets", [TextField("label", required=True)], model=Ticket, fk_field="order_id", pk_field="ref"),
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

    assert values == {"lines": [{"id": str(child_id), "sku": "A", "note": ""}], "tickets": []}


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


async def test_malformed_inline_payload_is_ignored_never_500_never_wipes(session):
    admin = OrderAdmin()
    order = await admin.create(session, {"name": "First", "lines": [{"sku": "A"}]}, "en")

    for bad in ["oops", 123, {}, [1, 2], None]:
        await admin.update(session, order.id, {"name": "First", "lines": bad}, "en")
        assert [sku for _, sku in await _lines(session, order.id)] == ["A"]


async def test_inline_validation_errors_carry_the_exact_row_path(session):
    admin = OrderAdmin()

    with pytest.raises(ValidationError) as exc:
        await admin.create(session, {"name": "First", "lines": [{"sku": "A"}, {"sku": ""}, {"sku": ""}]}, "en")

    paths = [error.path for error in exc.value.field_errors]
    assert paths == [["lines", 1, "sku"], ["lines", 2, "sku"]]

    # validation runs before any write, so nothing is persisted
    assert (await session.execute(select(Order))).scalars().all() == []
    assert (await session.execute(select(OrderLine))).scalars().all() == []


async def test_inline_supports_a_non_default_pk_field(session):
    admin = OrderAdmin()
    order = await admin.create(session, {"name": "First", "tickets": [{"label": "T1"}]}, "en")

    ref = (await admin.inline_values(session, order, "en"))["tickets"][0]["id"]

    await admin.update(session, order.id, {"name": "First", "tickets": [{"id": ref, "label": "T1-edited"}]}, "en")

    assert (await admin.inline_values(session, order, "en"))["tickets"] == [{"id": ref, "label": "T1-edited"}]
