import pytest
import pytest_asyncio

from fastkit_db.base import Base
from fastkit_db.engine import Database

from fastkit_webhooks import models  # noqa: F401
from fastkit_webhooks.provider import HmacWebhookProvider
from fastkit_webhooks.service import WebhookRegistry, WebhookService


@pytest_asyncio.fixture
async def database(tmp_path):
    db = Database(url=f"sqlite+aiosqlite:///{tmp_path}/webhooks.db")
    await db.create_all(Base.metadata)

    yield db

    await db.dispose()


@pytest.fixture
def registry():
    reg = WebhookRegistry()
    reg.register(HmacWebhookProvider(name="stripe", secret="whsec_test", signature_header="X-Signature"))

    return reg


@pytest.fixture
def service(database, registry):
    return WebhookService(database.session_factory, registry)


@pytest.fixture
def signer():
    from fastkit_webhooks.signature import compute_signature

    def sign(body: bytes):
        return compute_signature("whsec_test", body)

    return sign
