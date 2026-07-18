from fastkit_tenancy.resolvers.protocol import TenantResolver


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
