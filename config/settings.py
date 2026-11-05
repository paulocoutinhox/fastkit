from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from config.authentication_settings import AuthenticationSettings
from config.base import BASE_DIR, NAME
from config.cache_settings import CacheSettings
from config.captcha_settings import CaptchaSettings
from config.database_settings import DatabaseSettings
from config.email_settings import EmailSettings
from config.rate_limit_settings import RateLimitSettings
from config.retention_settings import RetentionSettings
from config.security_settings import SecuritySettings
from config.sentry_settings import SentrySettings
from config.site_settings import SiteSettings
from config.storage_settings import StorageSettings
from config.tenant_settings import TenantSettings
from config.upload_helper import MEGABYTE, UploadHelper
from config.upload_settings import UploadSettings
from enums.social_provider import SocialProvider
from enums.upload_purpose import UploadPurpose


class Settings(BaseModel):
    environment: str
    name: str = NAME

    # Whether this instance serves more than one brand. Serving one needs no tenant row at all, and a fork of this template starts there.
    multi_tenant: bool = False
    version: str = "1.0.0"
    debug: bool = False
    base_dir: Path = BASE_DIR
    admin_dist: Path = BASE_DIR / "webapps" / "admin" / "dist"
    admin_path: str = "/admin"
    api_path: str = "/api"

    # The colour of the brand, stated once: both builds read it from here and derive every step of their own palette from it.
    brand_hue: int = 258
    brand_chroma: float = 0.19
    templates_dir: Path = BASE_DIR / "templates"
    database: DatabaseSettings
    storage: StorageSettings
    security: SecuritySettings
    authentication: AuthenticationSettings = Field(default_factory=AuthenticationSettings)
    sentry: SentrySettings = Field(default_factory=SentrySettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    captcha: CaptchaSettings = Field(default_factory=CaptchaSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    site: SiteSettings = Field(default_factory=SiteSettings)
    tenants: dict[str, TenantSettings] = Field(default_factory=dict)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    # Nothing else calls this from a browser until an installation says which does, and the machine of whoever develops is what loosens it.
    allowed_origins: list[str] = Field(default_factory=list)
    default_language: str = "en"

    # What this instance offers, where the value is the name a speaker of that language calls it by.
    languages: dict[str, str] = Field(default_factory=lambda: {"en": "English", "pt": "Português", "es": "Español"})
    password_reset_token_ttl: int = 3600

    # How long an address waits between two recovery mails, because the route is open and asking again writes to somebody else's inbox.
    password_reset_interval: int = 60

    # Whether an address proves it is the address before the account it opened answers, which is what stops somebody signing up with an inbox that is not theirs.
    confirm_sign_up: bool = True

    # How long an address waits between two confirmation mails, for the same reason the recovery has one: the route is open.
    confirm_sign_up_interval: int = 60

    # How long the readiness probe waits on the database before it answers that this copy cannot serve.
    readiness_timeout: float = 2.0

    # Which peers may speak for a client, because a forwarded header is worth exactly what the connection carrying it is: the loopback alone means nothing is in front.
    trusted_proxies: str = "127.0.0.1"

    # What a body this process parses into memory may weigh, which is every body but the multipart one an upload streams.
    request_max_bytes: int = MEGABYTE

    # The ceiling of the environment, which no purpose rule may exceed.
    upload_max_bytes: int = 512 * MEGABYTE

    # What an image may weigh once it is decoded, because a few hundred kilobytes can name a canvas of hundreds of megabytes.
    image_max_pixels: int = 40_000_000

    uploads: dict[UploadPurpose, UploadSettings] = Field(default_factory=UploadHelper.default_uploads)
    cron_enabled: bool = True

    # Empty means this instance serves every queue its jobs declare, which is the shape of a single process.
    cron_queues: list[str] = Field(default_factory=list)
    cron_concurrency: int = 4
    cron_poll_seconds: float = 1.0

    # How long a claim is good for without a heartbeat, which is what decides how fast a dead instance is noticed.
    cron_lease_seconds: float = 300.0

    @model_validator(mode="after")
    def the_language_everything_falls_back_to_is_one_this_instance_offers(self):
        if self.default_language not in self.languages:
            raise ValueError(f"the default language is {self.default_language} and this instance offers {sorted(self.languages)}, so every message would be looked up in a catalog that is not loaded")

        return self

    @model_validator(mode="after")
    def apple_callbacks_use_secure_cookies(self):
        apple = self.authentication.social.get(SocialProvider.APPLE)

        if apple is not None and apple.enabled and (self.site.scheme != "https" or not self.site.cookie_secure):
            raise ValueError("apple sign-in requires HTTPS and secure site cookies")

        return self

    def email_for(self, code: str | None) -> EmailSettings:
        """A tenant sends through what it declares, and through the environment default when it declares nothing."""
        override = self.tenants.get(code or "")

        return override.email if override and override.email else self.email
