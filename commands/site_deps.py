from helpers.base_command import BaseCommand


class Command(BaseCommand):
    help = "Install what the site assets are built with."

    def handle(self, **options):
        self.npm("site", "install")
