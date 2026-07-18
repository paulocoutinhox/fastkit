# Add a model and admin resource

## 1. The model

```python
from sqlalchemy import String, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from fastkit_db.base import Base, PrimaryKeyMixin, TimestampMixin

class Product(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shop_products"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    def display_label(self) -> str:
        return self.name
```

Register it: `context.models.register(Product, source=self.name)`.

## 2. The resource

```python
from fastkit_admin.resource import AdminResource, Fieldset
from fastkit_admin.columns import Column
from fastkit_admin.fields import TextField, DecimalField

class ProductAdmin(AdminResource[Product]):
    name = "products"
    label = "Products"
    icon = "package"
    list_columns = ["name", Column("price", type="decimal"), Column("created_at", type="datetime")]
    search_fields = ["name"]
    form_fields = [TextField("name", required=True), DecimalField("price", decimal_places=2)]
    fieldsets = [Fieldset("Details", ["name", "price"])]
    permissions = {"list": "products.view", "create": "products.create",
                   "update": "products.update", "delete": "products.delete", "detail": "products.view"}
```

## 3. Register + menu

```python
def register_admin(self, context):
    site = context.component("admin_site")
    site.register(ProductAdmin())
    site.add_group("catalog", "Catalog", order=0, icon="package")
    site.add_menu("Products", group="catalog", resource="products")
```

That's a full CRUD grid + form + detail at `/admin/products`. Add
[filters](../admin/filters.md), [inlines](../admin/inlines.md),
[file fields](../admin/uploads-files.md) and [overrides](../admin/overrides.md) as needed.
