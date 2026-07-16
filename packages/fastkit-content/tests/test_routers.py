from types import SimpleNamespace

from fastkit_content.routers import TranslationEntry, TranslationsPayload, build_content_router


class _LanguageService:
    async def list_active(self):
        return [SimpleNamespace(id=1, code="en", name="English"), SimpleNamespace(id=2, code="pt", name="Portuguese")]


class _ContentService:
    def __init__(self):
        self.saved = []
        self.read = None

    async def translations_by_content_id(self, content_id):
        return [{"language": "en", "title": "Hi"}]

    async def set_translation(self, content_id, language_id, title, summary, body):
        self.saved.append((content_id, language_id, title, summary, body))

    async def get(self, key, locale, tenant_id):
        self.read = (key, locale, tenant_id)

        return "<p>body</p>"


class _Security:
    def __init__(self):
        self.checks = []

    async def get_current_user(self):
        return SimpleNamespace(id=1)

    async def authorize(self, user, permission):
        self.checks.append(permission)


def _runtime(content, languages):
    services = {"content_service": content, "language_service": languages}

    return SimpleNamespace(component=lambda name: services[name])


def _endpoints(runtime, security, **kwargs):
    router = build_content_router(runtime, security, **kwargs)

    return {(route.path, tuple(sorted(route.methods))): route.endpoint for route in router.routes}


async def test_languages_lists_active():
    security = _Security()
    endpoints = _endpoints(_runtime(_ContentService(), _LanguageService()), security)

    result = await endpoints[("/content/languages", ("GET",))](user=SimpleNamespace())

    assert result["data"] == [{"code": "en", "name": "English"}, {"code": "pt", "name": "Portuguese"}]
    assert security.checks == ["content.publish"]


async def test_get_translations_returns_service_payload():
    endpoints = _endpoints(_runtime(_ContentService(), _LanguageService()), _Security())

    result = await endpoints[("/content/{content_id}/translations", ("GET",))](content_id=3, user=SimpleNamespace())

    assert result["data"] == {"translations": [{"language": "en", "title": "Hi"}]}


async def test_set_translations_skips_unknown_languages():
    content = _ContentService()
    endpoints = _endpoints(_runtime(content, _LanguageService()), _Security(), publish_permission="cms.write")
    payload = TranslationsPayload(translations=[
        TranslationEntry(language="pt", title="Olá", body="<p>oi</p>"),
        TranslationEntry(language="zz", title="ignored"),
    ])

    await endpoints[("/content/{content_id}/translations", ("PUT",))](content_id=7, payload=payload, user=SimpleNamespace())

    assert content.saved == [(7, 2, "Olá", None, "<p>oi</p>")]


async def test_read_by_key_resolves_against_the_tenant():
    content = _ContentService()
    endpoints = _endpoints(_runtime(content, _LanguageService()), _Security(), tenant_id=4)

    result = await endpoints[("/content-by-key/{key}", ("GET",))](key="welcome", language="pt", user=SimpleNamespace())

    assert result["data"] == {"key": "welcome", "language": "pt", "body": "<p>body</p>"}
    assert content.read == ("welcome", "pt", 4)
