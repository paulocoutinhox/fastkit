from helpers.commands import BaseCommand
from helpers.db import AsyncSessionLocal
from jobs.subscription import run_subscription_cycle


class Command(BaseCommand):
    help = "Run one pass of the delivery jobs, the same one the scheduler runs."

    async def handle(self, **options):
        async with AsyncSessionLocal() as session:
            cycle = await run_subscription_cycle(session)

        self.stdout.write(", ".join(f"{name.replace('_', ' ')}: {count}" for name, count in cycle.items()))
