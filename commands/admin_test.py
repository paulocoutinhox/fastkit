from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Run the suite of the admin."

    def add_arguments(self, parser):
        parser.add_argument("--coverage", action="store_true", help="measure the coverage of the admin")

    def handle(self, coverage: bool, **options):
        self.npm("admin", "run", "test:cov" if coverage else "test")
