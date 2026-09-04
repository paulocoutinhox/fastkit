"""A console script pins the interpreter it was installed with, so every python tool of a recipe goes through the resolver of the project."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Each of these ships a console script, and calling one by name is what freezes the interpreter the venv was built with.
TOOLS = ("uvicorn", "ruff", "pytest", "pip", "python", "python3")


def recipes() -> list[str]:
    return [line.lstrip("\t").strip() for line in (ROOT / "Makefile").read_text().splitlines() if line.startswith("\t")]


def test_every_python_tool_a_recipe_calls_goes_through_uv():
    """The venv was built with one python and the machine moved to another, and `make start` answered ModuleNotFoundError."""
    called = re.compile(rf"^(?:@)?({'|'.join(TOOLS)})\b")
    wrong = [line for line in recipes() if called.match(line)]

    assert wrong == [], f"these pin the interpreter of whoever created the venv: {wrong}"


def test_no_recipe_runs_node_from_the_repository_root():
    """The node projects live under webapps, and an npm call with no prefix writes node_modules at the root."""
    wrong = [line for line in recipes() if line.startswith("npm ") and "--prefix webapps/" not in line]

    assert wrong == [], f"these would install node at the root of the repository: {wrong}"


def test_the_pipeline_runs_what_the_makefile_declares():
    """A command written twice is a command that drifts, and the one in the pipeline is the copy nobody runs locally."""
    recipes = set(re.findall(r"^([\w-]+):", (ROOT / "Makefile").read_text(), re.M))
    workflow = (ROOT / ".github/workflows/test.yml").read_text()
    ran = [line.strip() for found in re.finditer(r"^\s*run: (\|\n(?:\s+.+\n)+|.+)$", workflow, re.M) for line in found.group(1).replace("|", "").splitlines() if line.strip()]

    # Installing what the recipes need is the one thing the pipeline says for itself, because a recipe cannot install its own runtime.
    installing = {"uv sync --frozen", "npm ci --prefix webapps/admin", "npm ci --prefix webapps/site"}
    written = [command for command in ran if command not in installing and not command.startswith("make ")]

    assert len(ran) >= 8, f"the guard read only {len(ran)} steps, so it is proving nothing"
    assert written == [], f"the pipeline writes its own commands instead of calling the recipes: {written}"
    assert all(command.split()[1] in recipes for command in ran if command.startswith("make ")), "the pipeline calls a recipe the makefile does not declare"


def test_a_recipe_that_runs_a_command_in_the_image_is_not_swallowed_by_the_entrypoint():
    """The entrypoint serves and ignores what it is handed, so a command passed as its argument starts a second web server and never runs."""
    running = [line for line in recipes() if "docker compose run" in line]
    naming = [line for line in running if re.search(r"\bapp\b\s+\S", line)]

    assert len(naming) >= 2, f"the guard read only {len(naming)} of them, so it is proving nothing"

    swallowed = [line for line in naming if "--entrypoint" not in line]

    assert swallowed == [], f"these hand a command to the entrypoint instead of running it: {swallowed}"
