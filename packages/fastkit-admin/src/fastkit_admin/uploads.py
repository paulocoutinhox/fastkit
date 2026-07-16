from fastapi import APIRouter, Depends, File, UploadFile

from fastkit_core.api.envelope import build_message, success_envelope
from fastkit_core.errors.codes import RESOURCE_NOT_FOUND
from fastkit_core.errors.exceptions import NotFoundError
from fastkit_admin.api import AdminDeps
from fastkit_admin.helpers import DEFAULT_MAX_UPLOAD_BYTES, read_upload


def build_upload_router(deps: AdminDeps, handlers: dict, max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES) -> APIRouter:
    """Upload endpoint keyed by kind (``image``, ``file``, …).

    Each ``handler(data, filename, content_type)`` returns ``{"url": …, "asset_id": …}``
    so the router stays storage agnostic.
    """

    router = APIRouter()

    @router.post("/uploads/{kind}")
    async def create_upload(kind: str, file: UploadFile = File(...), user=Depends(deps.get_current_user)):
        handler = handlers.get(kind)

        if handler is None:
            raise NotFoundError(RESOURCE_NOT_FOUND, message=f"upload kind '{kind}' is not supported")

        data = await read_upload(file, max_bytes)
        result = await handler(data, file.filename, file.content_type)
        asset_id = str(result["asset_id"]) if result.get("asset_id") is not None else None

        return success_envelope(data={"url": result["url"], "asset_id": asset_id}, message=build_message("uploads.created", "File uploaded."))

    return router
