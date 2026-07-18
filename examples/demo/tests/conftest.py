import httpx
import pytest
import pytest_asyncio

from app.main import build_app
from app.seed import seed


@pytest_asyncio.fixture
async def demo(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "FASTKIT__DATABASE__URL", f"sqlite+aiosqlite:///{tmp_path}/demo.db"
    )
    monkeypatch.setenv("FASTKIT__CACHE__DIRECTORY", str(tmp_path / "cache"))
    monkeypatch.setenv("FASTKIT__STORAGE__ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("FASTKIT__MAIL__PROVIDER", "memory")

    application = build_app("test")
    runtime = application.state.fastkit

    await runtime.start()
    await seed(runtime)

    yield application, runtime

    await runtime.stop()


@pytest_asyncio.fixture
async def client(demo):
    application, _ = demo

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://demo"
    ) as http:
        yield http


@pytest.fixture
def login():
    async def _login(client, email="root@fastkit.local", password="root-password-123"):
        return await client.post(
            "/api/auth/login", json={"identifier": email, "password": password}
        )

    return _login
