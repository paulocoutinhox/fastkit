from helpers.base_command import BaseCommand


class Command(BaseCommand):
    help = "Build the image the application ships in."

    def handle(self, **options):
        self.compose("build")
