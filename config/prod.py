from urllib.parse import quote

from config.base import NAME, CacheSettings, CaptchaSettings, DatabaseSettings, EmailSettings, RateLimitSettings, SecuritySettings, SentrySettings, SiteSettings, StorageSettings, derive
from config.dev import settings as dev

DATABASE_USER = "fastkit"
DATABASE_PASSWORD = "change-me"
DATABASE_HOST = "mysql:3306"
DATABASE_NAME = "fastkit"

AWS_REGION = "us-east-1"
AWS_BUCKET = "change-me"
AWS_ACCESS_KEY = "change-me"
AWS_SECRET_KEY = "change-me"

# The ses SMTP password is derived from the iam secret by an algorithm of its own, and is never the secret itself.
SES_SMTP_PASSWORD = "change-me"


def ses(from_name: str, from_address: str) -> EmailSettings:
    """Every brand sends through the same ses account and signs with its own name and mailbox."""
    return EmailSettings(provider="smtp", host=f"email-smtp.{AWS_REGION}.amazonaws.com", port=587, username=AWS_ACCESS_KEY, password=SES_SMTP_PASSWORD, use_tls=True, from_name=from_name, from_address=from_address)


# Production states everything it is, so what brings the application up outlives the machine that hosted it.
# fmt: off
settings = derive(
    dev,
    environment="prod",
    # A product starts as one brand, and production states what it is instead of inheriting it.
    multi_tenant=False,
    debug=False,
    database=DatabaseSettings(
        # The password is escaped, because an @ or a # in it would end the credentials early and turn the rest into the host.
        url=f"mysql+aiomysql://{DATABASE_USER}:{quote(DATABASE_PASSWORD, safe='')}@{DATABASE_HOST}/{DATABASE_NAME}",
        pool_size=10,
        max_overflow=20,
    ),
    storage=StorageSettings(
        provider="s3",
        base_url=f"https://{AWS_BUCKET}.s3.{AWS_REGION}.amazonaws.com",
        bucket=AWS_BUCKET,
        region=AWS_REGION,
        access_key=AWS_ACCESS_KEY,
        secret_key=AWS_SECRET_KEY,
    ),
    email=ses(NAME, "no-reply@change-me.com"),
    security=SecuritySettings(
        secret_key="change-me-to-a-long-random-string",
        encryption_keys=["change-me-to-another-long-random-string"],
    ),
    sentry=SentrySettings(dsn="", traces_sample_rate=0.0, send_default_pii=False),
    captcha=CaptchaSettings(provider="recaptcha_v3", site_key="change-me", secret_key="change-me"),
    # One brand means this is the domain of every absolute address the application writes, the link in an email included.
    site=SiteSettings(cookie_secure=True, domain="change-me.com"),
    cache=CacheSettings(enabled=True),
    rate_limit=RateLimitSettings(ip_limit=300, total_limit=3000),
    allowed_origins=["https://change-me.com"],
    trusted_proxies="127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
)
# fmt: on
