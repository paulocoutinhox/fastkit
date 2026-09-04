"""What money and access are made of is written by this side, and no API may offer a way in."""

import ast
import importlib
import inspect
import pathlib
import pkgutil
import typing
from enum import Enum

import pytest

from schemas.common import BaseSchema

# A table whose rows decide what somebody paid for or may reach: the engine writes them and the API only ever reads.
ENGINE_OWNED = {
    "Subscription": "a subscription is opened by what the gateway answers, never by a request",
    "UserEntitlement": "a right is granted by the delivery engine",
    "SubscriptionBenefit": "the snapshot is taken at activation",
    "BenefitGrant": "a cycle is delivered once, and the key that says so is the engine's",
    "CreditTransaction": "the ledger is append only, and a balance is corrected by another movement",
    "UserProduct": "what the account owns is written by a payment or by the engine, never posted",
    "Purchase": "a payment is opened by this side before a gateway sees it, and settled by what the gateway answers",
    "AppEvent": "an event is reported in a batch by the app and closed by the cron",
    "WebhookEvent": "what a gateway said is what it said",
    "SystemLog": "an audit trail somebody can write into stops being one",
    "UserBalance": "a balance is what the ledger of that currency adds up to, and never a number somebody set",
    "NewsletterSubscription": "an address is on the list because the address itself confirmed it, never because a request said so",
}

# Naming whose row it is, or what it is worth, decides money and access: an administrator may, a client never.
OWNERSHIP = ("user_id", "tenant_id", "role", "balance_after", "amount")


def bound() -> list[tuple[str, object, bool]]:
    """Every service the API exposes, and whether its router accepts writes."""
    found = []

    for path in sorted(pathlib.Path("routes").glob("*.py")):
        tree = ast.parse(path.read_text())
        module = None

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or getattr(node.func, "id", "") not in ("build_router", "build_readonly_router"):
                continue

            module = module or importlib.import_module(f"routes.{path.stem}")
            found.append((path.stem, getattr(module, node.args[0].id), node.func.id == "build_router"))

    return found


@pytest.mark.parametrize("module, service, writable", bound(), ids=lambda value: getattr(value, "model", None).__name__ if hasattr(value, "model") else str(value))
def test_no_router_offers_a_way_into_what_the_engine_owns(module, service, writable):
    model = service.model.__name__

    if model not in ENGINE_OWNED:
        return

    assert not writable, f"{module}: {model} is written by this side — {ENGINE_OWNED[model]}"


def test_the_list_of_what_the_engine_owns_names_tables_that_exist():
    """A name that drifted would turn this whole guard off in silence."""
    import models.registry  # noqa

    from helpers.db import Base

    known = {mapper.class_.__name__ for mapper in Base.registry.mappers}

    assert set(ENGINE_OWNED) <= known


def payloads() -> list[tuple[str, int, str, type, bool]]:
    """Every schema a client may send, and whether only an administrator reaches the route that takes it."""
    found = []

    for path in sorted(pathlib.Path("routes").glob("*.py")):
        source = path.read_text()
        tree = ast.parse(source)
        module = None

        admin_routers = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and getattr(node.value.func, "id", "") == "APIRouter" and "get_administrator" in ast.unparse(node.value):
                admin_routers.add(node.targets[0].id)

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.decorator_list:
                continue

            decorator = ast.unparse(node.decorator_list[0])
            annotations = {ast.unparse(argument.annotation) for argument in node.args.args if argument.annotation is not None}
            only_admin = "AdministratorUser" in annotations or any(f"{name}." in decorator for name in admin_routers)

            for argument in node.args.args:
                name = ast.unparse(argument.annotation) if argument.annotation else ""

                if not name.endswith(("Request", "Create", "Update", "Write")):
                    continue

                module = module or importlib.import_module(f"routes.{path.stem}")
                schema = getattr(module, name, None)

                # A payload is a schema of ours, and `Request` is fastapi asking for the call itself.
                if isinstance(schema, type) and issubclass(schema, BaseSchema):
                    found.append((path.name, node.lineno, name, schema, only_admin))

    return found


@pytest.mark.parametrize("file, line, name, schema, only_admin", payloads(), ids=lambda value: value if isinstance(value, str) else "")
def test_only_an_administrator_may_name_whose_row_it_is(file, line, name, schema, only_admin):
    """A client that could name the owner could grant itself the row, so the account it acts on comes from the session."""
    named = sorted(set(schema.model_fields) & set(OWNERSHIP))

    if only_admin:
        return

    assert named == [], f"{file}:{line} {name} lets a client name {named}"


def test_the_crud_factory_takes_its_payload_only_from_the_roles_a_resource_names():
    """The write schemas of thirty resources name owners, and the factory is the single reason that is safe."""
    import re

    factory = pathlib.Path("helpers/crud.py").read_text()
    writes = re.findall(r"@router\.(?:post|put|delete)\(([^\n]+)\n", factory)

    assert len(writes) == 4
    assert [route for route in writes if "dependencies=[managed]" not in route] == []
    assert "managed = Depends(requires(*service.roles))" in factory


# A CPF and a phone number arrive punctuated and are stored stripped, so the schema accepts more characters than the column keeps.
PUNCTUATED = {("UserCreate", "cpf"), ("UserUpdate", "cpf"), ("SignUpRequest", "cpf"), ("UserCreate", "mobile_phone"), ("AccountUpdateRequest", "mobile_phone")}


def write_schemas() -> list[tuple[str, type, type]]:
    """Every create schema paired with the model whose columns it has to fit in."""
    import models.registry  # noqa

    from helpers.db import Base

    models = {mapper.class_.__name__: mapper.class_ for mapper in Base.registry.mappers}
    found = []

    for path in sorted(pathlib.Path("schemas").glob("*.py")):
        if path.stem == "common":
            continue

        module = importlib.import_module(f"schemas.{path.stem}")

        for name in dir(module):
            schema = getattr(module, name)

            if not (isinstance(schema, type) and hasattr(schema, "model_fields") and getattr(schema, "__module__", "") == module.__name__):
                continue

            model = models.get(name.removesuffix("Create")) if name.endswith("Create") else None

            if model is not None:
                found.append((name, schema, model))

    return found


@pytest.mark.parametrize("name, schema, model", write_schemas(), ids=lambda value: value if isinstance(value, str) else "")
def test_no_text_a_client_sends_is_longer_than_the_column_that_keeps_it(name, schema, model):
    """A payload the database refuses answers 500, and the same payload refused by the schema answers 422."""
    wrong = []

    for field, definition in schema.model_fields.items():
        column = model.__table__.columns.get(field)

        if column is None or not hasattr(column.type, "length"):
            continue

        # An enum is closed by its own values, so a length is neither reachable nor meaningful.
        if any(isinstance(part, type) and issubclass(part, Enum) for part in (definition.annotation, *typing.get_args(definition.annotation))):
            continue

        declared = next((rule.max_length for rule in definition.metadata if getattr(rule, "max_length", None) is not None), None)

        if declared is None:
            wrong.append(f"{field} has no limit and the column holds {column.type}")
        elif column.type.length is not None and declared > column.type.length and (name, field) not in PUNCTUATED:
            wrong.append(f"{field} accepts {declared} and the column holds {column.type.length}")

    assert wrong == []


def test_every_schema_that_crosses_the_wire_is_built_on_the_one_base():
    """The alias generator of the base is the only place camelCase happens, so a schema written beside it answers snake_case."""
    import sys

    from pydantic import BaseModel

    import main

    assert main.app is not None

    for folder in ("schemas", "routes"):
        for path in pathlib.Path(folder).rglob("*.py"):
            if path.name != "__init__.py":
                importlib.import_module(str(path.with_suffix("")).replace("/", "."))

    reached, stray = set(), set()

    for module in list(sys.modules.values()):
        for attribute in vars(module).values() if hasattr(module, "__dict__") else []:
            if not isinstance(attribute, type) or not issubclass(attribute, BaseModel):
                continue

            if attribute in (BaseModel, BaseSchema) or not attribute.__module__.startswith(("schemas", "routes", "helpers")):
                continue

            reached.add(attribute)

            if not issubclass(attribute, BaseSchema):
                stray.add(f"{attribute.__module__}.{attribute.__name__}")

    assert len(reached) >= 100, f"the scan reached only {len(reached)} schemas, so it is proving nothing"
    assert sorted(stray) == [], f"these answer the wire without the base that names their fields: {sorted(stray)}"


def read_schemas_paired_with_their_model() -> list[tuple[str, type, type]]:
    """Every read schema named after the model it answers for, which is how the two can be compared at all."""
    import models.registry  # noqa
    import schemas

    from helpers.db import Base

    by_name = {mapper.class_.__name__: mapper.class_ for mapper in Base.registry.mappers}
    found = []

    for module in pkgutil.iter_modules(schemas.__path__):
        loaded = importlib.import_module(f"schemas.{module.name}")

        for name, schema in vars(loaded).items():
            if not (inspect.isclass(schema) and issubclass(schema, BaseSchema) and schema.__module__ == loaded.__name__ and name.endswith("Schema")):
                continue

            model = by_name.get(name[: -len("Schema")])

            if model is not None:
                found.append((name, schema, model))

    return found


def test_no_read_schema_demands_a_column_the_table_lets_be_empty():
    """A row with nothing in that column answers the whole screen with a crash, and a shared row is exactly such a row."""
    paired = read_schemas_paired_with_their_model()
    wrong = []

    for name, schema, model in paired:
        for field, definition in schema.model_fields.items():
            column = model.__table__.columns.get(field)

            if column is not None and column.nullable and type(None) not in typing.get_args(definition.annotation):
                wrong.append(f"{name}.{field} is required and {model.__tablename__}.{column.name} is nullable")

    assert len(paired) >= 30
    assert wrong == []


@pytest.mark.parametrize("name, schema, model", write_schemas(), ids=lambda value: value if isinstance(value, str) else "")
def test_a_text_a_row_must_have_is_a_text_and_never_a_blank(name, schema, model):
    """A blank name is a card with no title, a page with an empty heading and a lookup that answers nothing, and the panel refusing it is only half a rule."""
    loose = []

    for field, definition in schema.model_fields.items():
        column = model.__table__.columns.get(field)

        if column is None or not hasattr(column.type, "length") or column.nullable or not definition.is_required():
            continue

        if any(isinstance(part, type) and issubclass(part, Enum) for part in (definition.annotation, *typing.get_args(definition.annotation))):
            continue

        if not any(getattr(rule, "min_length", None) for rule in definition.metadata):
            loose.append(field)

    assert loose == [], f"{name} accepts a blank where the table says there has to be something: {loose}"
