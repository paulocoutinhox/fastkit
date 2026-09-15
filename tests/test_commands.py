"""Every program a command runs goes through the framework, and the pipeline runs the commands instead of writing them again."""

import ast
import re
from pathlib import Path

from helpers.commands import names

ROOT = Path(__file__).resolve().parent.parent

# Each of these ships a console script, and calling one by name is what freezes the interpreter the environment was built with.
TOOLS = {"uvicorn", "ruff", "pytest", "pip", "python", "python3"}

# The programs with a runner of their own, because each carries a rule the plain one would forget.
RUNNERS = {"npm": "npm", "docker": "compose"}


def modules() -> list[Path]:
    return sorted((ROOT / "commands").glob("*.py"))


def calls(path: Path, method: str) -> list[list]:
    """The literal arguments of every `self.<method>(...)` call of a command, read from its syntax and never from its text."""
    found = []

    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == method and isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
            found.append([argument.value if isinstance(argument, ast.Constant) else None for argument in node.args])

    return found


def test_no_command_starts_a_program_behind_the_back_of_the_framework():
    """The framework runs a program from the root and turns its refusal into this command's, and a module that reaches past it does neither."""
    reaching = [path.name for path in modules() if re.search(r"\b(subprocess|os\.system|os\.popen)\b", path.read_text())]

    assert len(modules()) > 25, "the guard read too few commands to claim anything"
    assert reaching == [], f"these start a program themselves: {reaching}"


def test_every_program_a_command_runs_goes_through_the_runner_that_carries_its_rule():
    """A python tool by name pins the interpreter of whoever built the environment, and npm without its prefix writes node_modules at the root."""
    wrong, read = [], 0

    for path in modules():
        for arguments in calls(path, "run"):
            read += 1
            program = arguments[0] if arguments else None

            if program in TOOLS or program in RUNNERS:
                wrong.append(f"{path.name}: {program}")

    assert read >= 2, f"the guard read {read} programs, so it is proving nothing"
    assert wrong == [], f"these run a program the plain way instead of through python(), npm() or compose(): {wrong}"


def test_a_command_run_inside_the_image_is_not_swallowed_by_the_entrypoint():
    """The entrypoint serves and ignores what it is handed, so a command passed as its argument starts a second web server and never runs."""
    running = [arguments for path in modules() for arguments in calls(path, "compose") if arguments[:1] == ["run"]]
    swallowed = [arguments for arguments in running if "--entrypoint" not in arguments]

    assert len(running) >= 2, f"the guard read only {len(running)} of them, so it is proving nothing"
    assert swallowed == [], f"these hand a command to the entrypoint instead of running it: {swallowed}"


def test_the_pipeline_runs_the_commands_and_writes_none_of_its_own():
    """A command written twice is a command that drifts, and the one in the pipeline is the copy nobody runs locally."""
    workflow = (ROOT / ".github/workflows/test.yml").read_text()
    ran = [line.strip() for found in re.finditer(r"^\s*run: (\|\n(?:\s+.+\n)+|.+)$", workflow, re.M) for line in found.group(1).replace("|", "").splitlines() if line.strip()]

    # Installing what the commands need is the one thing the pipeline says for itself, because a command cannot install its own runtime.
    installing = {"uv sync --frozen", "npm ci --prefix webapps/admin", "npm ci --prefix webapps/site"}
    commanded = [command.split()[3] for command in ran if command.startswith("uv run manage.py ")]
    written = [command for command in ran if command not in installing and not command.startswith("uv run manage.py ")]

    assert len(ran) >= 8, f"the guard read only {len(ran)} steps, so it is proving nothing"
    assert written == [], f"the pipeline writes its own commands instead of calling them: {written}"
    assert sorted(set(commanded) - set(names())) == [], "the pipeline calls a command the project does not have"


def test_everything_that_serves_the_application_names_the_same_module():
    """The module is called by what it answers, and a server started by one name where another serves by a second is a rename left half done."""
    serving = {path: path.read_text() for path in (ROOT / "commands/start.py", ROOT / "entrypoint.sh")}
    elsewhere = [path.name for path, body in serving.items() if not re.search(r"\bapp:app\b", body)]

    assert elsewhere == [], f"these serve the application by another name: {elsewhere}"
    assert not (ROOT / "main.py").exists()
