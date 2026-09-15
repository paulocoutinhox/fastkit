from helpers.commands import BaseCommand, CommandError
from services.schema_diff import OUTPUT, compare, compared


class Command(BaseCommand):
    help = "Compare the schema of the configured database with the one the code declares, and write the statements that are missing."

    def add_arguments(self, parser):
        parser.add_argument("--current", default=None, help="a dump taken on the server, for when this machine cannot reach it")

    def handle(self, current: str | None, **options):
        subject = compared(current)

        if subject is None:
            raise CommandError("this configuration does not point at a server, so there is nothing to compare")

        self.stdout.write(f"comparing {subject} against the schema of the code")

        try:
            found = compare(current)
        except RuntimeError as refused:
            raise CommandError(str(refused)) from None

        for line in found["report"]:
            self.stdout.write(line)

        self.stdout.write(f"\nwritten in {OUTPUT}/: schema-from-scratch.sql, schema-in-place.sql, proposal.sql", self.style.SUCCESS)
        self.stdout.write(f"the proposal covers {found['proposed']} creation(s), and what the database has over is listed as a decision and never generated")
