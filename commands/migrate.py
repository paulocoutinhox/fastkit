from helpers.commands import BaseCommand
from helpers.db import visible_database
from helpers.schema import create_schema


class Command(BaseCommand):
    help = "Create every table the application needs, leaving the ones it already has untouched."

    async def handle(self, **options):
        await create_schema()
        self.stdout.write(f"schema is up to date at {visible_database()}", self.style.SUCCESS)
