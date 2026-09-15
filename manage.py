import argparse
from urllib.parse import urlsplit, urlunsplit

from enums.user import UserRole, UserStatus
from helpers.db import AsyncSessionLocal, run_scoped
from helpers.schema import create_schema, recreate_schema
from helpers.settings import settings
from jobs.subscription import run_subscription_cycle
from services.rotation import rotation_service
from services.schema_diff import run_command as run_schema_diff
from services.seed import ADMIN
from services.seed import run_command as run_seed_command
from services.sweep import sweep_service
from services.user import user_service


def visible_database() -> str:
    """The url names which database is about to be touched, without putting its password on a screen."""
    parts = urlsplit(settings.database.url)

    if not parts.password:
        return settings.database.url

    host = parts.netloc.rsplit("@", 1)[1]

    return urlunsplit(parts._replace(netloc=f"{parts.username}:***@{host}"))


async def create_administrator(username: str, email: str, password: str) -> int:
    """An administrator is global, because that is the scope the admin sign in resolves in."""
    async with AsyncSessionLocal() as session:
        user = await user_service.create(session, {"username": username, "email": email, "password": password, "role": UserRole.ADMINISTRATOR, "status": UserStatus.ACTIVE, "tenant_id": None})

        return user.id


async def deliver_once() -> dict:
    async with AsyncSessionLocal() as session:
        return await run_subscription_cycle(session)


async def rewrite_secrets() -> int:
    async with AsyncSessionLocal() as session:
        return await rotation_service.rewrite(session)


async def find_orphans() -> list[str]:
    async with AsyncSessionLocal() as session:
        return await sweep_service.find_orphans(session)


async def discard_orphans() -> list[str]:
    async with AsyncSessionLocal() as session:
        return await sweep_service.discard_orphans(session)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{settings.name} management commands")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("migrate", help="create every table the application needs, leaving the ones it already has untouched")

    recreate = commands.add_parser("recreate-schema", help="drop every table and build them again, losing all data")
    recreate.add_argument("--yes", action="store_true", help="confirm that the data of this database may be lost")

    administrator = commands.add_parser("create-administrator", help="create an account able to sign in to the admin")
    administrator.add_argument("--username", default=ADMIN["username"])
    administrator.add_argument("--email", default=ADMIN["email"])
    administrator.add_argument("--password", default=ADMIN["password"])

    seeding = commands.add_parser("seed", help="rebuild the database and fill it with everything a local machine needs")
    seeding.add_argument("--yes", action="store_true", help="confirm that the data of this database may be lost")

    comparison = commands.add_parser("schema-diff", help="compare the schema of the configured database with the one the code declares")
    comparison.add_argument("--current", default=None, help="a dump taken on the server, for when this machine cannot reach it")

    commands.add_parser("run-delivery", help="run one pass of the delivery jobs")

    commands.add_parser("rotate-secrets", help="write every stored secret again with the key that writes now, so the one before it can be removed")

    sweep = commands.add_parser("sweep-files", help="find the stored files no row of any table mentions")
    sweep.add_argument("--yes", action="store_true", help="confirm that the listed files may be deleted")

    return parser


def run_recreate_schema(confirmed: bool) -> int:
    """Recreating drops data, so it never happens as a side effect of typing the command."""
    if not confirmed:
        print(f"this would drop every table of {settings.environment} at {visible_database()}")
        print("run it again with --yes once you are sure")

        return 1

    run_scoped(recreate_schema())
    print(f"schema recreated at {visible_database()}")

    return 0


def run_sweep_files(confirmed: bool) -> int:
    """Deleting a file is not reversible, so the sweep lists what it found before anything is touched."""
    if not confirmed:
        orphans = run_scoped(find_orphans())

        for key in orphans:
            print(key)

        print(f"{len(orphans)} orphan files older than {settings.storage.orphan_grace_hours}h at {settings.storage.provider}")

        if orphans:
            print("run it again with --yes to delete them")

        return 0

    discarded = run_scoped(discard_orphans())
    print(f"deleted {len(discarded)} orphan files")

    return 0


def run_migrate() -> int:
    run_scoped(create_schema())
    print(f"schema is up to date at {visible_database()}")

    return 0


def run_create_administrator(username: str, email: str, password: str) -> int:
    run_scoped(create_schema())
    user_id = run_scoped(create_administrator(username, email, password))
    print(f"administrator created with id {user_id}")

    return 0


def run_rotate_secrets() -> int:
    print(f"{run_scoped(rewrite_secrets())} stored secrets written again with the first key")

    return 0


def run_delivery() -> int:
    cycle = run_scoped(deliver_once())
    print(", ".join(f"{name.replace('_', ' ')}: {count}" for name, count in cycle.items()))

    return 0


def commands(arguments) -> dict:
    """Every command is named here, and a guard reads this against the parser so one declared and forgotten fails in the suite."""
    return {
        "migrate": run_migrate,
        "recreate-schema": lambda: run_recreate_schema(arguments.yes),
        "create-administrator": lambda: run_create_administrator(arguments.username, arguments.email, arguments.password),
        "seed": lambda: run_seed_command(arguments.yes, visible_database()),
        "schema-diff": lambda: run_schema_diff(arguments.current),
        "run-delivery": run_delivery,
        "rotate-secrets": run_rotate_secrets,
        "sweep-files": lambda: run_sweep_files(arguments.yes),
    }


def main() -> int:
    arguments = build_parser().parse_args()

    return commands(arguments)[arguments.command]()


if __name__ == "__main__":
    raise SystemExit(main())
