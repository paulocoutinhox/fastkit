from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Build the site assets into the files the server hands out."

    def handle(self, **options):
        self.npm("site", "run", "build")
