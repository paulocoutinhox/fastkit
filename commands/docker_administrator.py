from helpers.commands import BaseCommand
from services.seed import ADMIN


class Command(BaseCommand):
    help = "Create an administrator from inside the image, against the database APP_ENV names."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=ADMIN["username"])
        parser.add_argument("--email", default=ADMIN["email"])
        parser.add_argument("--password", required=True)

    def handle(self, username: str, email: str, password: str, **options):
        # The entrypoint serves and ignores what it is handed, so a command run in the image replaces it instead of being passed to it.
        self.compose("run", "--rm", "--entrypoint", "python", "app", "manage.py", "create-administrator", "--username", username, "--email", email, "--password", password, hidden=(password,))
