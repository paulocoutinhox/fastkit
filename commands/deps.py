from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Install the python dependencies the lock file pins."

    def handle(self, **options):
        self.run("uv", "sync")
