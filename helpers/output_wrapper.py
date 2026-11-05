"""A stream a command writes lines to, which says nothing at all when the command was asked to be silent."""

from typing import TextIO


class OutputWrapper:
    def __init__(self, stream: TextIO, silent: bool = False):
        self.stream = stream
        self.silent = silent

    def write(self, message: str = "", style=None) -> None:
        if self.silent:
            return

        self.stream.write(f"{style(message) if style else message}\n")
        self.stream.flush()
