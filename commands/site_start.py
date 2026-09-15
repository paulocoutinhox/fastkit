from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Serve the site assets with the development server of Vite."

    def handle(self, **options):
        self.npm("site", "run", "dev")
