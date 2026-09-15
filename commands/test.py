from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Build both front ends and run the backend suite, with anything after -- handed to pytest."

    def add_arguments(self, parser):
        parser.add_argument("--coverage", action="store_true", help="measure the coverage, write the report to htmlcov and hold the floor the project declares")
        parser.add_argument("pytest", nargs="*", help="what pytest reads, written after --")

    def handle(self, coverage: bool, pytest: list[str], **options):
        # The contrast of both palettes is measured on what the builds write, so the suite builds what it reads instead of finding it left over.
        self.call("admin-build")
        self.call("site-build")

        measured = ["--cov", "--cov-report=html", "--cov-report=term"] if coverage else []
        self.python("pytest", *measured, *pytest)
