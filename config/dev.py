from config.base import DATA_DIR
from config.captcha_settings import CaptchaSettings
from config.database_settings import DatabaseSettings
from config.email_settings import EmailSettings
from config.rate_limit_settings import RateLimitSettings
from config.security_settings import SecuritySettings
from config.settings import Settings
from config.site_settings import SiteSettings
from config.storage_settings import StorageSettings

# fmt: off
# The base of the chain: everything runs on the machine of whoever is developing, and no tenant overrides anything.
settings = Settings(
    environment="dev",
    debug=True,
    database=DatabaseSettings(
        url=f"sqlite+aiosqlite:///{DATA_DIR / 'app.db'}",
        echo=False,
    ),
    storage=StorageSettings(
        provider="filesystem",
        base_url="/media",
        root=DATA_DIR / "media",
    ),
    email=EmailSettings(
        provider="console",
        from_address="no-reply@localhost",
    ),
    security=SecuritySettings(
        secret_key="dev-insecure-secret-key-not-for-deployment",
        encryption_keys=["dev-insecure-encryption-key-not-for-deployment"],
        # A machine that runs the suite hashes thousands of passwords, and the cost that protects a stolen table protects nothing here.
        password_memory_cost=8_192,
        password_time_cost=1,
        password_parallelism=1,
    ),
    site=SiteSettings(default_tenant="acme", domain="localhost:8000", scheme="http", cookie_secure=False),
    # The drawn challenge is on here so a developer sees on the machine what a visitor sees, and the suite turns it off for itself.
    captcha=CaptchaSettings(provider="image"),
    rate_limit=RateLimitSettings(enabled=False),
    allowed_origins=["*"],
)
# fmt: on
