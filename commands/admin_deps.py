from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Install what the admin is built with."

    def handle(self, **options):
        self.npm("admin", "install")
