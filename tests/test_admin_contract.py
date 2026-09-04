import ast
import importlib
import json
import pathlib
import re

from helpers.settings import settings
from main import app
from routes.meta import CATALOG

DEFINITIONS = sorted(path for path in pathlib.Path("webapps/admin/src/resources").glob("*.js") if path.name not in ("index.js", "fields.js"))

FIELD_BUILDERS = r"\b(?:text|textarea|html|number|decimal|toggle|choice|lookup|datetime|date|json|image|file|password)\("

RESOURCE = re.compile(r"export const \w+ = \{(.*?)\n\};", re.S)


def resources() -> dict[str, str]:
    """Every definition the admin declares, read from the files that declare them."""
    found = {}

    for path in DEFINITIONS:
        for match in RESOURCE.finditer(path.read_text()):
            name = re.search(r'name: "([^"]+)"', match.group(1))

            if name:
                found[name.group(1)] = match.group(1)

    return found


def written_fields(body: str) -> set[str]:
    """Every field a form draws is a field it sends, so each one answers to a column of the write payload."""
    groups = re.search(r"groups: \[(.*?)\n    \],", body, re.S)

    if groups is None:
        return set()

    return set(re.findall(FIELD_BUILDERS + r'"([a-zA-Z_]+)"', groups.group(1)))


def accepted_fields(spec: dict, resource: str) -> set[str] | None:
    """What the create payload of a resource accepts, which is what a form may send."""
    operation = spec["paths"].get(f"/api/{resource}", {}).get("post")

    if operation is None or "requestBody" not in operation:
        return None

    reference = operation["requestBody"]["content"]["application/json"]["schema"].get("$ref")

    if reference is None:
        return None

    return set(spec["components"]["schemas"][reference.split("/")[-1]].get("properties", {}))


def test_every_field_a_form_writes_is_a_field_the_api_accepts():
    """A definition is the whole screen here, so a name the API never heard of is a field that silently does nothing."""
    spec = app.openapi()
    unknown = []

    for resource, body in resources().items():
        accepted = accepted_fields(spec, resource)

        if accepted is None:
            continue

        unknown += [f"{resource}.{field}" for field in written_fields(body) - accepted]

    assert unknown == []


def test_a_field_the_api_refuses_to_write_is_only_ever_shown():
    """A balance is the running total of a ledger, so the admin reads it and no form of the account may send it."""
    spec = app.openapi()

    assert accepted_fields(spec, "users").isdisjoint({"amount", "balances"})
    assert "amount" in spec["components"]["schemas"]["UserBalanceSchema"]["properties"]
    assert accepted_fields(spec, "user-balances") is None


def test_every_resource_the_admin_declares_is_a_resource_the_api_answers():
    """The admin is driven by definition, so a name that matches no route is a screen that can only fail."""
    api = {path.rsplit("/lookup", 1)[0].removeprefix("/api/") for path in app.openapi()["paths"] if path.endswith("/lookup")}
    definitions = pathlib.Path("webapps/admin/src/resources").glob("*.js")
    declared = {match for path in definitions if path.name not in ("index.js", "fields.js") for match in re.findall(r'^    name: "([^"]+)"', path.read_text(), re.M)}

    assert declared == api


def test_every_field_the_admin_draws_is_a_field_the_api_answers(app):
    """A column the read schema has no field for is a column that is always empty, and nothing else would ever say so."""
    schemas = app.openapi()["components"]["schemas"]
    reading = {}

    for path, item in app.openapi()["paths"].items():
        found = re.fullmatch(r"/api/([a-z\-]+)/\{record_id\}", path)

        if not found or "get" not in item:
            continue

        answer = json.dumps(item["get"].get("responses", {}).get("200", {}))
        named = [name for name in schemas if f'"#/components/schemas/{name}"' in answer]

        if named:
            reading[found.group(1)] = set(schemas[named[0]].get("properties") or {})

    # A secret is written and never read back, and an id is the key the row is reached by.
    declared_elsewhere = {"id", "password"}
    missing = []
    checked = 0

    for source in sorted(pathlib.Path("webapps/admin/src/resources").glob("*.js")):
        if source.name in ("index.js", "fields.js"):
            continue

        for block in re.findall(r"export const \w+ = \{(.*?)\n\};", source.read_text(), re.S):
            name = re.search(r'name:\s*"([a-z\-]+)"', block)

            if not name or name.group(1) not in reading:
                continue

            fields = set(re.findall(r'\{\s*name:\s*"(\w+)"', block)) | set(re.findall(r'(?:text|number|decimal|toggle|choice|lookup|datetime|date|json|image|file|password|readOnly|html|textarea)\(\s*"(\w+)"', block))

            # A filter is answered by the service, which can resolve one through a join the read schema never shows.
            filters = re.search(r"filters:\s*\[(.*?)\n    \]", block, re.S)
            fields -= set(re.findall(r'name:\s*"(\w+)"', filters.group(1))) if filters else set()

            checked += len(fields)
            missing.extend(f"{name.group(1)}.{field}" for field in sorted(fields) if field not in reading[name.group(1)] and field not in declared_elsewhere)

    assert checked >= 100, f"the scan matched only {checked} fields, so it is proving nothing"
    assert missing == []


def block_of(text: str, start: int) -> str:
    """What one brace holds, counted rather than matched, because an entry may be laid out over many lines."""
    depth = 0

    for position in range(start, len(text)):
        if text[position] == "{":
            depth += 1
        elif text[position] == "}":
            depth -= 1

            if depth == 0:
                return text[start + 1 : position]

    raise AssertionError("unbalanced catalog")


def labels_of(catalog: str, group: str) -> dict[str, set[str]]:
    """What a catalog names inside one group, however the formatter chose to lay it out."""
    text = pathlib.Path(catalog).read_text()
    body = block_of(text, text.index("{", text.index(f"\n    {group}: ")))
    found = {}

    for entry in re.finditer(r'"?([\w-]+)"?: \{', body):
        found[entry.group(1)] = set(re.findall(r"(\w+):", block_of(body, entry.end() - 1)))

    return found


def catalogs() -> list[str]:
    """The panel offers three languages, and naming two of them is what left the third unchecked."""
    found = sorted(str(path) for path in pathlib.Path("webapps/admin/src/i18n").glob("*.js") if path.name != "index.js")

    assert len(found) == len(settings.languages), f"the panel carries {len(found)} catalogs and the application offers {len(settings.languages)}"

    return found


def test_every_enum_value_the_api_publishes_is_named_in_every_catalog():
    """A value the admin draws without a label shows the reader the raw key the database stores."""
    missing = []

    for catalog in catalogs():
        named = labels_of(catalog, "enum")

        for name, enum in CATALOG.items():
            for value in enum:
                if value.value not in named.get(name, set()):
                    missing.append(f"{catalog}: enum.{name}.{value.value}")

    assert missing == []


def enum_names_the_panel_draws() -> set[str]:
    """A field names its enum in two spellings, and reading one of them is reading half the panel."""
    named = set()

    for path in DEFINITIONS:
        body = path.read_text()
        named |= set(re.findall(r'enumName: "([a-z_]+)"', body))
        named |= set(re.findall(r'choice\("[A-Za-z]+", "[^"]+", "([a-z_]+)"', body))

    return named


def test_every_enum_the_panel_draws_is_an_enum_the_api_publishes():
    """A name the catalog has no answer for draws an empty select, which reads as a field with nothing to choose."""
    named = enum_names_the_panel_draws()

    assert len(named) >= 24
    assert sorted(named - set(CATALOG)) == []


def test_every_enum_the_api_publishes_is_drawn_by_the_panel():
    """A catalog nobody draws is a set the API carries to every screen for nothing."""
    assert sorted(set(CATALOG) - enum_names_the_panel_draws()) == []


def test_no_catalog_names_an_enum_value_the_api_no_longer_publishes():
    """A label left behind is a value somebody will look for and never find."""
    published = {name: {value.value for value in enum} for name, enum in CATALOG.items()}
    orphans = []

    for catalog in catalogs():
        for name, values in labels_of(catalog, "enum").items():
            orphans += [f"{catalog}: enum.{name}.{value}" for value in values - published.get(name, set())]

    assert orphans == []


def test_every_resource_the_admin_declares_is_named_in_every_catalog():
    for catalog in catalogs():
        named = labels_of(catalog, "resource")

        for name in resources():
            assert {"title", "singular"} <= named.get(name, set()), f"{catalog}: resource.{name}"


def listed(body: str, key: str) -> str | None:
    """What a list holds, counted rather than matched, because a definition fits on one line or on twenty."""
    marker = body.find(f"{key}: [")

    if marker < 0:
        return None

    start = body.index("[", marker)
    depth = 0

    for position in range(start, len(body)):
        if body[position] == "[":
            depth += 1
        elif body[position] == "]":
            depth -= 1

            if depth == 0:
                return body[start + 1 : position]

    raise AssertionError(f"unbalanced {key}")


def camel(name: str) -> str:
    head, *rest = name.split("_")

    return head + "".join(part.title() for part in rest)


def services_by_prefix() -> dict:
    found = {}

    for path in sorted(pathlib.Path("routes").glob("*.py")):
        tree = ast.parse(path.read_text())
        module = importlib.import_module(f"routes.{path.stem}")

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or getattr(node.func, "id", "") not in ("build_router", "build_readonly_router"):
                continue

            prefix = next(argument.value for argument in node.args if isinstance(argument, ast.Constant) and str(argument.value).startswith("/"))
            found[prefix.strip("/")] = getattr(module, node.args[0].id)

    return found


def test_every_filter_the_admin_draws_is_a_filter_the_service_applies():
    """A filter nothing answers is a control that changes the grid by not changing it."""
    services = services_by_prefix()
    ignored = []
    checked = 0

    for name, body in resources().items():
        service = services.get(name)
        filters = listed(body, "filters") if service else None

        if filters is None:
            continue

        drawn = set(re.findall(r'\bname: "(\w+)"', filters)) | set(re.findall(FIELD_BUILDERS + r'"(\w+)"', filters))
        applied = {field.split(".")[0] for field in service.filter_fields}

        checked += len(drawn)
        ignored += [f"{name}.{field}" for field in sorted(drawn) if field not in applied and field not in {camel(one) for one in applied}]

    assert checked >= 40, f"the scan matched only {checked} filters, so it is proving nothing"
    assert ignored == []


def test_every_column_the_grid_offers_to_sort_by_is_a_column_the_service_orders_by():
    """A header that sorts by nothing answers the same list, and the reader reads that as an order that exists."""
    services = services_by_prefix()
    wrong = []

    for name, body in resources().items():
        service = services.get(name)
        declared = listed(body, "ordering") if service else None

        if declared is None:
            continue

        offered = re.findall(r'"(\w+)"', declared)
        answered = {camel(field) for field in service.ordering_fields}

        wrong += [f"{name}.{field}" for field in offered if field not in answered]
        wrong += [f"{name} does not offer {camel(field)}" for field in service.ordering_fields if camel(field) not in offered]

    assert "\n".join(sorted(wrong)) == ""


def test_every_resource_the_admin_lists_says_what_it_sorts_by():
    services = services_by_prefix()
    missing = [name for name in resources() if name in services and listed(resources()[name], "ordering") is None]

    assert missing == []


def test_a_grid_draws_a_search_box_when_and_only_when_the_service_searches():
    """A box that searches nothing is a control that answers by not answering, and a resource that searches without one hides what it can do."""
    services = services_by_prefix()
    wrong = []

    for name, body in resources().items():
        service = services.get(name)

        if service is None:
            continue

        draws = "searchable: false" not in body
        searches = bool(service.search_fields or getattr(service, "text_search_fields", ()))

        if draws != searches:
            wrong.append(f"{name}: desenha={draws} procura={searches}")

    assert "\n".join(sorted(wrong)) == ""


def refers_to(prop: dict) -> str | None:
    """A nullable relation is an anyOf, so the referenced schema is never at the top of the property."""
    for shape in [prop, *prop.get("anyOf", []), *prop.get("allOf", [])]:
        if "$ref" in shape:
            return shape["$ref"].rsplit("/", 1)[-1]

    return None


def test_every_reference_field_the_grid_shows_is_a_field_the_related_schema_answers(app):
    """A reference column names a field of the row it points at, and one that is not there draws a cell that is always empty."""
    schemas = app.openapi()["components"]["schemas"]
    reading = {}
    checked = 0

    for path, item in app.openapi()["paths"].items():
        found = re.fullmatch(r"/api/([a-z\-]+)/\{record_id\}", path)

        if not found or "get" not in item:
            continue

        answer = json.dumps(item["get"].get("responses", {}).get("200", {}))
        named = [name for name in schemas if f'"#/components/schemas/{name}"' in answer]

        if named:
            reading[found.group(1)] = named[0]

    missing = []

    for source in sorted(pathlib.Path("webapps/admin/src/resources").glob("*.js")):
        if source.name in ("index.js", "fields.js"):
            continue

        for block in re.findall(r"export const \w+ = \{(.*?)\n\};", source.read_text(), re.S):
            name = re.search(r'name:\s*"([a-z\-]+)"', block)

            if not name or name.group(1) not in reading:
                continue

            for column, reference in re.findall(r'\{\s*name:\s*"(\w+)".*?referenceField:\s*"([\w.]+)"', block):
                checked += 1
                current = schemas[reading[name.group(1)]]

                for step in [column, *reference.split(".")]:
                    prop = (current.get("properties") or {}).get(step)

                    if prop is None:
                        missing.append(f"{name.group(1)}.{column} -> {reference}")
                        break

                    nested = refers_to(prop)
                    current = schemas[nested] if nested else {}

    assert checked >= 15, f"the scan matched only {checked} reference columns, so it is proving nothing"
    assert missing == []


def test_every_resource_the_admin_lets_write_is_a_resource_the_api_lets_write():
    """A form the API answers 405 to is a screen that can only waste what someone typed into it."""
    paths = app.openapi()["paths"]
    wrong = []

    for name, body in resources().items():
        offers_write = "readOnly: true" not in body
        accepts_write = "post" in paths.get(f"/api/{name}", {})

        if offers_write != accepts_write:
            wrong.append(f"{name}: admin offers write={offers_write}, api accepts it={accepts_write}")

    assert wrong == []


def declared_file_fields(body: str) -> dict[str, str]:
    return {found.group(1): found.group(2) for found in re.finditer(r'(?:image|file)\("(\w+)", "[^"]+", "([a-z-]+)"', body)}


def services_by_resource() -> dict:
    """The service behind each admin resource, read from the very call that binds a router to a path."""
    import ast
    import importlib
    import pathlib as paths

    found = {}

    for path in sorted(paths.Path("routes").glob("*.py")):
        module = importlib.import_module(f"routes.{path.stem}")

        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call) or getattr(node.func, "id", "") not in ("build_router", "build_readonly_router"):
                continue

            path_argument = next(argument for argument in node.args if isinstance(argument, ast.Constant) and str(argument.value).startswith("/"))
            found[path_argument.value.lstrip("/")] = getattr(module, node.args[0].id)

    return found


def test_every_file_field_a_form_writes_is_one_its_service_declares_with_the_same_purpose():
    """A column left out of file_fields keeps the old file in the bucket on every replace, and a purpose that disagrees points the deletion at another folder."""
    services = services_by_resource()
    offenders = []
    seen = 0

    for resource, body in resources().items():
        service = services.get(resource)

        if service is None:
            continue

        for name, purpose in declared_file_fields(body).items():
            seen += 1

            if name not in service.file_fields:
                offenders.append(f"{resource}.{name} is written by the admin and the service declares no purpose for it")
            elif service.file_fields[name].value != purpose:
                offenders.append(f"{resource}.{name} is {service.file_fields[name].value} and the admin sends {purpose}")

    assert seen >= 5, f"the scan matched only {seen} file fields, so it is proving nothing"
    assert offenders == []


def test_no_catalog_of_the_admin_carries_a_label_nothing_draws():
    """A rule that left takes its screen with it, and the label it was drawn with stays behind reading as one still in use."""
    import pathlib
    import re

    root = pathlib.Path("webapps/admin/src")
    drawn = "\n".join(path.read_text() for path in root.rglob("*") if path.is_file() and path.suffix in (".js", ".vue") and "i18n" not in path.parts)
    drawn += "\n".join(path.read_text() for path in pathlib.Path("webapps/admin/tests").rglob("*") if path.is_file())

    catalog = (root / "i18n" / "en.js").read_text()
    published = {f"enum.{name}.{member.value}" for name, enum in CATALOG.items() for member in enum}

    section = None
    orphans = []
    checked = 0

    for line in catalog.splitlines():
        header = re.match(r"^ {4}(\w+): \{", line)
        entry = re.match(r"^ {8}(\w+):", line)

        if header:
            section = header.group(1)

        if not entry or section is None:
            continue

        checked += 1
        name = entry.group(1)
        key = f"{section}.{name}"

        if section == "enum":
            if not any(value.startswith(f"{key}.") for value in published):
                orphans.append(key)

            continue

        if key not in drawn and f'"{name}"' not in drawn and f"'{name}'" not in drawn:
            orphans.append(key)

    assert checked >= 200, f"the scan read only {checked} labels, so it is proving nothing"
    assert orphans == [], f"the admin carries labels nothing draws: {orphans}"


def test_the_panel_never_draws_a_resource_for_a_role_the_api_refuses():
    """What a menu offers is what the API answers, and the panel is handed that set instead of declaring one of its own."""
    import pathlib
    import re

    from helpers.crud import RESOURCES

    drawn = set()

    for path in pathlib.Path("webapps/admin/src/resources").glob("*.js"):
        drawn |= set(re.findall(r'^    name: "([^"]+)"', path.read_text(), re.M))

    assert drawn, "the scan read no resource out of the panel, so it is proving nothing"
    assert drawn <= set(RESOURCES), f"the panel draws what the API serves nothing for: {sorted(drawn - set(RESOURCES))}"

    # Who reaches a resource is one line on its service, and the panel is handed the answer rather than declaring it again.
    definitions = "\n".join(path.read_text() for path in pathlib.Path("webapps/admin/src/resources").glob("*.js"))
    declared = re.findall(r"^\s{4}(roles|allowedRoles|permissions):", definitions, re.M)

    assert declared == [], f"a resource of the panel says who reaches it, and that decision belongs to the service: {declared}"


def test_every_option_a_form_offers_is_one_its_reader_can_resolve():
    """A form nobody can fill is a form nobody can send, so a lookup a role cannot resolve is a screen it should not have been given."""
    import pathlib
    import re

    from helpers.crud import RESOURCES

    pointed = re.compile(r'(?:lookup\("[^"]+", "[^"]+", "([^"]+)"|type: "lookup", resource: "([^"]+)")')
    unfillable = []
    checked = 0

    for path in pathlib.Path("webapps/admin/src/resources").glob("*.js"):
        body = path.read_text()

        for block in re.finditer(r'^    name: "([^"]+)",(.*?)^\};', body, re.S | re.M):
            drawn, definition = block.group(1), block.group(2)
            service = RESOURCES.get(drawn)

            if service is None:
                continue

            for match in pointed.finditer(definition):
                target = RESOURCES.get(match.group(1) or match.group(2))

                if target is None:
                    continue

                checked += 1
                resolving = set(target.lookup_roles or target.roles)

                if not set(service.roles) <= resolving:
                    unfillable.append(f"{drawn} offers {match.group(1) or match.group(2)} to a role that cannot resolve it")

    assert checked >= 20, f"the scan read only {checked} lookups, so it is proving nothing"
    assert unfillable == [], unfillable


# The JSON-LD of the home is built by the server and never typed by anyone, so it is the one value the panel does not author.
BUILT_BY_THE_SERVER = {"organization"}

RENDERED_AS_MARKUP = re.compile(r"\{\{\s*([\w.]+)\s*\|\s*safe\s*\}\}")


def test_every_value_the_site_renders_as_markup_is_one_the_panel_authors_as_markup():
    """Only what an operator wrote in the editor is rendered, because escaping is what makes every other value safe."""
    authored = {match for path in DEFINITIONS for match in re.findall(r'\bhtml\("(\w+)"', path.read_text())}
    rendered = []

    for template in sorted(pathlib.Path("templates").rglob("*.html")):
        for match in RENDERED_AS_MARKUP.finditer(template.read_text()):
            rendered.append((str(template), match.group(1).split(".")[-1]))

    assert len(rendered) >= 4, f"the scan read only {len(rendered)} values, so it is proving nothing"
    assert authored, "no editor field was found, so the comparison would pass against nothing"

    loose = [f"{where} renders {name}, which the panel does not author as markup" for where, name in rendered if name not in authored | BUILT_BY_THE_SERVER]

    assert loose == [], loose
