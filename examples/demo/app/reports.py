from fastapi import APIRouter, Depends, Request, Response
from fpdf import FPDF
from sqlalchemy import func, select

from fastkit_core.api.envelope import success_envelope
from fastkit_admin.filters import LookupFilter, NumberFilter
from fastkit_reports.contracts import ReportColumn, ReportDefinition
from app.admin import category_options, subcategory_options
from app.models import Category, Product
from fastkit_admin.security import AdminSecurity

EXPORT_MEDIA = {"csv": "text/csv", "pdf": "application/pdf", "html": "text/html"}


class PdfRenderer:
    name = "pdf"

    def render(self, result) -> bytes:
        columns = result.definition.columns
        pdf = FPDF(orientation="landscape")
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 12, result.definition.title, new_x="LMARGIN", new_y="NEXT")

        width = (pdf.w - 2 * pdf.l_margin) / len(columns)
        pdf.set_font("Helvetica", "B", 11)

        for column in columns:
            pdf.cell(width, 9, column.label, border=1)

        pdf.ln()
        pdf.set_font("Helvetica", size=10)

        for row in result.rows:
            for column in columns:
                pdf.cell(width, 8, str(row.get(column.key, "")), border=1)

            pdf.ln()

        return bytes(pdf.output())


async def _sales_rows(session, params):
    query = (
        select(Category.name.label("category"), func.count(Product.id).label("products"), func.coalesce(func.sum(Product.price), 0).label("total"))
        .join(Product, Product.category_id == Category.id, isouter=True)
        .group_by(Category.name)
        .order_by(Category.name)
    )

    if params.get("category_id"):
        query = query.where(Category.id == int(params["category_id"]))

    result = (await session.execute(query)).mappings().all()

    return [{"category": row["category"], "products": row["products"], "total": f"{float(row['total']):.2f}"} for row in result]


async def _product_rows(session, params):
    query = select(Product.name.label("name"), Product.sku.label("sku"), Product.price.label("price")).order_by(Product.name)

    if params.get("category_id"):
        query = query.where(Product.category_id == int(params["category_id"]))

    if params.get("subcategory_id"):
        query = query.where(Product.subcategory_id == int(params["subcategory_id"]))

    if params.get("max_price"):
        query = query.where(Product.price <= float(params["max_price"]))

    result = (await session.execute(query)).mappings().all()

    return [{"name": row["name"], "sku": row["sku"], "price": f"{float(row['price']):.2f}"} for row in result]


SALES_BY_CATEGORY = ReportDefinition(
    name="sales-by-category",
    title="Sales by category",
    columns=[
        ReportColumn("category", "Category"),
        ReportColumn("products", "Products", align="right"),
        ReportColumn("total", "Total price", align="right"),
    ],
    filters=[LookupFilter("category_id", options="category_id", label="Category")],
    options={"category_id": category_options},
    query=_sales_rows,
)

PRODUCT_PRICES = ReportDefinition(
    name="product-prices",
    title="Product prices",
    columns=[
        ReportColumn("name", "Product"),
        ReportColumn("sku", "SKU"),
        ReportColumn("price", "Price", align="right"),
    ],
    filters=[
        LookupFilter("category_id", options="category_id", label="Category"),
        LookupFilter("subcategory_id", options="subcategory_id", depends_on=["category_id"], label="Subcategory"),
        NumberFilter("max_price", label="Max price"),
    ],
    options={"category_id": category_options, "subcategory_id": subcategory_options},
    query=_product_rows,
)


def setup_reports(registry, service) -> None:
    registry.register(SALES_BY_CATEGORY)
    registry.register(PRODUCT_PRICES)
    service.add_renderer(PdfRenderer())


def build_report_router(runtime, security: AdminSecurity) -> APIRouter:
    router = APIRouter()
    service = runtime.component("report_service")
    registry = runtime.component("report_registry")
    translator = runtime.component("translator")

    async def _require(user):
        await security.authorize(user, "reports.view")

    @router.get("/reports")
    async def list_reports(user=Depends(security.get_current_user)):
        await _require(user)

        return success_envelope(data={"reports": [registry.get(name).to_schema() for name in registry.names()], "formats": service.export_formats()})

    @router.get("/reports/{name}/run")
    async def run_report(name: str, request: Request, session=Depends(security.get_session), user=Depends(security.get_current_user)):
        await _require(user)
        schema = registry.get(name).to_schema()
        result = await service.build_result(name, session, dict(request.query_params))
        locale = await security.get_locale(request)
        columns = [{**column, "label": translator.gettext(column["label"], locale=locale)} for column in schema["columns"]]
        filters = [{**item, "label": translator.gettext(item["label"], locale=locale)} for item in schema["filters"]]
        title = translator.gettext(schema["title"], locale=locale)

        return success_envelope(data={"title": title, "columns": columns, "filters": filters, "rows": result.rows, "formats": service.export_formats()})

    @router.get("/reports/{name}/options/{field}")
    async def report_options(name: str, field: str, request: Request, session=Depends(security.get_session), user=Depends(security.get_current_user)):
        await _require(user)
        locale = await security.get_locale(request)
        options = await service.resolve_options(name, session, field, dict(request.query_params), locale)

        return success_envelope(data=options)

    @router.get("/reports/{name}/export.{fmt}")
    async def export_report(name: str, fmt: str, request: Request, session=Depends(security.get_session), user=Depends(security.get_current_user)):
        await _require(user)
        content = await service.render(name, session, fmt, dict(request.query_params))

        if isinstance(content, str):
            content = content.encode()

        return Response(content, media_type=EXPORT_MEDIA.get(fmt, "application/octet-stream"), headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})

    return router
