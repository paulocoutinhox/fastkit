from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Follow what the containers of the stack write."

    def handle(self, **options):
        self.compose("logs", "-f")
