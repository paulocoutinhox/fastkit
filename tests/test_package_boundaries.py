import re
from pathlib import Path

import pytest

PACKAGES_DIR = Path(__file__).resolve().parents[1] / "packages"

# each package's src must not contain imports of these forbidden modules
FORBIDDEN_IMPORTS = {
    "fastkit-core": ["sqlalchemy", "redis", "boto3", "aioboto3", "PIL", "jinja2", "fastkit_db", "fastkit_admin"],
    "fastkit-config": ["sqlalchemy", "fastkit_db", "fastkit_admin"],
    "fastkit-db": ["fastkit_admin", "fastkit_accounts", "redis", "boto3"],
    "fastkit-storage": ["fastkit_admin", "fastkit_db"],
}

IMPORT_PATTERN = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.MULTILINE)


def _imported_modules(package: str) -> set[str]:
    src = PACKAGES_DIR / package / "src"
    modules: set[str] = set()

    for path in src.rglob("*.py"):
        for match in IMPORT_PATTERN.finditer(path.read_text(encoding="utf-8")):
            modules.add(match.group(1))

    return modules


@pytest.mark.parametrize("package,forbidden", FORBIDDEN_IMPORTS.items())
def test_no_forbidden_imports(package, forbidden):
    modules = _imported_modules(package)

    for banned in forbidden:
        offenders = [module for module in modules if module == banned or module.startswith(f"{banned}.")]

        assert not offenders, f"{package} must not import {banned}: found {offenders}"


def test_init_files_are_empty():
    for init_file in PACKAGES_DIR.rglob("src/**/__init__.py"):
        content = init_file.read_text(encoding="utf-8").strip()

        assert content == "", f"{init_file} must be empty per project convention"


def test_every_package_has_docs_and_pyproject():
    for package_dir in sorted(PACKAGES_DIR.iterdir()):
        if not package_dir.is_dir():
            continue

        assert (package_dir / "pyproject.toml").exists(), f"{package_dir.name} is missing pyproject.toml"
        assert (package_dir / "DOCS.md").exists(), f"{package_dir.name} is missing DOCS.md"


ERROR_CODE_MODULES = ["fastkit_core.errors.codes", "fastkit_auth.errors", "fastkit_assets.errors", "fastkit_mail.errors", "fastkit_storage.errors"]


def test_every_error_code_has_a_catalog_entry():
    import importlib

    from fastkit_core.errors.codes import ErrorCode
    from fastkit_i18n.catalogs import BASE_CATALOGS

    english = BASE_CATALOGS["en"]
    missing = []

    for module_name in ERROR_CODE_MODULES:
        module = importlib.import_module(module_name)

        for value in vars(module).values():
            if isinstance(value, ErrorCode) and value.translation_key not in english:
                missing.append(value.translation_key)

    assert not missing, f"error codes missing a catalog entry: {sorted(missing)}"
