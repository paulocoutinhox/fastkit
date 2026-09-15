from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Stop the stack and remove its containers."

    def add_arguments(self, parser):
        self.stack(parser)

    def handle(self, database: bool, **options):
        self.compose_stack(database, "down")
