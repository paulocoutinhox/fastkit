from helpers.base_command import BaseCommand


class Command(BaseCommand):
    help = "Format the site assets with the prettier configuration of the project."

    def handle(self, **options):
        self.npm("site", "run", "format")
