import json
import pathlib
import re

from pydantic.alias_generators import to_camel

from reports.registry import REPORTS
from services.report import Report

DEFINITIONS = pathlib.Path("webapps/admin/src/reports/index.js")

BUILDER = re.compile(r'\b(?:text|number|decimal|toggle|choice|lookup|datetime|date|timezone|language)\(\s*"(\w+)"')


def drawn() -> dict[str, set[str]]:
    """Every report the panel draws, with the filter fields its screen asks for, read off the file that declares them."""
    source = DEFINITIONS.read_text()
    found = {}

    for block in re.split(r"\n    \{\n", source)[1:]:
        code = re.search(r'code: "([a-z0-9-]+)"', block).group(1)
        found[code] = set(BUILDER.findall(block))

    assert len(found) >= 2, f"the scan read only {len(found)} reports, so it is proving nothing"

    return found


def report_modules() -> set[str]:
    """Every module of the folder that writes a report, beside the ones that write a format or a chart of a report's own."""
    modules = {path.stem for path in pathlib.Path("reports").glob("*.py") if path.stem not in ("__init__", "registry")}
    written = {module for module in modules if re.search(r"^class \w+\(Report\):", pathlib.Path(f"reports/{module}.py").read_text(), re.M)}

    assert len(written) >= 2, f"the scan found only {len(written)} reports, so it is proving nothing"

    return written


def test_every_report_written_is_one_the_registry_offers():
    """A report written and never registered is a screen nobody reaches, and one registered twice under one code would answer for the other."""
    registered = {type(report).__module__.split(".")[-1] for report in REPORTS.values()}

    assert registered == report_modules()
    assert all(isinstance(report, Report) and code == report.code for code, report in REPORTS.items())


def test_every_report_is_drawn_by_the_panel_and_every_one_drawn_is_served():
    assert set(drawn()) == set(REPORTS)


def test_the_panel_asks_for_exactly_the_filter_each_report_reads():
    """A field the panel draws and the report refuses is a screen that never runs, and one the report reads and nobody draws is a filter nobody can set."""
    asked = {code: {to_camel(name) for name in report.filters.model_fields} for code, report in REPORTS.items()}

    assert drawn() == asked


def test_every_title_is_written_on_both_sides_in_every_language():
    """The server titles the file and the panel titles the menu, so a report missing either reads its own key somewhere."""
    missing = []

    for language in ("en", "pt", "es"):
        server = json.loads(pathlib.Path(f"locale/{language}.json").read_text())
        panel = pathlib.Path(f"webapps/admin/src/i18n/{language}.js").read_text()

        missing += [f"{language}: {report.title}" for report in REPORTS.values() if report.title not in server]
        missing += [f"{language}: report.{code}.title" for code in REPORTS if not re.search(rf'^\s+"?{code}"?: \{{ title: "', panel, re.M)]

    assert missing == []
