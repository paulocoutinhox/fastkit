from helpers.base_command import BaseCommand


class Command(BaseCommand):
    help = "Move every dependency to its newest allowed version, then install them."

    def handle(self, **options):
        self.run("uv", "lock", "--upgrade")
        self.run("uv", "sync")
        self.npm("admin", "update")
        self.npm("site", "update")
