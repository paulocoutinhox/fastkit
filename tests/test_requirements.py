"""What the code imports is what the install has to bring, or a fresh machine answers ModuleNotFoundError."""

import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# What runs in the image, which is installed without the development group.
RUNNING = ("commands", "config", "enums", "helpers", "models", "schemas", "services", "routes", "jobs")

OURS = {*RUNNING, "tests", "app", "manage", "extras"}

# A module is imported by one name and installed by another, so the two are written down together.
PACKAGES = {"PIL": "pillow", "jwt": "pyjwt", "argon2": "argon2-cffi", "sentry_sdk": "sentry-sdk", "pytest_asyncio": "pytest-asyncio", "starlette": "fastapi"}


def imported(files: list[Path]) -> set[str]:
    found = set()

    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                found |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])

    return {name for name in found if name not in OURS and name not in sys.stdlib_module_names}


def declared(with_groups: bool) -> set[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    requirements = project["project"]["dependencies"] + ([name for group in project["dependency-groups"].values() for name in group] if with_groups else [])

    return {re.split(r"[\[><=;@ ]", line.strip(), maxsplit=1)[0].lower() for line in requirements}


def missing(files: list[Path], packages: set[str]) -> list[str]:
    return sorted(name for name in imported(files) if PACKAGES.get(name, name).lower() not in packages)


def test_every_module_the_running_code_imports_is_a_package_the_image_installs():
    """Jinja2 came in through an extra of fastapi, and it worked until somebody installed from this file alone: the image installs without the development group, so that group never answers for what runs."""
    running = [path for folder in RUNNING for path in (ROOT / folder).rglob("*.py")] + [ROOT / "app.py", ROOT / "manage.py"]

    assert missing(running, declared(with_groups=False)) == []


def test_every_module_a_test_imports_is_a_package_the_development_install_brings():
    assert missing(list((ROOT / "tests").rglob("*.py")), declared(with_groups=True)) == []
