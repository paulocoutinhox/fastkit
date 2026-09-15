from helpers.commands import BaseCommand, CommandError
from helpers.db import AsyncSessionLocal, visible_database
from helpers.schema import recreate_schema
from helpers.settings import settings
from services.seed import discard_media, seed_service


class Command(BaseCommand):
    help = "Rebuild the database and fill it with everything a local machine needs."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="confirm that the data of this database may be lost")

    async def handle(self, yes: bool, **options):
        # The seed owns the whole database, so it is refused where the data is not disposable.
        if settings.environment != "dev":
            raise CommandError(f"the seed only runs in dev and this is {settings.environment}")

        if not yes:
            raise CommandError(f"this would rebuild {visible_database()} and fill it from scratch, so run it again with --yes once you are sure")

        await recreate_schema()
        await discard_media()

        async with AsyncSessionLocal() as session:
            filled = await seed_service.run(session)

        for name, value in filled.items():
            self.stdout.write(f"{name}: {value}")
