"""The management commands, found by file name in the `commands` folder and run the way Django runs one."""

from helpers.base_command import PROGRAM, load, names, unknown
from helpers.settings import settings

# What a shell answers for a program that was interrupted from the keyboard, which is how a server a command started is stopped.
INTERRUPTED = 130


def listing() -> str:
    width = max(len(name) for name in names())
    lines = [f"Type '{PROGRAM} help <command>' for the options of one command.", "", "Available commands:"]

    return "\n".join(lines + [f"  {name.ljust(width)}  {load(name).help}" for name in names()])


def execute_from_command_line(argv: list[str]) -> int:
    """What `manage.py` does with what was typed: list the commands, describe one, or run it."""
    arguments = argv[1:]
    asked = arguments[0] if arguments else "help"

    if asked == "--version":
        print(settings.version)

        return 0

    if asked == "help" and len(arguments) > 1:
        return described(arguments[1])

    if asked in ("help", "--help", "-h"):
        print(listing())

        return 0

    if asked not in names():
        return unknown(asked)

    # A server a command started is stopped from the keyboard, which is the command ending as asked and not a traceback.
    try:
        return load(asked).run_from_argv(asked, arguments[1:])
    except KeyboardInterrupt:
        return INTERRUPTED


def described(name: str) -> int:
    if name not in names():
        return unknown(name)

    load(name).create_parser(name).print_help()

    return 0
