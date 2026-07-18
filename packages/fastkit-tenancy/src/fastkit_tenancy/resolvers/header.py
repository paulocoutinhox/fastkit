class HeaderTenantResolver:
    name = "header"

    def __init__(self, header_name: str = "X-Tenant"):
        self._header_name = header_name

    def resolve(self, request) -> str | None:
        return request.headers.get(self._header_name) or None
