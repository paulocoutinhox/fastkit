from helpers.commands import BaseCommand, CommandError
from helpers.db import visible_database
from helpers.schema import recreate_schema
from helpers.settings import settings


class Command(BaseCommand):
    help = "Drop every table and build them again, losing all data."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="confirm that the data of this database may be lost")

    async def handle(self, yes: bool, **options):
        # Recreating drops data, so it never happens as a side effect of typing the command.
        if not yes:
            raise CommandError(f"this would drop every table of {settings.environment} at {visible_database()}, so run it again with --yes once you are sure")

        await recreate_schema()
        self.stdout.write(f"schema recreated at {visible_database()}", self.style.SUCCESS)
