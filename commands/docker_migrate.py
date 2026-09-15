from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Apply the schema from inside the image, against the database APP_ENV names."

    def handle(self, **options):
        # The entrypoint serves and ignores what it is handed, so a command run in the image replaces it instead of being passed to it.
        self.compose("run", "--rm", "--entrypoint", "python", "app", "manage.py", "migrate")
