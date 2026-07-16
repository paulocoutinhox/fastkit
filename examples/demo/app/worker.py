import asyncio

from fastkit_core.app import create_application
from app.settings import get_settings


async def _run() -> None:
    settings = get_settings()
    settings.tasks.run_worker = True
    runtime = create_application(settings).state.fastkit
    await runtime.start()

    try:
        await asyncio.Event().wait()
    finally:
        await runtime.stop()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
