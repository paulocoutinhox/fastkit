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
