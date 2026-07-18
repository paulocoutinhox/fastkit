import json

from fastkit_reports.contracts import ReportResult


class JsonRenderer:
    name = "json"

    def render(self, result: ReportResult) -> bytes:
        payload = {"title": result.definition.title, "rows": result.rows}

        return json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
