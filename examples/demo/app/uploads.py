from fastkit_files.errors import NOT_AN_IMAGE
from fastkit_files.images import process_variant
from fastkit_files.presets import ImageVariantSpec
from fastkit_core.errors.exceptions import FastKitError

AVATAR_SPEC = ImageVariantSpec(name="avatar", width=512, height=512, mode="cover", format="webp", quality=88)


def build_image_upload_handler(runtime, base_url: str):
    file_service = runtime.component("file_service")

    async def handler(data: bytes, filename: str, content_type: str) -> dict:
        if content_type is None or not content_type.startswith("image/"):
            raise FastKitError(NOT_AN_IMAGE, message="only image uploads are supported here")

        session = await file_service.create_upload_session(tenant_id=0)
        stored = await file_service.confirm_image_upload(session.id, data, filename, content_type)

        return {"url": f"{base_url}/{stored.object_key}", "file_id": stored.id}

    return handler


def build_avatar_upload_handler(runtime, base_url: str):
    """Avatar uploads are cropped to a centered square so they render consistently everywhere."""

    file_service = runtime.component("file_service")

    async def handler(data: bytes, filename: str, content_type: str) -> dict:
        if content_type is None or not content_type.startswith("image/"):
            raise FastKitError(NOT_AN_IMAGE, message="only image uploads are supported here")

        square = process_variant(data, AVATAR_SPEC)
        session = await file_service.create_upload_session(tenant_id=0)
        stored = await file_service.confirm_image_upload(session.id, square.data, "avatar.webp", square.mime_type)

        return {"url": f"{base_url}/{stored.object_key}", "file_id": stored.id}

    return handler


def build_file_upload_handler(runtime, base_url: str):
    file_service = runtime.component("file_service")

    async def handler(data: bytes, filename: str, content_type: str) -> dict:
        session = await file_service.create_upload_session(tenant_id=0)
        stored = await file_service.confirm_upload(session.id, data, filename, content_type)

        return {"url": f"{base_url}/{stored.object_key}", "file_id": stored.id}

    return handler
