import re
import zipfile
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO

import pytest
from markupsafe import Markup

from enums.report_chart_kind import ReportChartKind
from enums.report_chart_period import ReportChartPeriod
from enums.report_column_kind import ReportColumnKind
from enums.subscription_status import SubscriptionStatus
from helpers import templates
from helpers.settings import settings
from reports.subscriptions_excel_exporter import SubscriptionsExcelExporter
from schemas.subscriptions_filter import SubscriptionsFilter
from services.excel_report_exporter import ExcelReportExporter
from services.grouped_report_chart import GroupedReportChart
from services.pdf_report_exporter import PdfReportExporter
from services.report import Report
from services.report_chart import ReportChart
from services.report_column import ReportColumn
from services.report_document import ReportDocument
from services.report_figure import report_figure
from services.report_plot import ReportPlot
from services.report_series import ReportSeries
from tests.factories import make_plan, make_product, make_purchase, make_subscription
from tests.reports.test_report_routes import period

COLUMNS = (
    ReportColumn("product", "report.column-product"),
    ReportColumn("status", "report.column-status", ReportColumnKind.ENUM, enum_name="purchase_status"),
    ReportColumn("price", "report.column-price", ReportColumnKind.MONEY, currency="currency"),
    ReportColumn("quantity", "report.column-plan", ReportColumnKind.INTEGER),
    ReportColumn("paid_at", "report.column-paid-at", ReportColumnKind.DATETIME),
    ReportColumn("day", "report.column-started-at", ReportColumnKind.DATE),
)


def documented(rows: list[dict], zone: str = "UTC", locale: str = "en") -> ReportDocument:
    return ReportDocument(title="Purchases", brand_name="Acme", brand_code="", generated_at=datetime(2026, 11, 9, 12, tzinfo=timezone.utc), columns=COLUMNS, rows=rows, locale=locale, zone=zone)


def row(**values) -> dict:
    return {"product": "Pro", "status": "paid", "price": Decimal("10"), "currency": "usd", "quantity": 1, "paid_at": None, "day": None} | values


def plotted(chart: GroupedReportChart, rows: list[dict], **reading) -> tuple[ReportPlot, ...]:
    return chart.plots(documented(rows, **reading))


def test_a_chart_counts_the_rows_of_each_label_in_alphabetical_order_and_writes_the_counts_the_way_the_reader_does():
    chart = GroupedReportChart("statuses", "report.chart-by-status", ReportChartKind.COLUMN, category="product")
    rows = [row(product="Zeta")] * 1200 + [row(product="alpha"), row(product="Beta"), row(product="beta 10"), row(product="beta 9")]

    (plot,) = plotted(chart, rows, locale="pt")

    assert plot.labels == ("alpha", "Beta", "beta 9", "beta 10", "Zeta")
    assert plot.series[0].values == (1.0, 1.0, 1.0, 1.0, 1200.0)
    assert plot.series[0].shown[-1] == "1.200"
    assert plot.series[0].name == "Quantidade"
    assert plot.title == "Por situação"
    assert plot.currency is None


def test_a_chart_of_an_enum_reads_each_value_by_its_label():
    chart = GroupedReportChart("statuses", "report.chart-by-status", ReportChartKind.BAR, category="status")

    (plot,) = plotted(chart, [row(status="paid"), row(status="failed")])

    assert set(plot.labels) == {"Paid", "Failed"}


def test_an_amount_is_added_up_in_a_chart_of_its_own_currency_and_never_with_another():
    chart = GroupedReportChart("revenue", "report.chart-paid-per-day", ReportChartKind.COLUMN, category="product", value="price")
    rows = [row(price=Decimal("10.10")), row(price=Decimal("5.05")), row(price=Decimal("100"), currency="brl"), row(price=None)]

    brl, usd = plotted(chart, rows)

    assert (brl.key, brl.title, brl.currency, brl.series[0].values, brl.series[0].shown) == ("revenue-brl", "Paid per day · BRL", "brl", (100.0,), ("BRL 100.00",))
    assert (usd.key, usd.title, usd.series[0].values, usd.series[0].shown, usd.series[0].name) == ("revenue-usd", "Paid per day · USD", (15.15,), ("USD 15.15",), "USD")


def test_a_number_is_added_up_under_the_heading_of_its_column():
    chart = GroupedReportChart("quantities", "report.chart-by-status", ReportChartKind.COLUMN, category="product", value="quantity")

    (plot,) = plotted(chart, [row(quantity=2), row(quantity=3), row(product="Other", quantity=None)])

    assert plot.labels == ("Pro",)
    assert plot.series[0].values == (5.0,)
    assert plot.series[0].name == "Plan"


def test_an_instant_is_grouped_by_the_day_on_the_clock_of_the_reader_with_every_day_between_drawn_as_zero():
    chart = GroupedReportChart("paid", "report.chart-paid-per-day", ReportChartKind.LINE, category="paid_at")
    rows = [row(paid_at=datetime(2026, 11, 2, 1, tzinfo=timezone.utc)), row(paid_at=datetime(2026, 11, 4, 15, tzinfo=timezone.utc)), row(paid_at=None)]

    (plot,) = plotted(chart, rows, zone="America/Sao_Paulo")

    assert plot.labels == ("2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04")
    assert plot.series[0].values == (1.0, 0.0, 0.0, 1.0)


def test_a_date_is_grouped_by_month_with_every_month_between_drawn():
    chart = GroupedReportChart("started", "report.chart-started-per-month", ReportChartKind.COLUMN, category="day", period=ReportChartPeriod.MONTH)

    (plot,) = plotted(chart, [row(day=date(2026, 1, 31)), row(day=date(2026, 1, 2)), row(day=date(2026, 4, 30))])

    assert plot.labels == ("2026-01", "2026-02", "2026-03", "2026-04")
    assert plot.series[0].values == (2.0, 0.0, 0.0, 1.0)


def test_a_pie_folds_what_the_palette_has_no_colour_for_into_one_last_slice_and_draws_no_slice_of_nothing():
    chart = GroupedReportChart("products", "report.chart-by-status", ReportChartKind.PIE, category="product", value="quantity")
    sizes = {f"product {index}": index for index in range(1, 11)}
    rows = [row(product=name, quantity=size) for name, size in sizes.items()] + [row(product="empty", quantity=0)]

    (plot,) = plotted(chart, rows)

    kept = settings.charts.slots - 1

    assert len(plot.labels) == settings.charts.slots
    assert plot.labels[-1] == "Other"
    assert plot.labels[:-1] == tuple(f"product {index}" for index in range(11 - kept, 11))
    assert plot.series[0].values[-1] == float(sum(range(1, 11 - kept)))
    assert "empty" not in plot.labels


def test_a_chart_of_no_row_or_of_nothing_but_empty_slices_is_no_chart_at_all():
    pie = GroupedReportChart("products", "report.chart-by-status", ReportChartKind.PIE, category="product", value="quantity")
    column = GroupedReportChart("products", "report.chart-by-status", ReportChartKind.COLUMN, category="product")

    assert plotted(column, []) == ()
    assert plotted(pie, [row(quantity=0)]) == ()


def test_a_chart_naming_what_its_report_does_not_answer_fails_where_the_report_is_written():
    def written(*charts):
        class Charted(Report):
            code = "charted"
            title = "report.purchases"
            filters = SubscriptionsFilter
            columns = COLUMNS

            def statement(self, chosen, operator):
                return None

        Charted.charts = charts
        Charted.__init_subclass__()

    with pytest.raises(TypeError, match="not a column"):
        written(GroupedReportChart("a", "report.chart-by-status", ReportChartKind.COLUMN, category="missing"))

    with pytest.raises(TypeError, match="not a number"):
        written(GroupedReportChart("a", "report.chart-by-status", ReportChartKind.COLUMN, category="product", value="status"))

    with pytest.raises(TypeError, match="key of its own"):
        written(GroupedReportChart("a", "report.chart-by-status", ReportChartKind.COLUMN, category="product"), GroupedReportChart("a", "report.chart-by-status", ReportChartKind.PIE, category="status"))


def test_a_plot_that_cannot_be_drawn_fails_where_it_is_built():
    one = ReportSeries("Count", (1.0,), ("1",))

    with pytest.raises(ValueError, match="at least one point"):
        ReportPlot("a", "A", ReportChartKind.COLUMN, (), ())

    with pytest.raises(ValueError, match="each of its labels"):
        ReportPlot("a", "A", ReportChartKind.COLUMN, ("x", "y"), (one,))

    with pytest.raises(ValueError, match="palette has colours"):
        ReportPlot("a", "A", ReportChartKind.COLUMN, ("x",), (one,) * (settings.charts.slots + 1))

    with pytest.raises(ValueError, match="larger than zero"):
        ReportPlot("a", "A", ReportChartKind.DOUGHNUT, ("x",), (ReportSeries("Count", (0.0,), ("0",)),))


def test_a_chart_of_its_own_is_a_subclass_that_works_out_its_numbers_however_it_wants():
    class Cumulative(ReportChart):
        def plots(self, document):
            totals, running = [], 0

            for value in [line["quantity"] for line in document.rows]:
                running += value
                totals.append(float(running))

            return (ReportPlot(self.key, "Cumulative", self.kind, tuple(str(index) for index in range(len(totals))), (ReportSeries("Total", tuple(totals), tuple(str(total) for total in totals)),)),)

    chart = Cumulative("cumulative", "report.chart-count", ReportChartKind.AREA)
    chart.check(COLUMNS)

    (plot,) = chart.plots(documented([row(quantity=2), row(quantity=3)]))

    assert plot.series[0].values == (2.0, 5.0)


@pytest.mark.parametrize("kind", list(ReportChartKind))
def test_every_kind_is_drawn_for_the_printed_page_as_a_vector_with_its_text_kept_as_text(kind):
    plot = ReportPlot("a", "Revenue $5 <script>", kind, ("$9 plan", "b & c"), (ReportSeries("USD", (1.5, 2.0), ("USD 1.50", "USD 2.00")),), currency="usd")

    drawn = report_figure.svg(plot, "pt")

    assert drawn.startswith("<svg")
    assert "Revenue $5 &lt;script&gt;" in drawn
    assert "<script>" not in drawn
    assert settings.charts.light[0] in drawn


def test_several_series_on_paper_are_named_by_a_legend():
    plot = ReportPlot("a", "New and renewed", ReportChartKind.COLUMN, ("x", "y"), (ReportSeries("New", (1.0, 2.0), ("1", "2")), ReportSeries("Renewed", (3.0, 4.0), ("3", "4"))))

    drawn = report_figure.svg(plot, "en")

    assert "New" in drawn and "Renewed" in drawn
    assert settings.charts.light[1] in drawn


def test_a_palette_names_the_same_slots_on_both_surfaces():
    from pydantic import ValidationError as SchemaError

    from config.chart_settings import ChartSettings

    with pytest.raises(SchemaError, match="same slots"):
        ChartSettings(light=("#000000",), dark=())

    with pytest.raises(SchemaError):
        ChartSettings(light=("blue",), dark=("blue",))


def test_the_printed_page_draws_each_chart_above_the_rows():
    document = replace(documented([row()]), plots=(ReportPlot("a", "Paid per day", ReportChartKind.COLUMN, ("x",), (ReportSeries("Count", (1.0,), ("1",)),)),))
    figures = [(plot, Markup(report_figure.svg(plot, "en"))) for plot in document.plots]

    drawn = templates.render("report/document.html", None, {"document": document, "figures": figures})

    assert drawn.index('aria-label="Paid per day"') < drawn.index("<table>")
    assert drawn.count("<svg") == 1


def test_the_printed_page_of_a_report_can_be_a_template_of_its_own_that_extends_the_shared_one():
    document = replace(documented([row()]), details={"figures": [{"key": "accounts", "label": "Accounts", "value": 1234}]})

    drawn = templates.render("report/subscriptions.html", None, {"document": document, "figures": []})

    assert '<dl class="figures">' in drawn
    assert "1,234" in drawn
    assert drawn.index("Accounts") < drawn.index("<table>")
    assert PdfReportExporter("report/subscriptions.html").render(document).startswith(b"%PDF")


def test_the_spreadsheet_opens_on_its_charts_drawn_by_the_spreadsheet_from_cells_beside_them():
    plots = (ReportPlot("paid-usd", "Paid · USD", ReportChartKind.COLUMN, ("2026-11-01", "2026-11-02"), (ReportSeries("USD", (10.5, 0.0), ("USD 10.50", "USD 0.00")),), currency="usd"), ReportPlot("statuses", "By status", ReportChartKind.PIE, ("Failed", "Paid"), (ReportSeries("Count", (1.0, 2.0), ("1", "2")),)))
    book = zipfile.ZipFile(BytesIO(ExcelReportExporter().render(replace(documented([row()]), plots=plots))))
    names = re.findall(r'<sheet name="([^"]+)"', book.read("xl/workbook.xml").decode())
    cells = book.read("xl/worksheets/sheet1.xml").decode()
    column = book.read("xl/charts/chart1.xml").decode()
    pie = book.read("xl/charts/chart2.xml").decode()

    assert names == ["Charts", "Purchases"]
    assert "<v>10.5</v>" in cells
    assert "<c:barChart>" in column and '<c:barDir val="col"/>' in column
    assert settings.charts.light[0].lstrip("#").upper() in column
    assert "<c:pieChart>" in pie
    assert settings.charts.light[1].lstrip("#").upper() in pie
    assert "&quot;USD&quot; #,##0.00" in book.read("xl/styles.xml").decode()


def test_a_spreadsheet_with_nothing_to_chart_has_no_sheet_of_charts():
    book = zipfile.ZipFile(BytesIO(ExcelReportExporter().render(documented([row()]))))

    assert re.findall(r'<sheet name="([^"]+)"', book.read("xl/workbook.xml").decode()) == ["Purchases"]


def test_a_spreadsheet_of_a_report_can_add_sheets_of_its_own_and_never_reuses_a_name():
    document = replace(documented([row()], locale="pt"), title="Resumo", details={"figures": [{"key": "accounts", "label": "Contas", "value": 3}]})
    book = zipfile.ZipFile(BytesIO(SubscriptionsExcelExporter().render(document)))
    names = re.findall(r'<sheet name="([^"]+)"', book.read("xl/workbook.xml").decode())

    assert names == ["Resumo", "Resumo (2)"]
    assert "<v>3</v>" in book.read("xl/worksheets/sheet1.xml").decode()


async def test_a_run_answers_its_charts_and_its_details_with_the_rows(client, db, tenant, member, admin_headers):
    product = await make_product(db, tenant, price=Decimal("19.9"))
    plan = await make_plan(db, tenant)
    await make_purchase(db, tenant, member, product)
    await make_subscription(db, tenant, member, plan, status=SubscriptionStatus.ACTIVE)
    await make_subscription(db, tenant, member, plan, status=SubscriptionStatus.EXPIRED)

    purchases = (await client.get("/api/reports/purchases/rows", params=period(), headers=admin_headers)).json()
    subscriptions = (await client.get("/api/reports/subscriptions/rows", headers=admin_headers)).json()

    assert [chart["key"] for chart in purchases["charts"]] == ["statuses"]
    assert purchases["charts"][0]["series"][0] == {"name": "Count", "values": [1.0], "shown": ["1"]}
    assert purchases["details"] == {}
    # Neither subscription is paid through a gateway, so they name no provider and that chart has no point to draw.
    assert [chart["key"] for chart in subscriptions["charts"]] == ["statuses", "started"]
    assert subscriptions["details"]["figures"] == [{"key": "subscriptions", "label": "Subscriptions", "value": 2}, {"key": "accounts", "label": "Accounts", "value": 1}, {"key": "eligible", "label": "Granting access", "value": 1}]


async def test_every_format_of_the_subscriptions_carries_its_figures(client, db, tenant, member, admin_headers):
    plan = await make_plan(db, tenant)
    await make_subscription(db, tenant, member, plan)

    for format in ("pdf", "excel", "csv"):
        answer = await client.get(f"/api/reports/subscriptions/export/{format}", headers=admin_headers)

        assert answer.status_code == 200

    book = zipfile.ZipFile(BytesIO((await client.get("/api/reports/subscriptions/export/excel", headers=admin_headers)).content))

    assert re.findall(r'<sheet name="([^"]+)"', book.read("xl/workbook.xml").decode()) == ["Summary", "Charts", "Subscriptions"]
