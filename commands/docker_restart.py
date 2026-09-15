from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Restart the containers of the stack."

    def add_arguments(self, parser):
        self.stack(parser)

    def handle(self, database: bool, **options):
        self.compose_stack(database, "restart")
