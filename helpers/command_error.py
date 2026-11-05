"""The one way a command refuses, answered on stderr and with the exit code it carries."""


class CommandError(Exception):
    def __init__(self, message: str, returncode: int = 1):
        super().__init__(message)
        self.returncode = returncode
