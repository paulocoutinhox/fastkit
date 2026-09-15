from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Format the admin with the prettier configuration of the project."

    def handle(self, **options):
        self.npm("admin", "run", "format")
