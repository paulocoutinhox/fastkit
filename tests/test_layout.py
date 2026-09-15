"""A file is read from the top down, so it is written that way: imports, constants, variables, and then what they are for."""

import ast
import pathlib
import re

import pytest

# The rule is about the code that runs, and a test legitimately reaches for a factory inside the one case that needs it.
FOLDERS = ("config", "enums", "helpers", "jobs", "models", "routes", "schemas", "services")

ORDER = {"import": 0, "constant": 1, "variable": 2}

NAMED = {0: "import", 1: "constant", 2: "variable"}


def sources() -> list[pathlib.Path]:
    return [path for folder in FOLDERS for path in sorted(pathlib.Path(folder).rglob("*.py"))] + [pathlib.Path("app.py"), pathlib.Path("manage.py")]


def kind(node) -> str | None:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return "import"

    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]

        # Two constants written on one line are two constants, and reading only the first target read a tuple as a variable.
        names = [found.id for target in targets for found in ast.walk(target) if isinstance(found, ast.Name)]

        return "constant" if names and all(name.isupper() for name in names) else "variable"

    return None


def test_the_scan_reads_every_folder_the_code_runs_from():
    """A folder that stopped being read would leave this whole file passing without looking at anything."""
    unread = sorted({path.parts[0] for path in pathlib.Path(".").glob("*/*.py") if path.parts[0] not in FOLDERS and not path.parts[0].startswith((".", "_")) and path.parts[0] != "tests"})

    assert unread == [], f"these hold code that runs and nothing here reads them: {unread}"
    assert len(sources()) > 140


@pytest.mark.parametrize("path", sources(), ids=str)
def test_a_file_opens_with_its_imports_then_its_constants_then_its_variables(path):
    """What a name means is read before it is used, and a file that mixes the three is one nobody can skim."""
    highest = 0

    for node in ast.parse(path.read_text()).body:
        # What comes after the first definition is what derives from it: a singleton, a router, a registry of the classes above.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return

        step = kind(node)

        if step is None:
            continue

        assert ORDER[step] >= highest, f"{path}:{node.lineno} is a {step} written after a {NAMED[highest]}"

        highest = max(highest, ORDER[step])


@pytest.mark.parametrize("path", sources(), ids=str)
def test_an_import_is_written_where_every_other_import_is(path):
    """An import inside a function is a cycle somebody worked around instead of breaking, and it hides what a module really needs."""
    offenders = []

    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for inner in ast.walk(node):
            if isinstance(inner, (ast.Import, ast.ImportFrom)):
                offenders.append(f"{path}:{inner.lineno} inside {node.name}")

    assert offenders == [], f"these imports are hidden inside a function: {offenders}"


@pytest.mark.parametrize("path", sources(), ids=str)
def test_nothing_is_imported_after_the_file_has_started_doing_things(path):
    """An import written below code runs after it, and what it needs may already have been asked for."""
    started = None

    for node in ast.parse(path.read_text()).body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert started is None, f"{path}:{node.lineno} imports after the file already did something"
        elif not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)):
            started = started or type(node).__name__


def test_every_helper_opens_by_saying_what_it_is():
    """A folder every module reaches into is read cold more than any other, and two conventions in it is one too many."""
    import ast
    import pathlib

    silent = []
    checked = 0

    for path in sorted(pathlib.Path("helpers").glob("*.py")):
        if path.name == "__init__.py":
            continue

        checked += 1
        opening = ast.get_docstring(ast.parse(path.read_text()), clean=False)

        if not opening:
            silent.append(path.name)

    assert checked >= 30, f"the scan read only {checked} helpers, so it is proving nothing"
    assert silent == [], f"these open without saying what they are: {silent}"


# A shape somebody else declares: the parameter is there because the caller passes it, and reading it is not this side's business.
SHAPED_ELSEWHERE = {
    "enforce_foreign_keys": "a sqlalchemy event listener is called with the signature the event declares",
    "process_bind_param": "a TypeDecorator is called with the dialect whether or not the column cares",
    "process_result_value": "the same, on the way back",
    "finished": "a queuefy listener is handed the result of the run it is told about",
    "save": "one storage answers a content type the bucket needs and the disk does not",
}

# The hooks a subclass overrides and the contracts a provider implements, written to a shape and not to what one body happens to read.
CONTRACTS = {"prepare", "validate", "after_save", "before_delete", "build_label", "label_ordering", "read", "state_from_query", "authenticate", "verify", "challenge", "lookup", "store", "delete", "url", "settle", "confinement"}


def test_no_function_takes_something_its_body_never_reads():
    """An argument nobody reads is one every caller still passes, and it outlives whatever used to need it."""
    unread, counted = [], 0

    for path in sources():
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name in CONTRACTS or node.decorator_list:
                continue

            counted += 1
            body = ast.unparse(ast.Module(body=node.body, type_ignores=[]))
            read = {found.id for found in ast.walk(node) if isinstance(found, ast.Name)}

            for argument in list(node.args.args) + list(node.args.kwonlyargs):
                if argument.arg in ("self", "cls") or argument.arg.startswith("_") or node.name in SHAPED_ELSEWHERE:
                    continue

                if argument.arg not in read and argument.arg not in body:
                    unread.append(f"{path}:{node.lineno}: {node.name} never reads {argument.arg}")

    assert counted >= 400, f"the scan read only {counted} functions, so it is proving nothing"
    assert unread == [], f"these take something they never read: {unread}"


def test_no_shape_is_excused_that_no_longer_needs_it():
    """An excuse that outlives the function it was written for is a rule nobody is following any more."""
    written = "\n".join(path.read_text() for path in sources())
    stale = sorted(name for name in SHAPED_ELSEWHERE if f"def {name}(" not in written)

    assert stale == [], f"these are excused and no longer exist: {stale}"


def test_no_task_is_left_running_with_nobody_reading_what_it_raised():
    """A task nobody awaits keeps its exception to itself, so the work it was doing simply stops and the process answers as if nothing happened."""
    unwatched, counted = [], 0

    for path in sources():
        for holder in ast.walk(ast.parse(path.read_text())):
            if not isinstance(holder, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            body = ast.unparse(ast.Module(body=holder.body, type_ignores=[]))

            for node in ast.walk(holder):
                if not isinstance(node, ast.Call) or ast.unparse(node.func) not in ("asyncio.create_task", "asyncio.ensure_future"):
                    continue

                counted += 1
                held = [target.id for parent in ast.walk(holder) if isinstance(parent, ast.Assign) and parent.value is node for target in parent.targets if isinstance(target, ast.Name)]

                if not held:
                    unwatched.append(f"{path}:{node.lineno} starts a task and keeps no hold on it")
                elif not any(f"{name}.add_done_callback" in body for name in held):
                    unwatched.append(f"{path}:{node.lineno} nobody reads what {held[0]} raises")

    assert counted >= 1, f"the scan read only {counted} tasks, so it is proving nothing"
    assert unwatched == [], f"these are started and nobody reads what they raise: {unwatched}"


# What opens a connection to a machine that is not this one, which is what a deadline has to bound.
REACHING_OUT = ("httpx", "aiosmtplib")


def test_every_call_that_leaves_this_machine_carries_a_deadline():
    """A server that accepts the connection and then says nothing holds a worker for as long as the library felt like, which is a number nobody here chose."""
    deadlineless, read = [], 0

    for path in sources():
        body = path.read_text()

        if not any(re.search(rf"^import {name}|^from {name}", body, re.M) for name in REACHING_OUT):
            continue

        for found in re.finditer(r"\b(?:httpx\.(?:Async)?Client|aiosmtplib\.send)\(", body):
            read += 1
            opened = body[found.end() - 1 :]
            depth, cut = 0, 0

            for position, letter in enumerate(opened):
                depth += letter == "("
                depth -= letter == ")"

                if depth == 0:
                    cut = position
                    break

            if "timeout" not in opened[:cut]:
                deadlineless.append(f"{path}:{body[: found.start()].count(chr(10)) + 1} reaches another machine with no deadline")

    assert read >= 8, f"the scan read only {read} calls that leave this machine, so it is proving nothing"
    assert deadlineless == [], f"these wait forever on somebody else: {deadlineless}"


def test_every_deadline_the_documentation_states_is_the_one_the_module_declares():
    """A number written in prose goes stale in silence, and this table is the only place a reader learns how long anybody is waited for."""
    stated = re.findall(r"^\| .*?\| (\d+)s[,.]?", pathlib.Path("CLAUDE.md").read_text(), re.M)
    declared = sorted(float(found) for path in sources() for found in re.findall(r"^(?:SUBSCRIBER_)?TIMEOUT = ([\d.]+)$", path.read_text(), re.M))

    assert len(declared) >= 6, f"the scan found only {len(declared)} declared deadlines, so it is proving nothing"
    assert sorted(float(number) for number in stated) == declared, f"the documentation states {sorted(stated)} and the modules declare {declared}"
