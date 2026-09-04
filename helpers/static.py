"""What is served straight off the disk: the media, the built assets and the panel."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from helpers.settings import settings


def setup_media(app: FastAPI) -> None:
    if settings.storage.provider != "filesystem":
        return

    settings.storage.root.mkdir(parents=True, exist_ok=True)
    app.mount(settings.storage.base_url, StaticFiles(directory=settings.storage.root), name="media")


def setup_assets(app: FastAPI) -> None:
    """What the site build wrote, served under a path of its own so no page route ever competes with a file."""
    if not settings.site.assets.is_dir():
        return

    app.mount(settings.site.assets_url, StaticFiles(directory=settings.site.assets), name="assets")


def inside(root: Path, path: str) -> Path | None:
    """A request names a file of the build and nothing else: `..` resolves before the check, so no path climbs out of the directory it is served from."""
    candidate = (root / path).resolve()

    if not candidate.is_file() or not candidate.is_relative_to(root.resolve()):
        return None

    return candidate


def setup_admin(app: FastAPI) -> None:
    """The admin is a single page app under its own path, so every unknown route below it answers the entry point."""
    index = settings.admin_dist / "index.html"

    if not index.is_file():
        return

    @app.get(settings.admin_path, include_in_schema=False)
    @app.get(f"{settings.admin_path}/{{path:path}}", include_in_schema=False)
    async def admin_entry(path: str = "") -> Response:
        candidate = inside(settings.admin_dist, path) if path else None

        if candidate is not None:
            return FileResponse(candidate)

        return FileResponse(index)


def setup(app: FastAPI):
    """The API and the admin own their own paths, the build owns one of its own, and the site renders the rest."""
    setup_media(app)
    setup_assets(app)
    setup_admin(app)
