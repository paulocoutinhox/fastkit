from fastapi import APIRouter, Depends
from pydantic import BaseModel

from fastkit_core.api.envelope import build_message, success_envelope


class TranslationEntry(BaseModel):
    language: str
    title: str | None = None
    summary: str | None = None
    body: str | None = None


class TranslationsPayload(BaseModel):
    translations: list[TranslationEntry]


def build_content_router(
    runtime, security, publish_permission: str = "content.publish", tenant_id: int = 0
) -> APIRouter:
    """pyaa-style static content managed per language and read by key + language.

    ``security`` supplies ``get_current_user`` and ``authorize``; the consumer decides the
    permission that guards editing and the tenant reads resolve against.
    """

    router = APIRouter()
    content_service = runtime.component("content_service")
    language_service = runtime.component("language_service")

    async def _require(user):
        await security.authorize(user, publish_permission)

    @router.get("/content/languages")
    async def languages(user=Depends(security.get_current_user)):
        await _require(user)

        active = await language_service.list_active()

        return success_envelope(
            data=[{"code": language.code, "name": language.name} for language in active]
        )

    @router.get("/content/{content_id}/translations")
    async def get_translations(
        content_id: int, user=Depends(security.get_current_user)
    ):
        await _require(user)

        return success_envelope(
            data={
                "translations": await content_service.translations_by_content_id(
                    content_id
                )
            }
        )

    @router.put("/content/{content_id}/translations")
    async def set_translations(
        content_id: int,
        payload: TranslationsPayload,
        user=Depends(security.get_current_user),
    ):
        await _require(user)

        codes = {
            language.code: language.id
            for language in await language_service.list_active()
        }

        for entry in payload.translations:
            language_id = codes.get(entry.language)

            if language_id is None:
                continue

            await content_service.set_translation(
                content_id,
                language_id,
                title=entry.title,
                summary=entry.summary,
                body=entry.body,
            )

        return success_envelope(
            message=build_message(
                "content.translations_updated", "Content translations updated."
            )
        )

    @router.get("/content-by-key/{key}")
    async def read_by_key(
        key: str, language: str | None = None, user=Depends(security.get_current_user)
    ):
        await _require(user)

        body = await content_service.get(key, locale=language, tenant_id=tenant_id)

        return success_envelope(data={"key": key, "language": language, "body": body})

    return router
