import asyncio

from fastkit_cli.cli import run


async def _run_with_lifecycle(runtime, argv):
    await runtime.start()

    try:
        return await run(runtime, argv)
    finally:
        await runtime.stop()


def main(argv: list[str], runtime_factory) -> int:
    """Entry point: build the runtime, run one command and print its output."""

    runtime = runtime_factory()
    runtime.bootstrap()

    exit_code, lines = asyncio.run(_run_with_lifecycle(runtime, argv))

    for line in lines:
        print(line)

    return exit_code
