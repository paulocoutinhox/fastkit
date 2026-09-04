"""What the code imports is what the install has to bring, or a fresh machine answers ModuleNotFoundError."""

import ast
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ("config", "enums", "helpers", "models", "schemas", "services", "routes", "jobs", "tests")

OURS = {*SOURCE, "main", "manage", "extras"}

# A module is imported by one name and installed by another, so the two are written down together.
PACKAGES = {"PIL": "pillow", "jwt": "pyjwt", "argon2": "argon2-cffi", "sentry_sdk": "sentry-sdk", "pytest_asyncio": "pytest-asyncio", "starlette": "fastapi"}


def imported() -> set[str]:
    files = [path for folder in SOURCE for path in (ROOT / folder).rglob("*.py")] + [ROOT / "main.py", ROOT / "manage.py"]
    found = set()

    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                found |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])

    return {name for name in found if name not in OURS and name not in sys.stdlib_module_names}


def declared() -> set[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    requirements = project["project"]["dependencies"] + [name for group in project["dependency-groups"].values() for name in group]

    return {re.split(r"[\[><=;@ ]", line.strip(), maxsplit=1)[0].lower() for line in requirements}


def test_every_module_the_code_imports_is_a_package_the_install_brings():
    """Jinja2 came in through an extra of fastapi, and it worked until somebody installed from this file alone."""
    packages = declared()
    missing = sorted(name for name in imported() if PACKAGES.get(name, name).lower() not in packages)

    assert missing == [], f"imported and never declared: {missing}"
