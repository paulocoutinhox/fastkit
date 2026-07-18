import ast
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


def _is_barrel(tree) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            continue

        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "__all__":
            continue

        return False

    return True


def test_init_files_are_empty_or_barrels():
    for init_file in PACKAGES_DIR.rglob("src/**/__init__.py"):
        content = init_file.read_text(encoding="utf-8").strip()

        if content == "":
            continue

        tree = ast.parse(content)

        assert _is_barrel(tree), f"{init_file} must be empty or a pure re-export barrel (only 'from ... import ...' and __all__)"


def test_every_package_has_docs_and_pyproject():
    for package_dir in sorted(PACKAGES_DIR.iterdir()):
        if not package_dir.is_dir():
            continue

        assert (package_dir / "pyproject.toml").exists(), f"{package_dir.name} is missing pyproject.toml"
        assert (package_dir / "DOCS.md").exists(), f"{package_dir.name} is missing DOCS.md"


ERROR_CODE_MODULES = ["fastkit_core.errors.codes", "fastkit_auth.errors", "fastkit_files.errors", "fastkit_mail.errors", "fastkit_storage.errors"]


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


def test_every_pydantic_validation_key_has_a_catalog_entry():
    from fastkit_core.errors.handlers import GENERIC_VALIDATION_CODE, PYDANTIC_CODE_MAP
    from fastkit_i18n.catalogs import BASE_CATALOGS

    keys = set(PYDANTIC_CODE_MAP.values()) | {GENERIC_VALIDATION_CODE}

    for locale, catalog in BASE_CATALOGS.items():
        missing = sorted(key for key in keys if key not in catalog)

        assert not missing, f"validation keys missing from {locale} catalog: {missing}"


FIELD_ERROR_CODE_PATTERN = re.compile(r"""FieldError\(\s*(?:field\s*=\s*)?["'][^"']*["']\s*,\s*(?:code\s*=\s*)?["']([^"']+)["']""")
CODE_LOCAL_PATTERN = re.compile(r"^[a-z0-9]+\.[a-z0-9-]+$")


def test_every_framework_field_error_code_is_translated():
    """Every inline FieldError code in framework source must be a kebab-case-local key present in
    both catalogs, so a field error never surfaces a raw code (e.g. `validation.password.incorrect`)."""

    from fastkit_i18n.catalogs import BASE_CATALOGS

    codes: set[str] = set()

    for path in PACKAGES_DIR.rglob("src/**/*.py"):
        for match in FIELD_ERROR_CODE_PATTERN.finditer(path.read_text(encoding="utf-8")):
            codes.add(match.group(1))

    assert codes, "no FieldError codes discovered — the scanner regressed"

    malformed = sorted(code for code in codes if not CODE_LOCAL_PATTERN.match(code))
    assert not malformed, f"field error codes must be context.local kebab-case, not dotted: {malformed}"

    for locale, catalog in BASE_CATALOGS.items():
        missing = sorted(code for code in codes if code not in catalog)
        assert not missing, f"field error codes missing from {locale} catalog: {missing}"


def test_pydantic_code_map_covers_every_error_type():
    import typing

    from pydantic_core.core_schema import ErrorType

    from fastkit_core.errors.handlers import PYDANTIC_CODE_MAP

    error_types = set(typing.get_args(ErrorType))
    mapped = set(PYDANTIC_CODE_MAP)

    assert not error_types - mapped, f"pydantic error types missing from the map: {sorted(error_types - mapped)}"
    assert not mapped - error_types, f"map has entries that are not pydantic error types: {sorted(mapped - error_types)}"
