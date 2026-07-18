from enum import Enum


class ContentType(str, Enum):
    plain_text = "plain_text"
    rich_text = "rich_text"
    html = "html"
    markdown = "markdown"
    json = "json"
    page = "page"
    block = "block"
    email_snippet = "email_snippet"
