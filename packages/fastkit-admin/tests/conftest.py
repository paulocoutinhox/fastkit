from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from fastkit_core.errors.exceptions import FastKitError
from fastkit_core.errors.handlers import fastkit_exception_handler, validation_exception_handler
from fastkit_db.base import Base, TimestampMixin, PrimaryKeyMixin
from fastkit_db.engine import Database

from fastkit_admin.actions import AdminAction
from fastkit_admin.api import AdminDeps, build_admin_router
from fastkit_admin.columns import Column
from fastkit_admin.fields import BooleanField, DateTimeField, DecimalField, SelectField, TextField
from fastkit_admin.filters import BooleanFilter, ChoiceFilter, TextFilter
from fastkit_admin.resource import AdminResource
from fastkit_admin.site import AdminSite


class Product(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "admin_products"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    category: Mapped[str] = mapped_column(String(40), default="general", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Tag(PrimaryKeyMixin, Base):
    __tablename__ = "admin_tags"

    slug: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)


class ProductAdmin(AdminResource[Product]):
    name = "products"
    label = "Products"
    icon = "box"
    model = Product

    list_columns = ["name", Column("price", align="right"), "category", "is_active", "badge", "created_at"]
    search_fields = ["name"]
    filters = [TextFilter("name"), BooleanFilter("is_active"), ChoiceFilter("category", choices=[("general", "General"), ("premium", "Premium")])]
    actions = [
        AdminAction(name="deactivate", label="Deactivate", permission="products.update", confirm=True),
        AdminAction(name="touch", label="Touch", scope="bulk"),
    ]
    ordering = ["-created_at"]

    form_fields = [
        TextField("name", required=True, max_length=120),
        DecimalField("price", required=True, decimal_places=2),
        SelectField("category", choices=[("general", "General"), ("premium", "Premium")]),
        BooleanField("is_active"),
        DateTimeField("updated_at", readonly=True),
    ]

    permissions = {"list": "products.view", "detail": "products.view", "create": "products.create", "update": "products.update", "delete": "products.delete"}

    async def options_owner_id(self, session, parent_values, locale):
        category = parent_values.get("category")

        if not category:
            return []

        return [{"value": 1, "label": f"{category} owner"}]

    def render_badge(self, row, locale):
        color = "green" if row.is_active else "gray"

        return f'<span class="badge badge-{color}">{row.category}</span>'

    async def action_deactivate(self, session, rows, locale):
        for row in rows:
            row.is_active = False

        await session.commit()

        return {"deactivated": len(rows)}

    async def action_touch(self, session, rows, locale):
        # returns nothing so run_action falls back to a default affected count
        return None


class FakeUser:
    def __init__(self, permissions):
        self.id = "user-1"
        self.is_root = False
        self.is_active = True
        self._permissions = set(permissions)

    def has(self, permission):
        return permission in self._permissions


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/admin.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()


class OpenAdmin(AdminResource[Product]):
    name = "open"
    label = "Open"
    model = Product
    list_columns = ["name"]
    form_fields = [TextField("name", required=True)]
    permissions = {}


@pytest.fixture
def site():
    admin_site = AdminSite()
    admin_site.register(ProductAdmin())
    admin_site.register(OpenAdmin())

    admin_site.add_group("catalog", "Catalog", order=0)
    admin_site.add_group("internal", "Internal", order=1)
    admin_site.add_menu("Products", group="catalog", resource="products")
    admin_site.add_menu("Open", group="catalog", resource="open")
    admin_site.add_menu("Reports", group="internal", path="/reports", permission="reports.view")

    return admin_site


@pytest.fixture
def product_admin(site):
    return site.get("products")


@pytest.fixture
def product_model():
    return Product


@pytest.fixture
def tag_model():
    return Tag


@pytest.fixture
def product_admin_cls():
    return ProductAdmin


@pytest_asyncio.fixture
async def session(database):
    async with database.session_factory() as active:
        yield active


def build_admin_app(database, site, user):
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(FastKitError, fastkit_exception_handler)

    async def get_session():
        async with database.session_factory() as active:
            yield active

    async def get_current_user():
        return user

    async def get_locale():
        return "en"

    async def authorize(current_user, permission):
        from fastkit_core.errors.codes import AUTHORIZATION_DENIED
        from fastkit_core.errors.exceptions import AuthorizationError

        if not current_user.has(permission):
            raise AuthorizationError(AUTHORIZATION_DENIED, message=f"permission '{permission}' is required")

    deps = AdminDeps(get_session=get_session, get_current_user=get_current_user, get_locale=get_locale, authorize=authorize)
    app.include_router(build_admin_router(site, deps))

    return app


@pytest.fixture
def admin_app_factory(database, site):
    def factory(permissions):
        return build_admin_app(database, site, FakeUser(permissions))

    return factory
