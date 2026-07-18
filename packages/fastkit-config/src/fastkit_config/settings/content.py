from pydantic import BaseModel


class ContentSettings(BaseModel):
    sanitize_html: bool = True
