from helpers.base_command import BaseCommand


class Command(BaseCommand):
    help = "Install what the admin is built with."

    def handle(self, **options):
        self.npm("admin", "install")
