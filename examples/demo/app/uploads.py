import hashlib
from pathlib import Path

from fastkit_assets.errors import NOT_AN_IMAGE
from fastkit_assets.images import process_variant
from fastkit_assets.presets import ImageVariantSpec
from fastkit_core.errors.exceptions import FastKitError

AVATAR_SPEC = ImageVariantSpec(name="avatar", width=512, height=512, mode="cover", format="webp", quality=88)


def build_image_upload_handler(runtime, base_url: str):
    asset_service = runtime.component("asset_service")

    async def handler(data: bytes, filename: str, content_type: str) -> dict:
        if content_type is None or not content_type.startswith("image/"):
            raise FastKitError(NOT_AN_IMAGE, message="only image uploads are supported here")

        session = await asset_service.create_upload_session(tenant_id=0)
        asset = await asset_service.confirm_image_upload(session.id, data, filename, content_type)

        return {"url": f"{base_url}/{asset.object_key}", "asset_id": asset.id}

    return handler


def build_avatar_upload_handler(runtime, base_url: str):
    """Avatar uploads are cropped to a centered square so they render consistently everywhere."""

    asset_service = runtime.component("asset_service")

    async def handler(data: bytes, filename: str, content_type: str) -> dict:
        if content_type is None or not content_type.startswith("image/"):
            raise FastKitError(NOT_AN_IMAGE, message="only image uploads are supported here")

        square = process_variant(data, AVATAR_SPEC)
        session = await asset_service.create_upload_session(tenant_id=0)
        asset = await asset_service.confirm_image_upload(session.id, square.data, "avatar.webp", square.mime_type)

        return {"url": f"{base_url}/{asset.object_key}", "asset_id": asset.id}

    return handler


def build_file_upload_handler(runtime, base_url: str):
    storage = runtime.component("storage")

    async def handler(data: bytes, filename: str, content_type: str) -> dict:
        digest = hashlib.sha256(data).hexdigest()
        suffix = Path(filename or "file").suffix
        key = f"files/{digest[:2]}/{digest}{suffix}"
        await storage.put(key, data, content_type=content_type or "application/octet-stream")

        return {"url": f"{base_url}/{key}", "asset_id": None}

    return handler
