from html import escape
from html.parser import HTMLParser

DEFAULT_ALLOWED_TAGS = frozenset(
    {
        "p", "br", "strong", "b", "em", "i", "u", "s", "blockquote", "code", "pre",
        "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "a", "img", "hr",
        "table", "thead", "tbody", "tr", "th", "td", "span", "div",
    }
)

DEFAULT_ALLOWED_ATTRS = {
    "a": frozenset({"href", "title", "target", "rel"}),
    "img": frozenset({"src", "alt", "title", "width", "height", "data-asset-id"}),
    "*": frozenset({"class"}),
}

_VOID_TAGS = frozenset({"br", "img", "hr"})
_DROP_CONTENT_TAGS = frozenset({"script", "style"})
_SAFE_URL_SCHEMES = frozenset({"http", "https", "mailto", "tel"})


def _is_safe_url(value: str) -> bool:
    stripped = value.strip().lower()

    if stripped.startswith("/") or stripped.startswith("#"):
        return True

    if ":" not in stripped:
        return True

    scheme = stripped.split(":", 1)[0]

    if scheme == "data":
        return stripped.startswith("data:image/")

    return scheme in _SAFE_URL_SCHEMES


class _Sanitizer(HTMLParser):
    def __init__(self, allowed_tags, allowed_attrs):
        super().__init__(convert_charrefs=True)
        self._allowed_tags = allowed_tags
        self._allowed_attrs = allowed_attrs
        self._parts: list[str] = []
        self._skip_depth = 0

    def _allowed_attributes(self, tag: str) -> frozenset:
        return self._allowed_attrs.get(tag, frozenset()) | self._allowed_attrs.get("*", frozenset())

    def handle_starttag(self, tag, attrs):
        if tag in _DROP_CONTENT_TAGS:
            self._skip_depth += 1
            return

        if self._skip_depth or tag not in self._allowed_tags:
            return

        allowed = self._allowed_attributes(tag)
        rendered = []

        for name, value in attrs:
            if name.startswith("on") or name not in allowed:
                continue

            if name in ("href", "src") and (value is None or not _is_safe_url(value)):
                continue

            rendered.append(f' {name}="{escape(value or "", quote=True)}"')

        closing = " /" if tag in _VOID_TAGS else ""
        self._parts.append(f"<{tag}{''.join(rendered)}{closing}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in _DROP_CONTENT_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return

        if self._skip_depth or tag not in self._allowed_tags or tag in _VOID_TAGS:
            return

        self._parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self._skip_depth:
            self._parts.append(escape(data))

    def result(self) -> str:
        return "".join(self._parts)


def sanitize_html(html: str, allowed_tags: frozenset | None = None, allowed_attrs: dict | None = None) -> str:
    """Return HTML containing only allow-listed tags, attributes and safe URLs."""

    parser = _Sanitizer(allowed_tags or DEFAULT_ALLOWED_TAGS, allowed_attrs or DEFAULT_ALLOWED_ATTRS)
    parser.feed(html)
    parser.close()

    return parser.result()
