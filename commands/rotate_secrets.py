from helpers.commands import BaseCommand
from helpers.db import AsyncSessionLocal
from services.rotation import rotation_service


class Command(BaseCommand):
    help = "Write every stored secret again with the key that writes now, so the one before it can be removed."

    async def handle(self, **options):
        async with AsyncSessionLocal() as session:
            rewritten = await rotation_service.rewrite(session)

        self.stdout.write(f"{rewritten} stored secrets written again with the first key", self.style.SUCCESS)
