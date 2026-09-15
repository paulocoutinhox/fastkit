"""The management framework: how a command is found, described, run, composed and refused."""

import io
import subprocess
import sys
from types import SimpleNamespace

import pytest

from helpers import commands
from helpers.commands import BaseCommand, CommandError, call_command, execute_from_command_line, load, names
from helpers.errors import ConflictError
from helpers.settings import settings


class Greeting(BaseCommand):
    help = "Say hello to somebody."

    def add_arguments(self, parser):
        parser.add_argument("name")
        parser.add_argument("--shout", action="store_true")

    def handle(self, name: str, shout: bool, **options):
        self.stdout.write(f"hello {name.upper() if shout else name}", self.style.SUCCESS)


class Refusal(BaseCommand):
    help = "Refuse with an exit code of its own."

    def handle(self, **options):
        raise CommandError("not today", returncode=3)


class Awaited(BaseCommand):
    help = "Write from a coroutine."

    async def handle(self, **options):
        self.stdout.write("awaited")


class Ruled(BaseCommand):
    help = "Break a rule of the application."

    def handle(self, **options):
        raise ConflictError("error.duplicated-record")


class Stopped(BaseCommand):
    help = "Get interrupted from the keyboard."

    def handle(self, **options):
        raise KeyboardInterrupt


class Composed(BaseCommand):
    help = "Run another command as part of this one."

    def handle(self, **options):
        self.call("greeting", "ana")


FAKES = {"greeting": Greeting, "refusal": Refusal, "awaited": Awaited, "composed": Composed, "ruled": Ruled, "stopped": Stopped}


@pytest.fixture
def fakes(monkeypatch):
    monkeypatch.setattr(commands, "names", lambda: sorted(FAKES))
    monkeypatch.setattr(commands, "load", lambda name: FAKES[name]())


@pytest.fixture
def programs(monkeypatch):
    ran = []

    def recorded(arguments, cwd):
        ran.append((arguments, cwd))

        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", recorded)

    return ran


def test_every_module_of_the_folder_is_a_command_typed_with_hyphens():
    found = names()

    assert len(found) > 25, "the scan found too few commands to claim anything"
    assert "create-administrator" in found
    assert all("_" not in name for name in found)
    assert all(isinstance(load(name), BaseCommand) for name in found)


def test_a_command_without_a_purpose_or_without_work_fails_where_it_is_written():
    with pytest.raises(TypeError):

        class Silent(BaseCommand):
            def handle(self, **options):
                return None

    with pytest.raises(TypeError):

        class Idle(BaseCommand):
            help = "Do nothing at all."


def test_nothing_typed_lists_every_command_with_what_it_is_for(fakes, capsys):
    assert execute_from_command_line(["manage.py"]) == 0

    listed = capsys.readouterr().out

    assert "greeting" in listed and "Say hello to somebody." in listed
    assert "refusal" in listed


@pytest.mark.parametrize("asked", ["help", "--help", "-h"])
def test_asking_for_help_lists_the_commands(fakes, capsys, asked):
    assert execute_from_command_line(["manage.py", asked]) == 0
    assert "Available commands:" in capsys.readouterr().out


def test_help_of_one_command_prints_its_options(fakes, capsys):
    assert execute_from_command_line(["manage.py", "help", "greeting"]) == 0

    described = capsys.readouterr().out

    assert "manage.py greeting" in described
    assert "--shout" in described
    assert "--verbosity" in described


def test_the_version_is_the_one_the_configuration_declares(capsys):
    assert execute_from_command_line(["manage.py", "--version"]) == 0
    assert capsys.readouterr().out.strip() == settings.version


@pytest.mark.parametrize("typed", [["manage.py", "greting"], ["manage.py", "help", "greting"]])
def test_a_command_nobody_wrote_is_refused_with_the_closest_one_named(fakes, capsys, typed):
    assert execute_from_command_line(typed) == 1
    assert "Unknown command: 'greting'. Did you mean greeting?" in capsys.readouterr().err


def test_a_command_runs_with_what_was_typed(fakes, capsys):
    assert execute_from_command_line(["manage.py", "greeting", "ana", "--shout"]) == 0
    assert capsys.readouterr().out == "hello ANA\n"


def test_a_refusal_is_said_on_stderr_with_the_exit_code_it_carries(fakes, capsys):
    assert execute_from_command_line(["manage.py", "refusal"]) == 3

    said = capsys.readouterr()

    assert said.err == "CommandError: not today\n"
    assert said.out == ""


def test_a_refusal_is_raised_when_the_traceback_is_asked_for(fakes):
    with pytest.raises(CommandError):
        execute_from_command_line(["manage.py", "refusal", "--traceback"])


def test_a_coroutine_is_awaited_by_the_framework(fakes):
    written = io.StringIO()

    call_command("awaited", stdout=written)

    assert written.getvalue() == "awaited\n"


def test_calling_from_code_takes_positional_arguments_and_options_by_name(fakes):
    written = io.StringIO()

    call_command("greeting", "ana", shout=True, stdout=written)

    assert written.getvalue() == "hello ANA\n"


def test_calling_from_code_refuses_an_option_the_command_does_not_have(fakes):
    with pytest.raises(TypeError, match="has no option whisper"):
        call_command("greeting", "ana", whisper=True)


def test_calling_from_code_lets_the_refusal_reach_the_caller(fakes):
    with pytest.raises(CommandError):
        call_command("refusal")


def test_a_command_run_inside_another_writes_where_the_first_one_writes(fakes):
    written = io.StringIO()

    call_command("composed", stdout=written, force_color=True)

    assert written.getvalue() == "\x1b[32;1mhello ana\x1b[0m\n"


def test_nothing_is_said_when_silence_was_asked_for(fakes):
    written = io.StringIO()

    call_command("greeting", "ana", verbosity=0, stdout=written)

    assert written.getvalue() == ""


def test_a_line_is_painted_only_where_it_was_asked_for_or_a_terminal_reads_it(fakes):
    plain, forced, refused = io.StringIO(), io.StringIO(), io.StringIO()

    call_command("greeting", "ana", stdout=plain)
    call_command("greeting", "ana", stdout=forced, force_color=True)
    call_command("greeting", "ana", stdout=refused, force_color=True, no_color=True)

    assert plain.getvalue() == "hello ana\n"
    assert forced.getvalue() == "\x1b[32;1mhello ana\x1b[0m\n"
    assert refused.getvalue() == "hello ana\n"


def test_a_program_runs_from_the_root_of_the_repository(programs):
    command = Greeting()
    command.execute(stdout=io.StringIO(), verbosity=1, no_color=True, force_color=False, name="ana", shout=False)

    command.run("uv", "sync")
    command.python("ruff", "check", ".")
    command.npm("admin", "run", "build")
    command.compose("logs", "-f")

    assert programs == [(["uv", "sync"], settings.base_dir), ([sys.executable, "-m", "ruff", "check", "."], settings.base_dir), (["npm", "--prefix", "webapps/admin", "run", "build"], settings.base_dir), (["docker", "compose", "logs", "-f"], settings.base_dir)]


def test_a_program_that_refuses_is_a_refusal_with_its_exit_code(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda arguments, cwd: SimpleNamespace(returncode=4))

    command = Greeting()
    command.execute(stdout=io.StringIO(), verbosity=1, no_color=True, force_color=False, name="ana", shout=False)

    with pytest.raises(CommandError) as refused:
        command.run("uv", "sync")

    assert refused.value.returncode == 4


def test_a_verbose_command_says_every_program_it_runs(programs):
    written = io.StringIO()
    command = Greeting()
    command.execute(stdout=written, verbosity=2, no_color=True, force_color=False, name="ana", shout=False)

    command.run("uv", "sync")

    assert written.getvalue() == "hello ana\n$ uv sync\n"


def test_a_rule_of_the_application_refusing_is_a_refusal_in_one_line(fakes, capsys):
    """Creating an administrator twice is a duplicate, and an operator reads the sentence and never a traceback."""
    assert execute_from_command_line(["manage.py", "ruled"]) == 1
    assert capsys.readouterr().err == "CommandError: An equivalent record already exists.\n"


def test_a_command_stopped_from_the_keyboard_ends_the_way_a_shell_expects(fakes):
    assert execute_from_command_line(["manage.py", "stopped"]) == 130


def test_a_program_a_signal_killed_answers_the_code_a_shell_reads(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda arguments, cwd: SimpleNamespace(returncode=-9))

    command = Greeting()
    command.execute(stdout=io.StringIO(), verbosity=1, no_color=True, force_color=False, name="ana", shout=False)

    with pytest.raises(CommandError) as refused:
        command.run("npm", "run", "build")

    assert refused.value.returncode == 137


def test_a_hidden_argument_never_reaches_the_screen_or_the_refusal(monkeypatch):
    """A password handed to another program is what a terminal and a pipeline log would otherwise keep."""
    monkeypatch.setattr(subprocess, "run", lambda arguments, cwd: SimpleNamespace(returncode=1))

    written = io.StringIO()
    command = Greeting()
    command.execute(stdout=written, verbosity=2, no_color=True, force_color=False, name="ana", shout=False)

    with pytest.raises(CommandError) as refused:
        command.compose("run", "app", "--password", "s3cret", hidden=("s3cret",))

    assert "s3cret" not in written.getvalue()
    assert "s3cret" not in str(refused.value)
    assert "--password ***" in str(refused.value)


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_each_stream_is_painted_by_whether_a_terminal_reads_it(fakes):
    """A refusal sent to a file carries no escape codes, whatever the output does."""
    to_terminal, to_file = Refusal(), Refusal()

    with pytest.raises(CommandError):
        to_terminal.execute(stdout=io.StringIO(), stderr=Terminal(), verbosity=1, no_color=False, force_color=False)

    with pytest.raises(CommandError):
        to_file.execute(stdout=Terminal(), stderr=io.StringIO(), verbosity=1, no_color=False, force_color=False)

    assert to_terminal.alarm.ERROR("x") == "\x1b[31;1mx\x1b[0m"
    assert to_file.alarm.ERROR("x") == "x"


def test_a_required_option_missing_from_code_is_a_refusal_and_never_the_process_leaving():
    """A terminal is answered by argparse leaving with 2, and code calling a command is answered the way every other refusal is."""
    with pytest.raises(CommandError) as refused:
        call_command("create-administrator")

    assert refused.value.returncode == 2
    assert "--password" in str(refused.value)
