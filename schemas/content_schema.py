from datetime import date

from pydantic import computed_field

from enums.content_audience import ContentAudience
from helpers.brand import address_on
from helpers.site import content_path
from schemas.content_category_reference import ContentCategoryReference
from schemas.language_reference import LanguageReference
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


class ContentSchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    category_id: int | None
    category: ContentCategoryReference | None
    language_id: int | None
    language: LanguageReference | None
    title: str
    tag: str
    content: str | None
    published_at: date | None
    active: bool
    audience: ContentAudience
    meta: dict

    @computed_field
    @property
    def address(self) -> str:
        """Where a reader opens this page, on the site of the brand it belongs to, and a shared page is on every site so it is the path alone."""
        path = content_path(self.tag)

        return address_on(self.tenant.domain, path) if self.tenant else path
