from fastkit_reports.renderers.csv import CsvRenderer
from fastkit_reports.renderers.html import HtmlRenderer
from fastkit_reports.renderers.json import JsonRenderer
from fastkit_reports.renderers.screen import ScreenRenderer


def default_renderers() -> dict:
    return {
        renderer.name: renderer
        for renderer in (
            ScreenRenderer(),
            JsonRenderer(),
            CsvRenderer(),
            HtmlRenderer(),
        )
    }
