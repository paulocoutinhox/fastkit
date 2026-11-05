from config.cache_settings import CacheSettings
from config.captcha_settings import CaptchaSettings
from config.database_settings import DatabaseSettings
from config.dev import settings as dev
from config.email_settings import EmailSettings
from config.environment_helper import EnvironmentHelper
from config.rate_limit_settings import RateLimitSettings
from config.security_settings import SecuritySettings

# The application against a real database server and holding no secret, brought up with its own database by `manage.py docker-start --database`, where the brands are created in the panel.
# fmt: off
settings = EnvironmentHelper.derive(
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
