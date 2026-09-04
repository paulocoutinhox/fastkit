"""Every path under /API answers to somebody, and the ones that answer to anybody are named here."""

import ast
import pathlib
import socket

import pytest

ANNOTATED = {"AdministratorUser": "administrator", "CurrentUser": "account", "OptionalUser": "account", "CurrentBrand": "brand"}

DEPENDED = {"get_administrator": "administrator", "get_current_user": "account", "get_optional_user": "account", "get_current_brand": "brand"}

# A route anybody may call, and why it is allowed to be one.
OPEN = {
    ("POST", "/signin"): "signing in is how an account proves itself",
    ("POST", "/signup"): "creating an account cannot require one",
    ("POST", "/admin/signin"): "the administrator signs in the same way",
    ("POST", "/password-reset"): "asking for a reset is done by whoever lost the password",
    ("POST", "/password-reset/confirm"): "the token in the payload is the credential",
    ("GET", "/active"): "the languages offered are public",
    ("GET", "/offered"): "the countries an address may name are public, and the postal code of one is not",
    ("POST", ""): "writing to the operator and joining a newsletter are done by whoever has no account, and both carry a challenge",
    ("POST", "/confirm/{token}"): "the token mailed to the address is the credential",
    ("POST", "/unsubscribe/{token}"): "the same token is how the address leaves",
    ("GET", ""): "meta answers enums, timezones and the version, and no data of anybody",
    ("GET", "/health"): "a health check answers before anything else does",
    ("GET", "/ready"): "a readiness check is what a balancer reads, and it answers before anything else does",
    ("GET", "/captcha"): "the challenge is drawn for the sign in form, which nobody has passed yet",
    ("GET", "/visitor"): "a name to be counted by is handed to whoever asks, because only this side signs one and a banner is counted by readers with no account",
    ("ANY", "/{key}"): "the webhook key is the credential, and the provider authenticates the call",
}

# A segment that names no row, so there is no owner to resolve it against, and why it is one.
NOT_A_RECORD = {
    ("POST", "/{purpose}"): "the purpose names an upload rule and never a record, and what the caller may do with it is decided before anything is stored",
    ("GET", "/{country_code}/postal-code/{code}"): "neither segment names a row of ours: one is a country of the registry and the other is what a third party is asked about",
    ("POST", "/confirm/{token}"): "the token is the credential, and it is what the row is found by",
    ("POST", "/unsubscribe/{token}"): "the token is the credential, and it is what the row is found by",
}


def routes() -> list[dict]:
    found = []

    for path in sorted(pathlib.Path("routes").glob("*.py")):
        tree = ast.parse(path.read_text())
        router_guards = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and getattr(node.value.func, "id", "") == "APIRouter":
                source = ast.unparse(node.value)
                router_guards[node.targets[0].id] = {label for name, label in DEPENDED.items() if name in source}

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.decorator_list:
                continue

            decorator = ast.unparse(node.decorator_list[0])
            match = __import__("re").search(r"^(\w+)\.(get|post|put|patch|delete)\('([^']*)'", decorator)

            if match is None:
                continue

            annotations = {ast.unparse(argument.annotation) for argument in node.args.args if argument.annotation is not None}
            guards = {ANNOTATED[name] for name in annotations & set(ANNOTATED)} | router_guards.get(match.group(1), set())

            body = "\n".join(ast.unparse(statement) for statement in node.body)

            found.append({"file": path.name, "line": node.lineno, "method": match.group(2).upper(), "path": match.group(3), "guards": guards, "body": body})

    return found


@pytest.mark.parametrize("route", routes(), ids=lambda route: f"{route['method']} {route['file']}{route['path']}")
def test_every_route_answers_to_somebody(route):
    """A route with no guard is readable by anybody, and that is only ever deliberate."""
    if route["guards"]:
        return

    assert (route["method"], route["path"]) in OPEN, f"{route['file']}:{route['line']} has no guard and is not declared open"


@pytest.mark.parametrize("route", [r for r in routes() if "{" in r["path"] and "administrator" not in r["guards"]], ids=lambda route: f"{route['method']} {route['file']}{route['path']}")
def test_an_identifier_from_a_client_is_resolved_against_the_caller(route):
    """An id the client chose is not a permission, so whoever asked is handed to the query and not merely received."""
    if (route["method"], route["path"]) in NOT_A_RECORD:
        return

    scope = "user" if "account" in route["guards"] else "brand"
    handed = (f"{scope}.id", f"{scope}.token", f"db, {scope}", f", {scope},", f"({scope})", f"{scope}=")

    assert any(mark in route["body"] for mark in handed), f"{route['file']}:{route['line']} takes an identifier and never hands the {scope} to what it calls"


def test_the_crud_factories_answer_only_to_the_roles_a_resource_names():
    """Thirty resources reach the API through here, so one route built without the guard would open all of them at once."""
    import re

    factory = pathlib.Path("helpers/crud.py").read_text()
    built = re.findall(r"@router\.(?:get|post|put|delete)\(([^\n]+)\n", factory)
    resolving = [route for route in built if "/lookup" in route]

    assert len(resolving) == 2, "the two that answer an option of somebody else's form"
    assert [route for route in built if "dependencies=[managed]" not in route] == resolving
    assert "APIRouter(prefix=prefix, tags=[tag], dependencies=[Depends(requires(*(service.lookup_roles or service.roles)))])" in factory


def test_the_only_route_registered_outside_a_decorator_is_the_webhook():
    """A route added in a loop is invisible to the check above, so there is exactly one and it is known."""
    registering = [path.name for path in pathlib.Path("routes").glob("*.py") if "add_api_route" in path.read_text()]

    assert registering == ["webhook.py"]


def test_the_suite_cannot_reach_a_machine_that_is_not_this_one():
    """The local database carries a real gateway key whenever somebody is testing a purchase, so a test that opens a socket is stopped before it spends one."""
    with pytest.raises(AssertionError, match="never by the network"):
        socket.socket().connect(("api.revenuecat.com", 443))
