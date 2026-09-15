from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Format the backend and both front ends."

    def handle(self, **options):
        self.python("ruff", "check", "--fix", ".")
        self.python("ruff", "format", ".")
        self.call("admin-format")
        self.call("site-format")
