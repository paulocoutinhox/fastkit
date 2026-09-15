# What an administrator writes without leaving a trail of its own, each with the reason it leaves none.
UNTRACKED = {"POST /api/uploads/{purpose}": "the file leaves its trail on the record that ends up naming it, and that write is written down", "POST /api/subscriptions/{record_id}/new-cycle": "the delivery engine writes this one itself, with the operator who asked for it"}


def declared(app) -> list[tuple[str, object]]:
    """Every route of the application in the order it was registered, reached through the routers it was built out of."""
    found = []

    for included in app.routes:
        context = getattr(included, "include_context", None)
        prefix = context.prefix if context else ""

        for route in getattr(getattr(included, "original_router", None), "routes", [route for route in (included,) if getattr(route, "endpoint", None)]):
            for method in getattr(route, "methods", set()) or set():
                found.append((f"{method} {prefix}{route.path}", route))

    return found


def endpoints(app) -> dict:
    """Every route by name, where a name that repeats is what `test_app` refuses."""
    return dict(declared(app))


def test_every_write_an_administrator_reaches_leaves_a_trail(app):
    """A resource built by the factory answers for itself, and every write outside it has to say so here."""
    import ast
    import pathlib

    from tests.test_role_matrix import ACCOUNT, OPEN

    audited = set()

    for path in [*pathlib.Path("routes").rglob("*.py"), pathlib.Path("helpers/crud.py")]:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "audit.written" in ast.unparse(node):
                audited.add(node.name)

    checked, missing = 0, []

    for name, route in sorted(endpoints(app).items()):
        method, path = name.split(" ", 1)

        if method in ("GET", "HEAD", "OPTIONS") or not path.startswith("/api") or name in OPEN or name in ACCOUNT:
            continue

        checked += 1

        if route.endpoint.__name__ not in audited and name not in UNTRACKED:
            missing.append(name)

    assert checked >= 20, f"the scan read only {checked} administrator writes, so it is proving nothing"
    assert missing == [], f"an administrator writes here and nothing records it: {missing}"
