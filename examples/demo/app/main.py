import asyncio
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from fastkit_core.app import create_application
from fastkit_admin.mounting import mount_admin_static
from app.seed import seed
from app.settings import get_settings

BASE_DIR = Path(__file__).resolve().parents[1]


def build_app(environment: str | None = None):
    settings = get_settings(environment)
    application = create_application(settings)

    media_root = BASE_DIR / settings.storage.root.lstrip("./")
    media_root.mkdir(parents=True, exist_ok=True)
    application.mount(settings.storage.base_url, StaticFiles(directory=media_root), name="media")
    application.mount("/demo-static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="demo-static")
    mount_admin_static(application)

    return application


app = build_app()


async def _run_seed():
    settings = get_settings()
    application = create_application(settings)
    runtime = application.state.fastkit
    await runtime.start()

    try:
        result = await seed(runtime)
        print(f"seeded: {result}")
    finally:
        await runtime.stop()


def run_seed() -> None:
    asyncio.run(_run_seed())


if __name__ == "__main__":
    run_seed()
