from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Move every python dependency to its newest allowed version, then install them."

    def handle(self, **options):
        self.run("uv", "lock", "--upgrade")
        self.run("uv", "sync")
