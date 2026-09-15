from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Start the stack in the background, with the configuration APP_ENV names."

    def add_arguments(self, parser):
        self.stack(parser)

    def handle(self, database: bool, **options):
        self.compose_stack(database, "up", "-d")
