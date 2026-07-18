class ExplicitTenantResolver:
    name = "explicit"

    def __init__(self, code: str | None):
        self._code = code

    def resolve(self, request) -> str | None:
        return self._code
