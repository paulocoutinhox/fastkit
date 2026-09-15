import ast
import pathlib
import re

from app import app
from enums.integration import Provider
from enums.upload import UploadPurpose
from enums.user import UserRole
from helpers.scheduler import app as tasks
from helpers.settings import settings
from services.gateway import PROVIDERS

DOCS = ["CLAUDE.md", "README.md"] + sorted(str(path) for path in pathlib.Path("docs").glob("*.md"))


def claimed(pattern: str) -> set[int]:
    """What the documentation states about the size of the surface, read from every file that states it, in either language it is written in."""
    found = set()

    for name in DOCS:
        # A number written in bold is the same claim, and reading only the plain one let a count drift for as long as it was emphasised.
        written = pathlib.Path(name).read_text().replace("**", "")
        found |= {int(number) for number in re.findall(pattern, written)}

    return found


def test_the_documented_number_of_paths_is_the_number_the_api_answers():
    """A number written in prose goes stale in silence, so the suite is what keeps it honest."""
    assert claimed(r"(\d+) (?:caminhos|paths)") == {len(app.openapi()["paths"])}


def test_the_documented_number_of_flows_is_the_number_the_suite_drives():
    """The swap flow left with the feature and the prose kept counting it."""
    flows = len(re.findall(r"^async def test_", pathlib.Path("tests/test_app_flows.py").read_text(), re.MULTILINE))

    assert claimed(r"(\d+) (?:fluxos|flows)") == {flows}


def test_the_documented_number_of_route_descriptions_is_the_number_the_api_publishes():
    """A docstring is what whoever integrates reads, so the count of them is a claim about the published documentation."""
    described = [operation for path in app.openapi()["paths"].values() for operation in path.values() if operation.get("description")]

    assert claimed(r"(\d+) (?:descrições|route descriptions)") == {len(described)}


def test_the_documented_number_of_tables_is_the_number_the_schema_builds():
    """It drifted once already, and a wrong count is read as a schema somebody miscounted rather than a doc nobody updated."""
    import models.registry  # noqa: F401
    from helpers.db import Base

    assert claimed(r"(\d+) (?:tabelas|tables)") == {len(Base.metadata.sorted_tables)}


def test_the_documented_shape_of_the_schema_is_the_shape_it_declares():
    """These are only ever seen by raising a server, so nothing was counting them and one of them drifted by thirty."""
    import models.registry  # noqa: F401
    from helpers.db import Base

    indexes = sum(len(table.indexes) + len([rule for rule in table.constraints if type(rule).__name__ == "UniqueConstraint"]) for table in Base.metadata.sorted_tables)
    searched = len([index for table in Base.metadata.sorted_tables for index in table.indexes if index.dialect_options.get("mysql", {}).get("prefix") == "FULLTEXT"])

    assert claimed(r"(\d+) (?:índices e uniques|indexes and uniques)") == {indexes}
    assert claimed(r"(\d+) `FULLTEXT`") == {searched}


def prose_of(body: str) -> str:
    """The sentences of a page, with the code taken out, because a semicolon inside a snippet is the language and not the writing."""
    return re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", body, flags=re.S))


def test_no_sentence_anywhere_is_split_by_a_semicolon():
    """Two ideas glued by a semicolon read as one, and this file asks for two sentences everywhere it asks for anything."""
    import ast

    SPLIT = re.compile(r"[a-záéíóúâêôãõç]; [a-záéíóúâêôãõç]")

    split, read = [], 0

    for name in [*DOCS, *PUBLIC]:
        path = pathlib.Path(name)
        read += 1

        for number, line in enumerate(prose_of(path.read_text()).split("\n"), 1):
            if SPLIT.search(line):
                split.append(f"{path}:{number} {line.strip()[:70]}")

    from tests.test_layout import sources

    for path in sources():
        body = path.read_text()
        read += 1

        for number, line in enumerate(body.split("\n"), 1):
            if line.strip().startswith("#") and SPLIT.search(line):
                split.append(f"{path}:{number} {line.strip()[:70]}")

        for node in ast.walk(ast.parse(body)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and (written := ast.get_docstring(node)) and SPLIT.search(written):
                split.append(f"{path}:{getattr(node, 'lineno', 1)} {written[:70]}")

    assert read >= 150, f"the scan read only {read} files, so it is proving nothing"
    assert SPLIT.search("one thing; another thing"), "the scan no longer recognises a sentence split by a semicolon"
    assert split == [], f"these glue two sentences with a semicolon: {split}"


# A word an english sentence borrows with its marks on, named with the reason it keeps them.
ACCENTED_IN_ENGLISH: dict[str, str] = {}


def test_the_running_code_is_written_in_english():
    """The internal documentation is written in one language and the code in another, and a comment that drifted is the half a reader outside this repository cannot follow."""
    import ast

    from tests.test_layout import sources

    MARKED = re.compile(r"[áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]")

    borrowed, read = [], 0

    for path in sources():
        body = path.read_text()
        read += 1
        written = [(number, line.strip()) for number, line in enumerate(body.split("\n"), 1) if line.strip().startswith("#")]
        written += [(getattr(node, "lineno", 1), said) for node in ast.walk(ast.parse(body)) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and (said := ast.get_docstring(node))]

        for number, text in written:
            marked = {word for word in re.findall(r"\S+", text) if MARKED.search(word)} - set(ACCENTED_IN_ENGLISH)

            if marked:
                borrowed.append(f"{path}:{number} {sorted(marked)}")

    assert read >= 140, f"the scan read only {read} modules, so it is proving nothing"
    assert MARKED.search("o que este método faz"), "the scan no longer recognises a sentence written in the other language"
    assert borrowed == [], f"these are written in the language this file is written in, and the code is written in english: {borrowed}"


def test_no_borrowed_word_is_excused_that_nothing_writes_any_more():
    """An excuse that outlives the sentence it was written for is one nobody reads again, and it would cover the next word to carry those marks."""
    from tests.test_layout import sources

    written = "\n".join(path.read_text() for path in sources())
    stale = sorted(word for word in ACCENTED_IN_ENGLISH if word not in written)

    assert stale == [], f"these are excused and nothing writes them: {stale}"


def test_the_documented_windows_are_the_windows_the_settings_declare():
    """How long a table keeps a row is close to a promise, and a number in prose that nothing reads goes stale in silence."""
    from config.base import CacheSettings, RetentionSettings

    body = pathlib.Path("CLAUDE.md").read_text()
    kept = sorted(int(number) for number in re.findall(r"^\| `[^|]+\| (\d+) dias \|", body, re.M))
    lived = sorted({int(number) for number in re.findall(r"^\| `[^|]+\| (\d+) s \|", body, re.M)})

    declared = sorted(field.default for name, field in RetentionSettings.model_fields.items() if name.endswith("_days"))
    spaces = sorted({field.default for name, field in CacheSettings.model_fields.items() if name.endswith("_ttl")})

    assert len(declared) >= 7, f"the scan found only {len(declared)} retention windows, so it is proving nothing"
    assert len(spaces) >= 4, f"the scan found only {len(spaces)} cache lifetimes, so it is proving nothing"
    assert kept == declared, f"the documentation keeps rows for {kept} days and the settings for {declared}"
    assert lived == spaces, f"the documentation holds an answer for {lived} seconds and the settings for {spaces}"


def test_the_documented_number_of_groups_is_the_number_the_api_publishes():
    groups = {tag for path in app.openapi()["paths"].values() for operation in path.values() for tag in operation.get("tags", [])}

    assert claimed(r"(\d+) (?:grupos|groups)") == {len(groups)}


def test_the_documented_number_of_resources_is_the_number_the_admin_declares():
    definitions = pathlib.Path("webapps/admin/src/resources").glob("*.js")
    declared = {match for path in definitions if path.name not in ("index.js", "fields.js") for match in re.findall(r'^    name: "([^"]+)"', path.read_text(), re.M)}

    assert claimed(r"(\d+) (?:recursos|resources)") == {len(declared)}


def test_the_public_site_never_links_to_the_admin():
    """The panel is where an operator works, and a link to it on a page every visitor reads is an invitation nobody meant to send."""
    from helpers.settings import settings

    checked = 0

    for folder in ("webapps/site/src", "templates/global/site", "templates/tenants"):
        for path in pathlib.Path(folder).rglob("*"):
            if not path.is_file():
                continue

            checked += 1

            assert settings.admin_path not in path.read_text(errors="ignore"), path

    assert checked >= 30, f"the scan read only {checked} files, so it is proving nothing"


def test_no_path_a_client_types_carries_an_underscore():
    """A route is a public address, so it goes in dashes — the underscore belongs to the python identifier behind it, never to the URL."""
    drawn = set(re.findall(r'@router\.(?:get|post)\("([^"]+)"', "\n".join(path.read_text() for path in pathlib.Path("routes/site").glob("*.py"))))
    offenders = []

    for path in set(app.openapi()["paths"]) | drawn:
        offenders += [f"{path}: {part}" for part in path.split("/") if part and not part.startswith("{") and "_" in part]

    assert len(drawn) >= 40, f"the scan read only {len(drawn)} pages of the site, so it is proving nothing"
    assert offenders == []


def test_the_folder_of_a_stored_file_is_a_public_address_too():
    from helpers.settings import settings

    assert [rule.folder for rule in settings.uploads.values() if "_" in rule.folder] == []


def test_a_link_between_two_things_carries_no_state_of_its_own():
    """Undoing an association is deleting the row, and whether either side is on air is said by that side."""
    import models.registry  # noqa: F401
    from helpers.db import Base

    links = {"subscription_plan_entitlement"}
    offenders = []

    for mapper in Base.registry.mappers:
        table = mapper.local_table.name

        if table in links and "active" in {column.key for column in mapper.column_attrs}:
            offenders.append(table)

    assert offenders == []


def test_the_documented_jobs_are_the_jobs_the_scheduler_registers():
    """A table of scheduled work goes stale the day two jobs become one, and nothing else notices."""
    documented = set(re.findall(r"^\| `(\w+)` \| (?:a cada|\d{2}:\d{2})", pathlib.Path("CLAUDE.md").read_text(), re.M))

    assert documented == set(tasks.tasks)


# What is named here belongs to somebody else: the engines under the database, the django this came from, and SQL itself.
FOREIGN = {
    "PascalCase",
    "TYPE_CHECKING",
    "UPDATE",
    "INSERT",
    "SAVEPOINT",
    "_ibfk_N",
    "declarative_base",
    "lock_wait_timeout",
    "CacheError",
    "MetaData",
    "cachefy_entry",
    "queuefy_run",
    "sk_live_",
    "whsec_",
    "after_rollback",
    "on_commit",
    "ActiveStorage",
    "data.object.object",
    "dataset.nome",
    "dataset.uploadName",
    "pytest.ini",
}

# What every reader outside this repository reads, which is the documentation nothing was checking.
PUBLIC = ["README.md"] + sorted(str(path) for path in pathlib.Path("docs").glob("*.md"))

SEARCHED = ("config", "enums", "helpers", "models", "schemas", "services", "routes", "jobs", "tests", "webapps/admin/src", "webapps/site/src", "templates", "locale")


def written() -> str:
    root = pathlib.Path(".")
    files = [path for folder in SEARCHED for path in (root / folder).rglob("*") if path.is_file() and path.suffix in (".py", ".js", ".vue", ".json", ".html")]
    names = [str(path) for folder in SEARCHED for path in (root / folder).rglob("*")]

    return "\n".join([path.read_text(errors="ignore") for path in files] + names + [pathlib.Path(name).read_text() for name in ("Makefile", "app.py", "manage.py", "nginx.conf", "docker-compose.yml", "entrypoint.sh")])


def symbols_of(*names: str) -> set[str]:
    """Every project symbol the prose names, which is what a rename leaves pointing at nothing."""
    prose = "\n".join(pathlib.Path(name).read_text() for name in names)

    # A setting is a name of this project as much as a function is, and one written all in lowercase was never read.
    return {name for name in re.findall(r"`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)`", prose) if "_" in name or name[0].isupper() or "." in name}


def shown(code: str, name: str) -> bool:
    """A dotted name is a member of something, so the code has to show it as one rather than as a word that happens to appear in a comment."""
    last = name.split(".")[-1]

    if "." not in name:
        return bool(re.search(rf"\b{re.escape(last)}\b", code))

    return bool(re.search(rf"\.{re.escape(last)}\b|\b{re.escape(last)}\s*[:=]|def {re.escape(last)}\b|class {re.escape(last)}\b", code))


def test_every_symbol_the_documentation_names_still_exists():
    """A rename leaves the prose pointing at nothing, and whoever follows it looks for a function that is gone."""
    cited = symbols_of("CLAUDE.md")
    code = written()

    missing = sorted(name for name in cited - FOREIGN if not shown(code, name))

    assert len(cited) >= 200, f"the scan read only {len(cited)} symbols out of the prose, so it is proving nothing"
    assert missing == [], f"the documentation names what the code no longer has: {missing}"


def test_every_symbol_the_public_documentation_names_still_exists():
    """The readme and the guides are what somebody who never saw this repository reads, and nothing was checking them."""
    cited = symbols_of(*PUBLIC)
    code = written()

    missing = sorted(name for name in cited - FOREIGN if not shown(code, name))

    assert len(cited) >= 80, f"the scan read only {len(cited)} symbols out of the public documentation, so it is proving nothing"
    assert missing == [], f"the public documentation names what the code no longer has: {missing}"


LEADS = ("> ", "- ", "* ") + tuple(f"{number}. " for number in range(1, 10))


def opener(line: str) -> str | None:
    """The first word of a sentence, answered only when it is written in lowercase."""
    body = line.lstrip()

    for lead in LEADS:
        while body.startswith(lead):
            body = body[len(lead) :].lstrip()

    word = re.match(r"`?([A-Za-zÀ-ÿ][\w./-]*)", body.lstrip("*_"))

    return word.group(1) if word and word.group(1)[0].islower() else None


def test_no_sentence_of_the_documentation_opens_in_lowercase():
    """A name written in lowercase keeps its spelling, so the sentence is what gets rewritten and never the name."""
    offenders, read = [], 0

    for page in ["CLAUDE.md"] + PUBLIC:
        inside, carries = False, False

        for number, line in enumerate(pathlib.Path(page).read_text().splitlines(), 1):
            if line.startswith("```"):
                inside, carries = not inside, False
                continue

            stripped = line.strip()

            if inside or not stripped or stripped.startswith(("|", "#")):
                carries = False
                continue

            if not carries:
                read += 1

                if opener(stripped):
                    offenders.append(f"{page}:{number} {stripped[:70]}")

            # A full stop ends a sentence, and anything else carries it into the line below.
            carries = not stripped.endswith((".", "!", "?"))

    assert read >= 800, f"the scan read only {read} sentences, so it is proving nothing"
    assert offenders == [], f"these open in lowercase, and it is the sentence that gets rewritten: {offenders[:10]}"


def test_every_address_the_public_documentation_names_is_one_the_application_answers():
    """An address is what somebody integrating types, so a guide naming one this application does not serve is worse than a guide that names none."""
    from tests.test_admin_audit import declared

    served = {}

    for name, _ in declared(app):
        method, path = name.split(" ", 1)
        served.setdefault(path, set()).add(method)

    named = [(page, method, address.rstrip(".,`")) for page in PUBLIC for method, address in re.findall(r"\b(GET|POST|PUT|PATCH|DELETE)\s+`?(/[\w/{}.-]+)", pathlib.Path(page).read_text())]
    wrong = sorted(f"{page}: {method} {address}" for page, method, address in named if method not in served.get(address, set()))

    assert len(named) >= 20, f"the scan read only {len(named)} addresses out of the public documentation, so it is proving nothing"
    assert wrong == [], f"the public documentation names an address the application does not answer: {wrong}"


def code_of(body: str) -> str:
    """What a page offers as something to type, which is what is fenced or written in code and never the prose around it."""
    return "\n".join(re.findall(r"```[a-z]*\n(.*?)```", body, re.S) + re.findall(r"`([^`\n]+)`", body))


def test_every_command_the_public_documentation_offers_is_one_the_makefile_answers():
    """A renamed recipe leaves the first command a stranger types answering nothing."""
    recipes = set(re.findall(r"^([a-z][\w-]*):", pathlib.Path("Makefile").read_text(), re.M))
    offered = {target for name in PUBLIC for target in re.findall(r"make ([a-z][\w-]*)", code_of(pathlib.Path(name).read_text()))}

    assert len(offered) >= 10, f"the scan read only {len(offered)} commands, so it is proving nothing"
    assert sorted(offered - recipes) == [], f"the public documentation offers a command the Makefile does not answer: {sorted(offered - recipes)}"


# What a tool reads rather than a person, so it stays exactly as the tool expects.
PRAGMAS = ("fmt:", "noqa", "type:", "pragma:", "pylint:", "ruff:", "isort:", "mypy:", "nosec", "!", "-*-", "eslint", "prettier", "@ts-", "stylelint")

COMMENTED = ("config", "enums", "helpers", "jobs", "models", "routes", "schemas", "services", "tests", "webapps/admin/src", "webapps/admin/tests", "webapps/site/src", "webapps/site/tests")


def spoken(body: str) -> bool:
    """Answers whether a comment is prose a person reads, rather than a directive a tool does."""
    return bool(body) and not body.lower().startswith(PRAGMAS) and not body.lower().startswith(("http://", "https://"))


def commented_files() -> list[pathlib.Path]:
    root = pathlib.Path(".")

    return [path for folder in COMMENTED for path in (root / folder).rglob("*") if path.is_file() and path.suffix in (".py", ".js", ".vue")] + [pathlib.Path("app.py"), pathlib.Path("manage.py")]


def test_every_comment_is_a_sentence():
    """A fragment with no capital and no full stop reads as a note somebody left behind, and the next one is written to match it."""
    offenders = []
    checked = 0

    for path in commented_files():
        for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            stripped = line.strip()
            marker = "#" if stripped.startswith("#") else "//" if stripped.startswith("//") else None

            if marker is None:
                continue

            body = stripped[len(marker) :].strip()

            if not spoken(body):
                continue

            checked += 1

            if not body[0].isupper() or not body.endswith((".", "!", "?")):
                offenders.append(f"{path}:{number} {body[:70]}")

    assert checked >= 150, f"the scan read only {checked} comments, so it is proving nothing"
    assert offenders == [], f"these are not written as sentences: {offenders[:10]}"


def test_every_docstring_is_a_sentence():
    """The docstring of a route is published in the API documentation, so it is read by whoever integrates and never only by us."""
    import ast

    offenders = []
    checked = 0

    for path in commented_files():
        if path.suffix != ".py":
            continue

        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                continue

            body = ast.get_docstring(node, clean=False)

            if not body:
                continue

            checked += 1

            if "\n" in body:
                offenders.append(f"{path}:{getattr(node, 'lineno', 1)} spans more than one line")
            elif not body[0].isupper() or not body.endswith((".", "!", "?")):
                offenders.append(f"{path}:{getattr(node, 'lineno', 1)} {body[:70]}")

    assert checked >= 400, f"the scan read only {checked} docstrings, so it is proving nothing"
    assert offenders == [], f"these are not written as sentences: {offenders[:10]}"


# What the prose shows as code, which is read as the real thing and copied as the real thing.
EXAMPLED = ["CLAUDE.md", "README.md"] + sorted(str(path) for path in pathlib.Path("docs").glob("*.md"))

SIGNATURE = re.compile(r"^(?:async )?def ([a-z_]+)\((self[^)]*)\)")


def parameters(signature: str) -> list[str]:
    """The names a signature takes, with the annotation and the default of each one dropped."""
    return [part.split(":")[0].split("=")[0].strip() for part in signature.split(",")]


def declared_in_code() -> dict[str, set[tuple[str, ...]]]:
    found: dict[str, set[tuple[str, ...]]] = {}

    for folder in ("config", "enums", "helpers", "models", "schemas", "services", "routes", "jobs"):
        for path in pathlib.Path(folder).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found.setdefault(node.name, set()).add(tuple(argument.arg for argument in node.args.args))

    return found


def test_every_method_the_documentation_shows_takes_what_the_code_takes():
    """An example is copied as it is written, so a parameter the code grew and the prose did not is a caller that breaks."""
    code = declared_in_code()
    offenders = []
    checked = 0

    for name in EXAMPLED:
        for block in re.findall(r"```python\n(.*?)```", pathlib.Path(name).read_text(), re.S):
            for line in block.splitlines():
                match = SIGNATURE.match(line.strip())

                if match is None:
                    continue

                checked += 1
                shown = tuple(parameters(match.group(2)))

                if shown not in code.get(match.group(1), set()):
                    offenders.append(f"{name}: {match.group(1)}{shown}")

    assert checked >= 3, f"the scan read only {checked} signatures, so it is proving nothing"
    assert offenders == [], f"the documentation shows a signature the code does not have: {offenders}"


def test_every_class_the_documentation_declares_is_declared_that_way():
    """A base class named in an example is the one a reader subclasses, and the wrong one sends them to the wrong rules."""
    code = "\n".join(path.read_text() for folder in ("config", "enums", "helpers", "models", "schemas", "services", "routes", "jobs") for path in pathlib.Path(folder).rglob("*.py"))
    offenders = []
    checked = 0

    for name in EXAMPLED:
        for block in re.findall(r"```python\n(.*?)```", pathlib.Path(name).read_text(), re.S):
            first = block.strip().splitlines()[0]

            if not first.startswith("class ") or "(" not in first:
                continue

            checked += 1

            if first not in code:
                offenders.append(f"{name}: {first}")

    assert checked >= 3, f"the scan read only {checked} declarations, so it is proving nothing"
    assert offenders == [], f"the documentation declares a class the code does not: {offenders}"


def test_every_page_of_the_documentation_is_one_the_readme_points_at():
    """A page nothing links to is a page nobody opens, and one linked that is gone is a reader sent nowhere."""
    published = {path.name for path in pathlib.Path("docs").glob("*.md")}
    linked = set(re.findall(r"\]\(docs/([\w-]+\.md)\)", pathlib.Path("README.md").read_text()))

    assert published, "the scan found no documentation at all, so it is proving nothing"
    assert linked - published == set(), f"the readme points at documentation that is not there: {sorted(linked - published)}"
    assert published - linked == set(), f"this documentation is published and nothing points at it: {sorted(published - linked)}"


def anchor_of(title: str) -> str:
    """The fragment a heading answers to, reduced the way a markdown renderer reduces one."""
    cleaned = re.sub(r"[`*_]", "", title).lower()

    return re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", cleaned)).strip("-")


def test_every_link_of_the_documentation_lands_on_something():
    """A renamed file or a retitled section leaves a dead link in front of whoever arrives, and nothing else here reads one."""
    written = [pathlib.Path("README.md"), pathlib.Path("CLAUDE.md")] + [pathlib.Path(name) for name in PUBLIC if name != "README.md"]
    headings = {path: {anchor_of(found) for found in re.findall(r"^#{1,6}\s+(.+?)\s*$", path.read_text(), re.M)} for path in written}

    broken, read = [], 0

    for path in written:
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
            if target.startswith(("http://", "https://", "mailto:")):
                continue

            read += 1
            where, _, anchor = target.partition("#")
            landing = path.parent / where if where else path

            if where and landing not in headings:
                broken.append(f"{path} -> {target} names no page of this documentation")
            elif anchor and anchor_of(anchor) not in headings[landing]:
                broken.append(f"{path} -> {target} names no heading of {landing}")

    assert read >= 15, f"the scan read only {read} internal links, so it is proving nothing"
    assert broken == [], f"these links land nowhere: {broken}"


def test_the_index_of_the_contract_names_every_section_and_only_those():
    """An index that went stale is worse than none: it promises a section that is gone and hides the one written after it."""
    body = pathlib.Path("CLAUDE.md").read_text()

    # The index is a section like any other and it is the one thing it never lists, because a map does not point at itself.
    written = [anchor_of(title) for title in re.findall(r"^## (.+?)\s*$", body, re.M) if anchor_of(title) != "o-que-está-escrito-aqui"]
    indexed = [anchor for anchor in re.findall(r"^\| \[[^\]]+\]\(#([^)]+)\) \|", body, re.M)]

    assert len(written) >= 20, f"the scan found only {len(written)} sections, so it is proving nothing"
    assert sorted(indexed) == sorted(written), f"the index and the sections disagree: {sorted(set(indexed) ^ set(written))}"
    assert indexed == written, "the index reads in an order the document does not follow"


def test_every_helper_is_named_in_the_table_that_maps_them():
    """The helpers are what every module reaches and what is read coldest, so a row missing from the map is a file nobody knows the purpose of."""
    body = pathlib.Path("CLAUDE.md").read_text()
    section = re.search(r"### `helpers/`.*?\n(.*?)\n#{2,3} ", body, re.S)

    assert section, "the contract no longer holds a table of the helpers"

    listed = set(re.findall(r"^\| `(\w+\.py)` \|", section.group(1), re.M))
    present = {path.name for path in pathlib.Path("helpers").glob("*.py") if path.name != "__init__.py"}

    assert len(present) >= 40, f"the scan found only {len(present)} helpers, so it is proving nothing"
    assert present - listed == set(), f"these helpers are in the folder and not on the map: {sorted(present - listed)}"
    assert listed - present == set(), f"the map names these and the folder does not have them: {sorted(listed - present)}"


def test_the_documented_number_of_restricted_keys_is_the_number_the_schema_declares():
    """It went stale the day a key of a join table moved to cascade, which is a change this same document explains."""
    import models.registry  # noqa: F401
    from helpers.db import Base

    restricted = [key for table in Base.metadata.sorted_tables for key in table.foreign_keys if (key.ondelete or "").upper() == "RESTRICT"]

    assert claimed(r"(\d+) (?:chaves com|keys with)") == {len(restricted)}


def test_the_roles_the_documentation_names_are_the_roles_the_enum_holds():
    """The prose called it an enum of two the whole time the editor was being written about three sections below."""
    named = re.search(r"`role` é um enum de \w+ valores: ((?:`\w+`(?:,| e )?\s*)+)", pathlib.Path("CLAUDE.md").read_text())

    assert named is not None
    assert set(re.findall(r"`(\w+)`", named.group(1))) == {role.value for role in UserRole}


def test_the_quickstart_builds_every_surface_it_then_promises():
    """It ran the build of the site and promised the panel too, and a fresh clone answered the drawn 404 at `/admin`."""
    ignored = {re.fullmatch(r"/webapps/(\w+)/dist", line).group(1) for line in pathlib.Path(".gitignore").read_text().splitlines() if re.fullmatch(r"/webapps/\w+/dist", line)}
    recipes = set(re.findall(r"^(\w+)-build:", pathlib.Path("Makefile").read_text(), re.M))
    quickstart = re.search(r"## [^\n]*How to use.*?```bash(.+?)```", pathlib.Path("README.md").read_text(), re.S)

    assert quickstart is not None
    assert ignored, "the guard reads what git ignores, so it proves nothing where it matched nothing"

    for surface in ignored & recipes:
        assert f"make {surface}-build" in quickstart.group(1), f"the quickstart never builds {surface}, and what serves it falls through to the site"


def test_every_limit_the_table_names_resolves_in_the_settings():
    """A limit renamed leaves the table naming a knob nobody can turn, and the symbol guard reads only the last segment of a dotted name."""
    from helpers.settings import settings

    written = pathlib.Path("CLAUDE.md").read_text()
    table = re.search(r"### Limites\n\n\| Limite \| Valor \| Onde \|\n(.+?)\n\n", written, re.S)

    assert table is not None, "the limits table is not where this guard reads it"

    rows = re.findall(r"^\| [^|]+ \| ([^|]+) \| ((?:`[\w./]+`(?:, )?)+) \|$", table.group(1), re.M)
    named, missing, wrong = 0, [], []

    for stated, paths in rows:
        for path in re.findall(r"`([\w.]+)`", paths):
            # A row also names a file or a constant of the code, and only a dotted name whose head is a section is a setting.
            if "." not in path or not hasattr(settings, path.split(".")[0]):
                continue

            target = settings

            try:
                for part in path.split("."):
                    target = getattr(target, part)
            except AttributeError:
                missing.append(path)
                continue

            if not isinstance(target, (int, float)) or isinstance(target, bool):
                continue

            named += 1
            stated_numbers = [int(number.replace(".", "")) for number in re.findall(r"\d[\d.]*", stated)]

            if not any(target == number or target // scale == number for number in stated_numbers for scale in (1, 60, 3600, 86400, 31536000, 1024 * 1024)):
                wrong.append(f"{path}: the table says {stated.strip()!r} and the settings hold {target}")

    assert named > 15, "the guard read too few limits to claim anything about the table"
    assert missing == [], f"the table names a setting that no longer exists: {missing}"
    assert wrong == [], f"the table disagrees with what the settings hold: {wrong}"


# What is written with a dash because it is typed into an address, where the rule of a path outranks the rule of an enum.
ADDRESSED = {"UploadPurpose": "the value is the segment of `POST /api/uploads/{purpose}`, and a segment of a path carries a dash"}


def test_every_enum_value_is_written_the_way_this_project_writes_one():
    """A value reaches a catalog, an api and a column, so one written by another rule is one that reads wrong in all three."""
    import enum
    import importlib
    import re

    astray, counted = [], 0

    for path in sorted(pathlib.Path("enums").rglob("*.py")):
        if path.name == "__init__.py":
            continue

        module = importlib.import_module(f"enums.{path.stem}")

        for name in dir(module):
            thing = getattr(module, name)

            if not isinstance(thing, type) or not issubclass(thing, enum.Enum) or thing.__module__ != module.__name__:
                continue

            shape = r"[a-z0-9]+(-[a-z0-9]+)*" if thing.__name__ in ADDRESSED else r"[a-z0-9]+(_[a-z0-9]+)*"

            for member in thing:
                counted += 1

                if isinstance(member.value, str) and not re.fullmatch(shape, member.value):
                    astray.append(f"{thing.__name__}.{member.name} = {member.value!r}")

                if not re.fullmatch(r"[A-Z][A-Z0-9_]*", member.name):
                    astray.append(f"{thing.__name__}.{member.name} is not the name of a member")

    assert counted >= 100, f"the scan read only {counted} values, so it is proving nothing"
    assert astray == [], f"these are written by another rule: {astray}"


def test_no_enum_is_excused_from_the_rule_it_no_longer_breaks():
    """An excuse that outlives the reason for it is a rule nobody is following any more."""
    import importlib
    import re

    stale = []

    for name, reason in ADDRESSED.items():
        found = next((getattr(importlib.import_module(f"enums.{path.stem}"), name, None) for path in pathlib.Path("enums").rglob("*.py") if hasattr(importlib.import_module(f"enums.{path.stem}"), name)), None)

        assert found is not None, f"{name} is excused and no longer exists"

        if all(re.fullmatch(r"[a-z0-9]+(_[a-z0-9]+)*", member.value) for member in found if isinstance(member.value, str)):
            stale.append(name)

    assert stale == [], f"these are excused and follow the rule anyway: {stale}"


# The scrim a photograph opens over, and the white that sits on it: it is dark in either palette, so here the colour is the role.
OVER_A_SCRIM = ("bg-black/80", "bg-black/95", "text-white", "text-white/80", "bg-white/10", "bg-white/20")


def test_no_surface_names_a_colour_where_it_should_name_a_role():
    """One place says what dark means, and a raw slate written into a screen is one the palette never reaches."""
    import re

    named = re.compile(r"\b(?:bg|text|border|ring|divide|placeholder|from|to|via|shadow|outline|accent|fill|stroke)-(?:white|black|slate|gray|zinc|neutral|stone|red|rose|emerald|green|amber|yellow|blue|indigo)(?:-\d{1,3})?(?:/\d+)?\b")
    surfaces = [("templates", {".html"}), ("webapps/admin/src", {".vue", ".js", ".css"}), ("webapps/site/src", {".js", ".css"})]
    astray, counted = [], 0

    for folder, suffixes in surfaces:
        for path in sorted(pathlib.Path(folder).rglob("*")):
            if path.suffix not in suffixes:
                continue

            counted += 1
            astray += [f"{path}: {found}" for found in sorted(set(named.findall(path.read_text()))) if found not in OVER_A_SCRIM]

    assert counted >= 100, f"the scan read only {counted} files, so it is proving nothing"
    assert astray == [], f"these name a colour where the palette names a role: {astray}"


def test_the_rule_of_every_upload_is_the_one_the_configuration_declares():
    """The table saying what a picture becomes is what somebody changing an upload reads, and it carried the numbers of before the decision that changed them."""
    rows = re.findall(r"^\| `([a-z-]+)` \| `([\w/]+)` \| \w+ \| (\d+) MB \| \*{0,2}(\w+)\*{0,2} \| ([^|]+?) \|$", pathlib.Path("CLAUDE.md").read_text(), re.M)
    wrong = []

    assert len(rows) == len(settings.uploads), f"the prose describes {len(rows)} purposes and the configuration declares {len(settings.uploads)}"

    for purpose, folder, size, naming, shape in rows:
        rule = settings.uploads[UploadPurpose(purpose)]
        said = shape.replace("×", "x")

        if rule.folder != folder or rule.max_bytes != int(size) * 1024 * 1024 or rule.naming != naming:
            wrong.append(f"{purpose} is written as {folder}, {size} MB, {naming} and declared as {rule.folder}, {rule.max_bytes // (1024 * 1024)} MB, {rule.naming}")

        if rule.image is None:
            continue

        drawn = f"{rule.image.width}x{rule.image.height}" if rule.image.height else str(rule.image.width)

        if drawn not in said or rule.image.image_format not in said or str(rule.image.quality) not in said or (rule.image.crop and "crop" not in said):
            wrong.append(f"{purpose} is written as {shape.strip()!r} and becomes {drawn}, {rule.image.image_format} {rule.image.quality}, crop={rule.image.crop}")

    assert wrong == [], f"the prose and the configuration disagree: {wrong}"

    # The readme names a few of these in prose, and it describes what the product is today rather than what it was.
    shapes = {f"{rule.image.width}×{rule.image.height}" for rule in settings.uploads.values() if rule.image and rule.image.height}
    written = re.findall(r"\b(\d{2,4}×\d{2,4})\b", pathlib.Path("README.md").read_text())

    assert len(written) >= 3, f"the readme names {len(written)} shapes, so this half is proving nothing"
    assert sorted(set(written) - shapes) == [], f"the readme names a shape no purpose declares: {sorted(set(written) - shapes)}"


def test_every_window_the_retention_declares_is_one_the_table_names():
    """The table is what somebody asking whether a table stops growing reads, and one left out of it is one they believe grows for ever."""
    written = pathlib.Path("CLAUDE.md").read_text()
    block = re.search(r"\| Tabela \| Padrão \| O que é apagado \|\n\|[^\n]+\n((?:\|[^\n]+\n)+)", written)

    assert block is not None, "the retention table is not where this guard reads it"

    stated = sorted(int(days) for days in re.findall(r"^\| `\w+` \| (\d+) dias \|", block.group(1), re.M))
    declared = sorted(value for name, value in settings.retention.model_dump().items() if name.endswith("_days"))

    assert len(stated) >= 6, f"the guard read only {len(stated)} rows, so it is proving nothing"
    assert stated == declared, f"the table states {stated} and the settings declare {declared}"


def test_every_state_the_gateway_names_is_one_the_table_reads_the_same_way():
    """The table says what a payment state becomes, and reading it wrong is reading what a subscription delivers wrong."""
    written = pathlib.Path("CLAUDE.md").read_text()
    block = re.search(r"\| O que o Stripe diz \| O que isso vira aqui \|\n\|[^\n]+\n((?:\|[^\n]+\n)+)", written)

    assert block is not None, "the table of gateway states is not where this guard reads it"

    said = dict(re.findall(r"^\| `(\w+)` \| ([^|]+?) \|$", block.group(1), re.M))
    mapped = PROVIDERS[Provider.STRIPE].STATUSES

    assert said.keys() == mapped.keys(), f"the table names {sorted(said)} and the provider reads {sorted(mapped)}"

    # The word and the state it becomes name each other, so two that become the same are written the same and two that differ are written apart.
    written_as = {}

    for name, becomes in mapped.items():
        written_as.setdefault(becomes, set()).add(said[name])

    scattered = {becomes.value: sorted(words) for becomes, words in written_as.items() if len(words) > 1}
    shared = {word for words in written_as.values() for word in words}

    assert scattered == {}, f"one state is written more than one way: {scattered}"
    assert len(shared) == len(written_as), f"the table writes {len(written_as)} different states with {len(shared)} words, so two of them read the same"
