from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Build the image the application ships in."

    def handle(self, **options):
        self.compose("build")
