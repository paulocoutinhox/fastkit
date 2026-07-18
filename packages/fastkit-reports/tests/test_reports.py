import pytest
import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_reports.app import ReportsApp
from fastkit_reports.contracts import ReportRegistry, ReportResult
from fastkit_reports.models import ExecutionStatus, ReportExecution
from fastkit_reports.renderers import (
    CsvRenderer,
    HtmlRenderer,
    JsonRenderer,
    PdfRenderer,
    ScreenRenderer,
)
from fastkit_reports.service import ReportService


def test_registry_register_and_errors(sales_def):
    registry = ReportRegistry()
    registry.register(sales_def)

    assert registry.get("sales").title == "Sales Report"
    assert registry.names() == ["sales"]

    with pytest.raises(ValueError, match="already registered"):
        registry.register(sales_def)

    with pytest.raises(KeyError, match="not registered"):
        registry.get("missing")


def test_definition_schema(sales_def):
    schema = sales_def.to_schema()

    assert schema["columns"][1]["align"] == "right"
    assert schema["filters"][0]["type"] == "number"


def test_screen_renderer(sample_result):
    output = ScreenRenderer().render(sample_result)

    assert output["title"] == "Sales Report"
    assert len(output["rows"]) == 2
    assert output["columns"][0]["key"] == "product"


def test_json_renderer(sample_result):
    output = JsonRenderer().render(sample_result)

    assert b'"Sales Report"' in output


def test_csv_renderer(sample_result):
    output = CsvRenderer().render(sample_result).decode("utf-8")

    assert "Product,Total" in output
    assert "Alpha,100" in output


def test_csv_renderer_neutralizes_formula_injection(sales_def):
    result = ReportResult(
        definition=sales_def, rows=[{"product": "=HYPERLINK(x)", "total": 1}]
    )
    output = CsvRenderer().render(result).decode("utf-8")

    assert "'=HYPERLINK(x)" in output


def test_html_renderer_escapes(sales_def):
    definition = sales_def
    result = ReportResult(
        definition=definition, rows=[{"product": "<script>", "total": 1}]
    )
    output = HtmlRenderer().render(result)

    assert "<table>" in output
    assert "&lt;script&gt;" in output


def test_pdf_renderer_uses_backend(sample_result):
    captured = {}

    def backend(html):
        captured["html"] = html

        return b"%PDF-1.4 fake"

    output = PdfRenderer(backend).render(sample_result)

    assert output == b"%PDF-1.4 fake"
    assert "<table>" in captured["html"]


async def test_service_build_and_render(service, database):
    async with database.session_factory() as session:
        result = await service.build_result("sales", session)
        assert len(result.rows) == 3

        filtered = await service.build_result("sales", session, {"minimum": 100})
        assert len(filtered.rows) == 2

        screen = await service.render("sales", session, "screen")
        assert screen["title"] == "Sales Report"


async def test_service_render_unknown_renderer(service, database):
    async with database.session_factory() as session:
        with pytest.raises(KeyError, match="renderer 'xlsx'"):
            await service.render("sales", session, "xlsx")


async def test_resolve_options_returns_handler_result(service, database):
    async with database.session_factory() as session:
        options = await service.resolve_options("sales", session, "region", {})

    assert options == [
        {"value": "north", "label": "North"},
        {"value": "south", "label": "South"},
    ]


async def test_resolve_options_unknown_field_raises(service, database):
    async with database.session_factory() as session:
        with pytest.raises(KeyError, match="no options handler for 'nope'"):
            await service.resolve_options("sales", session, "nope", {})


async def test_service_add_renderer(service, database):
    def backend(html):
        return b"pdf"

    service.add_renderer(PdfRenderer(backend))

    async with database.session_factory() as session:
        assert await service.render("sales", session, "pdf") == b"pdf"


async def test_execute_success(service):
    execution = await service.execute("sales", "csv", params={"minimum": 100})

    assert execution.status == ExecutionStatus.succeeded.value
    assert execution.row_count == 2
    assert execution.progress == 100


async def test_execute_failure_unknown_renderer(service):
    execution = await service.execute("sales", "xlsx")

    assert execution.status == ExecutionStatus.failed.value
    assert execution.error_code == "report.failed"


class Settings:
    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        pool_recycle = 1800
        echo = False

    installed_apps = ["fastkit.core", "fastkit.db", "fastkit.reports"]


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {
            "fastkit.core": CoreApp,
            "fastkit.db": DbApp,
            "fastkit.reports": ReportsApp,
        },
    )
    runtime = Runtime(settings=Settings(), installed_apps=list(Settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_reports_app_registers(runtime):
    assert ReportExecution in runtime.models.all()
    assert isinstance(runtime.component("report_service"), ReportService)
    assert isinstance(runtime.component("report_registry"), ReportRegistry)


def test_export_formats_excludes_screen_and_json(service):
    formats = service.export_formats()

    assert "csv" in formats
    assert "html" in formats
    assert "screen" not in formats
    assert "json" not in formats
