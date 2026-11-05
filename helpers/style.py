"""What a line is, painted only where somebody reads a terminal."""

SUCCESS, WARNING, ERROR, NOTICE = "32;1", "33;1", "31;1", "36;1"


class Style:
    def __init__(self, painted: bool):
        self.painted = painted
        self.SUCCESS = self.painter(SUCCESS)
        self.WARNING = self.painter(WARNING)
        self.ERROR = self.painter(ERROR)
        self.NOTICE = self.painter(NOTICE)

    def painter(self, code: str):
        return lambda text: f"\x1b[{code}m{text}\x1b[0m" if self.painted else text
