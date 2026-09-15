"""The management commands, found by file name in the `commands` folder and run the way Django runs one."""

import argparse
import difflib
import inspect
import pkgutil
import subprocess
import sys
from importlib import import_module
from typing import TextIO

import commands
from helpers.db import run_scoped
from helpers.errors import AppError
from helpers.settings import settings

PROGRAM = "manage.py"

# What every command answers besides its own options, so no command declares them.
BASE_OPTIONS = {"verbosity", "traceback", "no_color", "force_color", "stdout", "stderr"}

SUCCESS, WARNING, ERROR, NOTICE = "32;1", "33;1", "31;1", "36;1"

# What a shell answers for a program that was interrupted from the keyboard, which is how a server a command started is stopped.
INTERRUPTED = 130


class CommandError(Exception):
    """The one way a command refuses, answered on stderr and with the exit code it carries."""

    def __init__(self, message: str, returncode: int = 1):
        super().__init__(message)
        self.returncode = returncode


class Style:
    """What a line is, painted only where somebody reads a terminal."""

    def __init__(self, painted: bool):
        self.painted = painted
        self.SUCCESS = self.painter(SUCCESS)
        self.WARNING = self.painter(WARNING)
        self.ERROR = self.painter(ERROR)
        self.NOTICE = self.painter(NOTICE)

    def painter(self, code: str):
        return lambda text: f"\x1b[{code}m{text}\x1b[0m" if self.painted else text


class OutputWrapper:
    """A stream a command writes lines to, which says nothing at all when the command was asked to be silent."""

    def __init__(self, stream: TextIO, silent: bool = False):
        self.stream = stream
        self.silent = silent

    def write(self, message: str = "", style=None) -> None:
        if self.silent:
            return

        self.stream.write(f"{style(message) if style else message}\n")
        self.stream.flush()


class BaseCommand:
    """A command says what it is for in `help`, declares its options in `add_arguments`, and does its work in `handle`, which may be a coroutine."""

    help = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # A command without a purpose or without work fails where it is written, and not at a terminal somebody is waiting on.
        if not cls.help or not callable(getattr(cls, "handle", None)):
            raise TypeError(f"{cls.__module__} has to say what it is for in help and do it in handle")

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """A command with options of its own declares them here."""

    def create_parser(self, name: str) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog=f"{PROGRAM} {name}", description=self.help)
        parser.add_argument("-v", "--verbosity", type=int, choices=(0, 1, 2, 3), default=1, help="0 says nothing of its own, 1 says what was done, and 2 or 3 also say every program it runs")
        parser.add_argument("--traceback", action="store_true", help="raise a refusal instead of only saying it")
        parser.add_argument("--no-color", action="store_true", help="never paint the output")
        parser.add_argument("--force-color", action="store_true", help="paint the output even where nobody reads a terminal")
        self.add_arguments(parser)

        return parser

    def execute(self, stdout: TextIO | None = None, stderr: TextIO | None = None, **options) -> None:
        """Runs the command with its options already parsed, which is what the command line and `call_command` both hand over."""
        written = stdout or sys.stdout

        self.options = {name: options[name] for name in ("verbosity", "no_color", "force_color")} | {"stdout": written, "stderr": stderr}
        self.verbosity = options["verbosity"]
        refused = stderr or sys.stderr

        self.stdout = OutputWrapper(written, silent=self.verbosity == 0)
        self.stderr = OutputWrapper(refused)
        self.style = Style(not options["no_color"] and (options["force_color"] or written.isatty()))

        # Each stream is painted by whether a terminal reads it, so a refusal sent to a file never carries escape codes.
        self.alarm = Style(not options["no_color"] and (options["force_color"] or refused.isatty()))

        # A rule of the application refusing is the command refusing, said in one line and not as a traceback.
        try:
            answer = self.handle(**options)

            # The loop of an async command is opened and closed here, so no command opens one of its own around the shared session.
            if inspect.isawaitable(answer):
                run_scoped(answer)
        except AppError as error:
            raise CommandError(error.message) from error

    def run_from_argv(self, name: str, arguments: list[str]) -> int:
        options = vars(self.create_parser(name).parse_args(arguments))

        try:
            self.execute(**options)
        except CommandError as error:
            if options["traceback"]:
                raise

            self.stderr.write(f"CommandError: {error}", self.alarm.ERROR)

            return error.returncode

        return 0

    def call(self, name: str, *arguments) -> None:
        """Another command, run as part of this one with the same verbosity, colors and streams."""
        call_command(name, *arguments, **self.options)

    def run(self, *arguments: str, hidden: tuple[str, ...] = ()) -> None:
        """Another program, run from the root of the repository, whose refusal is this command's refusal with the same exit code, and whose hidden arguments never reach a screen or a log."""
        shown = " ".join("***" if argument in hidden else argument for argument in arguments)

        if self.verbosity >= 2:
            self.stdout.write(f"$ {shown}", self.style.NOTICE)

        done = subprocess.run(list(arguments), cwd=settings.base_dir)

        if done.returncode == 0:
            return

        # A program a signal killed answers the negative of the signal, and a shell reads that as 128 plus the signal.
        code = done.returncode if done.returncode > 0 else 128 - done.returncode

        raise CommandError(f"{shown} exited with {code}", code)

    def python(self, *arguments: str) -> None:
        """A python tool runs as a module of this very interpreter, because a console script pins the one the environment was built with."""
        self.run(sys.executable, "-m", *arguments)

    def npm(self, project: str, *arguments: str) -> None:
        """Both node projects live under webapps, and npm run anywhere else writes node_modules at the root of the repository."""
        self.run("npm", "--prefix", f"webapps/{project}", *arguments)

    def compose(self, *arguments: str, hidden: tuple[str, ...] = ()) -> None:
        self.run("docker", "compose", *arguments, hidden=hidden)

    def stack(self, parser) -> None:
        """The database of the compose file lives behind a profile, so a stack that runs its own names it on every call that starts or stops it."""
        parser.add_argument("--database", action="store_true", help="include the MySQL of the compose file, for an environment whose database runs on this machine")

    def compose_stack(self, database: bool, *arguments: str) -> None:
        self.compose(*(("--profile", "database") if database else ()), *arguments)


def names() -> list[str]:
    """Every module of the commands folder is a command, typed with a hyphen where the python module has an underscore."""
    return sorted(module.name.replace("_", "-") for module in pkgutil.iter_modules(commands.__path__))


def load(name: str) -> BaseCommand:
    return import_module(f"commands.{name.replace('-', '_')}").Command()


def call_command(name: str, *arguments, **options) -> None:
    """Runs a command from code, with positional arguments as they would be typed and options named by their destination."""
    command = load(name)
    parser = command.create_parser(name)
    unknown = sorted(set(options) - {action.dest for action in parser._actions} - BASE_OPTIONS)

    if unknown:
        raise TypeError(f"{name} has no option {', '.join(unknown)}")

    typed = [str(argument) for argument in arguments]
    named = dict(options)

    # A required option named from code is written into the line as it would have been typed, because that line is what argparse checks it against.
    for action in parser._actions:
        if action.required and action.dest in named:
            typed += [action.option_strings[0], str(named.pop(action.dest))]

    # Called from code, a refused line is a refusal the caller handles, and never the process leaving as it does in a terminal.
    parser.exit_on_error = False

    try:
        parsed = parser.parse_args(typed)
    except argparse.ArgumentError as refused:
        raise CommandError(str(refused), returncode=2) from refused

    command.execute(**(vars(parsed) | named))


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


def unknown(name: str) -> int:
    close = difflib.get_close_matches(name, names())
    suggestion = f" Did you mean {' or '.join(close)}?" if close else ""

    print(f"Unknown command: '{name}'.{suggestion} Type '{PROGRAM} help' for usage.", file=sys.stderr)

    return 1
