from helpers.base_command import BaseCommand


class Command(BaseCommand):
    help = "Serve the admin with the development server of Vite."

    def handle(self, **options):
        self.npm("admin", "run", "dev")
