from typing import Protocol, runtime_checkable


@runtime_checkable
class TenantResolver(Protocol):
    name: str

    def resolve(self, request) -> str | None:
        """Return a tenant code from the request, or None when this resolver does not apply."""
        ...


class SubdomainTenantResolver:
    name = "subdomain"

    def __init__(self, base_domain: str):
        self._base_domain = base_domain

    def resolve(self, request) -> str | None:
        host = request.headers.get("host", "").split(":")[0]
        suffix = f".{self._base_domain}"

        if not host.endswith(suffix):
            return None

        return host[: -len(suffix)] or None


class HeaderTenantResolver:
    name = "header"

    def __init__(self, header_name: str = "X-Tenant"):
        self._header_name = header_name

    def resolve(self, request) -> str | None:
        return request.headers.get(self._header_name) or None


class PathTenantResolver:
    name = "path"

    def __init__(self, prefix: str = "/t/"):
        self._prefix = prefix

    def resolve(self, request) -> str | None:
        path = request.url.path

        if not path.startswith(self._prefix):
            return None

        remainder = path[len(self._prefix):].split("/", 1)[0]

        return remainder or None


class ExplicitTenantResolver:
    name = "explicit"

    def __init__(self, code: str | None):
        self._code = code

    def resolve(self, request) -> str | None:
        return self._code


class TenantResolverChain:
    """Runs resolvers in configured order and returns the first non-empty tenant code."""

    def __init__(self, resolvers: list[TenantResolver]):
        self._resolvers = resolvers

    def resolve(self, request) -> tuple[str, str] | None:
        for resolver in self._resolvers:
            code = resolver.resolve(request)

            if code is not None:
                return code, resolver.name

        return None
