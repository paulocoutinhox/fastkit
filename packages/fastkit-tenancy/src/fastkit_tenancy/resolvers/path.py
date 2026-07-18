class PathTenantResolver:
    name = "path"

    def __init__(self, prefix: str = "/t/"):
        self._prefix = prefix

    def resolve(self, request) -> str | None:
        path = request.url.path

        if not path.startswith(self._prefix):
            return None

        remainder = path[len(self._prefix) :].split("/", 1)[0]

        return remainder or None
