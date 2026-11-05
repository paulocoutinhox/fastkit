from helpers.base_command import BaseCommand


class Command(BaseCommand):
    help = "Format the admin with the prettier configuration of the project."

    def handle(self, **options):
        self.npm("admin", "run", "format")
