"""Who a request answers for, which is a tenant where this instance serves many and the configuration where it serves one."""

from dataclasses import dataclass

from helpers.settings import settings
from models.tenant import Tenant


@dataclass(frozen=True)
class Brand:
    """The identity a page and a message are written under, whose id is the scope every row it touches is written into — and nothing at all where this instance serves one site."""

    id: int | None
    code: str
    name: str
    domain: str
    email_contact: str

    def address(self, path: str) -> str:
        return address_on(self.domain, path)


def address_on(domain: str, path: str) -> str:
    """Where a path lives on a site, which is what that site declares and never the host a request happened to arrive under."""
    return f"{settings.site.scheme}://{domain}{path}"


def of(tenant: Tenant | None) -> Brand:
    """The brand a tenant is, or the one this instance is when it serves a single site and holds no tenant at all."""
    if tenant is None:
        return Brand(id=None, code="", name=settings.name, domain=settings.site.domain, email_contact=settings.email.from_address)

    return Brand(id=tenant.id, code=tenant.code, name=tenant.name, domain=tenant.domain, email_contact=tenant.email_contact)
