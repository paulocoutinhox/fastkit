import pytest
import pytest_asyncio

from fastkit_db.base import Base
from fastkit_db.engine import Database

from fastkit_reports import models  # noqa: F401
from fastkit_reports.contracts import ReportColumn, ReportDefinition, ReportFilter, ReportRegistry
from fastkit_reports.renderers import default_renderers
from fastkit_reports.service import ReportService


async def _sales_query(session, params):
    minimum = params.get("minimum", 0)

    rows = [
        {"product": "Alpha", "total": 100},
        {"product": "Beta", "total": 250},
        {"product": "Gamma", "total": 50},
    ]

    return [row for row in rows if row["total"] >= minimum]


async def _region_options(session, params, locale):
    return [{"value": "north", "label": "North"}, {"value": "south", "label": "South"}]


def sales_definition() -> ReportDefinition:
    return ReportDefinition(
        name="sales",
        title="Sales Report",
        columns=[ReportColumn("product", "Product"), ReportColumn("total", "Total", align="right")],
        query=_sales_query,
        filters=[ReportFilter("minimum", "Minimum total", "number")],
        options={"region": _region_options},
    )


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/reports.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()


@pytest.fixture
def registry():
    reg = ReportRegistry()
    reg.register(sales_definition())

    return reg


@pytest.fixture
def service(database, registry):
    return ReportService(database.session_factory, registry, default_renderers())


@pytest.fixture
def sales_def():
    return sales_definition()


@pytest.fixture
def sample_result():
    from fastkit_reports.contracts import ReportResult

    return ReportResult(definition=sales_definition(), rows=[{"product": "Alpha", "total": 100}, {"product": "Beta", "total": 250}])
