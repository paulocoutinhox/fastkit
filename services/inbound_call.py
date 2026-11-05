import json
from dataclasses import dataclass, field
from urllib.parse import parse_qsl

from models.base import JSON_DEPTH_MAX
from schemas.common import nesting

# What proves the caller is the provider is worth reading once and never keeping, so it is not written down with the rest.
SECRET_HEADERS = ("authorization", "cookie", "proxy-authorization")


@dataclass(frozen=True)
class InboundCall:
    """What arrived, exactly as it arrived: the provider decides the method, the format and the headers, and we decide nothing."""

    method: str
    headers: dict = field(default_factory=dict)
    query: dict = field(default_factory=dict)
    body: bytes = b""

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def data(self) -> dict:
        content_type = (self.header("content-type") or "").split(";")[0].strip()

        if content_type == "application/x-www-form-urlencoded":
            return dict(parse_qsl(self.text()))

        # A body nested deep enough stops the parser itself, and one past the depth a column holds is as unreadable here as one that is not JSON.
        try:
            parsed = json.loads(self.text())
        except (ValueError, RecursionError):
            return {}

        return parsed if isinstance(parsed, dict) and nesting(parsed) <= JSON_DEPTH_MAX else {}

    def is_empty(self) -> bool:
        return not self.body and not self.query

    def recorded(self) -> dict:
        return {"method": self.method, "query": self.query, "headers": {name: value for name, value in self.headers.items() if name not in SECRET_HEADERS}}
