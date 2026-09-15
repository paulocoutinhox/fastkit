from helpers.commands import BaseCommand
from helpers.db import AsyncSessionLocal
from helpers.settings import settings
from services.sweep import sweep_service


class Command(BaseCommand):
    help = "Find the stored files no row mentions, and delete them once confirmed."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="confirm that the listed files may be deleted")

    async def handle(self, yes: bool, **options):
        # Deleting a file is not reversible, so the sweep lists what it found before anything is touched.
        async with AsyncSessionLocal() as session:
            if yes:
                discarded = await sweep_service.discard_orphans(session)
                self.stdout.write(f"deleted {len(discarded)} orphan files", self.style.SUCCESS)

                return

            found = 0

            async for key in sweep_service.find_orphans(session):
                self.stdout.write(key)
                found += 1

        self.stdout.write(f"{found} orphan files older than {settings.storage.orphan_grace_hours}h at {settings.storage.provider}")

        if found:
            self.stdout.write("run it again with --yes to delete them", self.style.WARNING)
