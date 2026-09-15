from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Build the site assets and run their suite, which reads what the build wrote."

    def add_arguments(self, parser):
        parser.add_argument("--coverage", action="store_true", help="measure the coverage of the site assets")

    def handle(self, coverage: bool, **options):
        self.call("site-build")
        self.npm("site", "run", "test:cov" if coverage else "test")
