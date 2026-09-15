from helpers.commands import BaseCommand


class Command(BaseCommand):
    help = "Serve the application and reload it whenever the code changes."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=8000)

    def handle(self, host: str, port: int, **options):
        self.python("uvicorn", "app:app", "--host", host, "--port", str(port), "--log-level", "debug", "--reload")
