from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Build the admin into the files the server hands out."

    def handle(self, **options):
        self.npm("admin", "run", "build")
