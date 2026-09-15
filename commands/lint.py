from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Check the backend against the lint and the formatter without writing anything."

    def handle(self, **options):
        self.python("ruff", "check", ".")
        self.python("ruff", "format", "--check", ".")
