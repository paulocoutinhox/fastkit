from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Serve the admin with the development server of Vite."

    def handle(self, **options):
        self.npm("admin", "run", "dev")
