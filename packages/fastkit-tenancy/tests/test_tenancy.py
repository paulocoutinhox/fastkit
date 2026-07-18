from types import SimpleNamespace

import pytest

from fastkit_core.errors.exceptions import TenantError
from fastkit_tenancy.constants import GLOBAL_TENANT_ID, is_global, to_api, to_persisted
from fastkit_tenancy.context import (
    TenantContext,
    get_tenant_context,
    global_context,
    require_tenant_context,
    reset_tenant_context,
    set_tenant_context,
)
from fastkit_tenancy.models import Tenant, TenantStatus
from fastkit_tenancy.resolvers import (
    ExplicitTenantResolver,
    HeaderTenantResolver,
    PathTenantResolver,
    SubdomainTenantResolver,
    TenantResolverChain,
)
from fastkit_tenancy.service import TenantService, resolve_effective_tenant


def fake_request(host="", path="/", headers=None):
    merged = {"host": host}
    merged.update(headers or {})

    return SimpleNamespace(headers=merged, url=SimpleNamespace(path=path))


def test_global_tenant_conversions():
    assert to_persisted(0) is None
    assert to_persisted(None) is None
    assert to_persisted(5) == 5
    assert to_api(None) == GLOBAL_TENANT_ID
    assert to_api(5) == 5
    assert is_global(0)
    assert is_global(None)
    assert not is_global(3)


def test_context_lifecycle():
    assert get_tenant_context() is None

    context = TenantContext(requested_tenant_id=1, effective_tenant_id=1, source="header", resolved_at="now")
    token = set_tenant_context(context)

    try:
        assert require_tenant_context() is context
        assert not context.is_global_scope
    finally:
        reset_tenant_context(token)

    assert get_tenant_context() is None


def test_require_context_raises_when_absent():
    with pytest.raises(LookupError, match="no tenant context"):
        require_tenant_context()


def test_global_context_is_global_scope():
    assert global_context(source="system").is_global_scope


def test_subdomain_resolver():
    resolver = SubdomainTenantResolver(base_domain="example.com")

    assert resolver.resolve(fake_request(host="acme.example.com")) == "acme"
    assert resolver.resolve(fake_request(host="example.com")) is None
    assert resolver.resolve(fake_request(host="other.org")) is None
    assert resolver.resolve(fake_request(host="notexample.com")) is None
    assert resolver.resolve(fake_request(host="a.b.example.com")) == "a.b"


def test_header_resolver():
    resolver = HeaderTenantResolver()

    assert resolver.resolve(fake_request(headers={"X-Tenant": "acme"})) == "acme"
    assert resolver.resolve(fake_request()) is None


def test_path_resolver():
    resolver = PathTenantResolver(prefix="/t/")

    assert resolver.resolve(fake_request(path="/t/acme/users")) == "acme"
    assert resolver.resolve(fake_request(path="/other")) is None
    assert resolver.resolve(fake_request(path="/t/")) is None


def test_explicit_resolver():
    assert ExplicitTenantResolver("acme").resolve(fake_request()) == "acme"
    assert ExplicitTenantResolver(None).resolve(fake_request()) is None


def test_resolver_chain_returns_first_match():
    chain = TenantResolverChain([HeaderTenantResolver(), SubdomainTenantResolver("example.com")])

    assert chain.resolve(fake_request(host="acme.example.com")) == ("acme", "subdomain")
    assert chain.resolve(fake_request(headers={"X-Tenant": "beta"})) == ("beta", "header")
    assert chain.resolve(fake_request(host="example.com")) is None


def test_resolve_effective_tenant():
    assert resolve_effective_tenant(identity_tenant_id=0, requested_tenant_id=5) == 5
    assert resolve_effective_tenant(identity_tenant_id=0, requested_tenant_id=None) == GLOBAL_TENANT_ID
    assert resolve_effective_tenant(identity_tenant_id=3, requested_tenant_id=5) == 3


def test_assert_access_rules():
    service = TenantService(database=None)

    service.assert_access(identity_tenant_id=0, effective_tenant_id=9)
    service.assert_access(identity_tenant_id=3, effective_tenant_id=3)

    with pytest.raises(TenantError, match="another tenant"):
        service.assert_access(identity_tenant_id=3, effective_tenant_id=9)


async def test_service_get_and_require(database):
    async with database.session_factory() as session:
        session.add(Tenant(code="acme", name="Acme"))
        session.add(Tenant(code="ghost", name="Ghost", status=TenantStatus.disabled.value))
        await session.commit()

    service = TenantService(database)

    assert (await service.get_by_code("acme")).name == "Acme"
    assert await service.get_by_code("missing") is None
    assert (await service.require_active("acme")).code == "acme"


async def test_require_active_raises_for_missing(database):
    service = TenantService(database)

    with pytest.raises(TenantError, match="was not found"):
        await service.require_active("nope")


async def test_require_active_raises_for_inactive(database):
    async with database.session_factory() as session:
        session.add(Tenant(code="off", name="Off", status=TenantStatus.suspended.value))
        await session.commit()

    service = TenantService(database)

    with pytest.raises(TenantError, match="not active"):
        await service.require_active("off")


def test_tenant_display_label():
    from fastkit_tenancy.models import Tenant

    assert Tenant(code="acme", name="Acme Inc.").display_label() == "Acme Inc."
