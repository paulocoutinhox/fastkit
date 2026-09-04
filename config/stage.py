from config.base import CacheSettings, CaptchaSettings, DatabaseSettings, EmailSettings, RateLimitSettings, SecuritySettings, derive
from config.dev import settings as dev

# The application against a real database server, holding no secret at all, so `docker compose up` works whole.
# fmt: off
settings = derive(
    dev,
    environment="stage",
    multi_tenant=True,
    database=DatabaseSettings(
        url="mysql+aiomysql://app:app@mysql:3306/app",
        pool_size=10,
        max_overflow=20,
    ),
    email=EmailSettings(
        provider="console",
        from_address="no-reply@stage.localhost",
    ),
    security=SecuritySettings(
        secret_key="stage-insecure-secret-key-not-for-deployment",
        encryption_keys=["stage-insecure-encryption-key-not-for-deployment"],
    ),
    captcha=CaptchaSettings(provider="image"),
    cache=CacheSettings(enabled=True),
    rate_limit=RateLimitSettings(ip_limit=600, total_limit=6000),
    allowed_origins=["*"],
    trusted_proxies="127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
)
# fmt: on
