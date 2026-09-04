from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from enums.consent import ConsentCategory
from enums.storage import StorageProvider
from enums.upload import Naming, UploadPurpose

BASE_DIR = Path(__file__).resolve().parent.parent

# What the product is called, written once and read by the api, the admin, the mailer and the command line.
NAME = "FastKit"

# Everything a running instance writes on disk lives under one directory, so nothing of the developer machine lands in the repository root.
DATA_DIR = BASE_DIR / "data"


class DatabaseSettings(BaseModel):
    url: str
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 3600


class RetentionSettings(BaseModel):
    """How long an operational table keeps what nothing will ever act on again, where zero keeps it forever."""

    system_log_days: int = 180
    app_event_days: int = 90
    webhook_event_days: int = 90
    outbound_email_days: int = 90
    client_request_days: int = 30
    banner_impression_days: int = 90
    cron_run_days: int = 30

    # The first pass of a table nobody ever trimmed would lock it for minutes, so it walks out in bites.
    batch: int = 1000


class CacheSettings(BaseModel):
    """What an assembled answer is kept in, which a machine somebody develops on leaves off so a page shows what was just edited."""

    enabled: bool = False

    # Nothing evicts anything here, so each of these is also how long an edit in the panel takes to reach a reader.
    home_ttl: int = 60
    banners_ttl: int = 60
    products_ttl: int = 120
    search_ttl: int = 30
    plans_ttl: int = 300
    content_ttl: int = 300
    gallery_ttl: int = 300


class StorageSettings(BaseModel):
    provider: StorageProvider
    base_url: str
    root: Path = DATA_DIR / "media"
    bucket: str = ""
    region: str = ""
    endpoint_url: str = ""
    access_key: str = ""
    secret_key: str = ""
    sweep_orphans: bool = True
    orphan_grace_hours: int = 24


MEGABYTE = 1024 * 1024

# SVG is left out on purpose: it carries markup, and an editor renders whatever it carries.
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
DOCUMENT_EXTENSIONS = frozenset({".pdf", ".epub", ".zip", ".mp3", ".mp4"})


class ImageSettings(BaseModel):
    """What an uploaded image becomes before it is stored, so what reaches the storage never depends on what somebody sent."""

    width: int | None = None
    height: int | None = None
    crop: bool = False
    image_format: Literal["jpeg", "png", "webp"] = "jpeg"
    quality: int = 85

    # What is stored: the image this rule describes, or the bytes exactly as they arrived.
    # Either way the content is decoded first, so an extension can never lie about what the bytes are.
    store: Literal["processed", "original"] = "processed"


class UploadSettings(BaseModel):
    """One purpose: where it is stored, what it accepts, how big it may be, what it is called and what it becomes."""

    folder: str
    extensions: frozenset[str]
    max_bytes: int

    # A purpose with no image rule stores exactly the bytes that arrived.
    image: ImageSettings | None = None

    naming: Naming = Naming.UUID


def image_upload(folder: str, max_bytes: int, image: ImageSettings) -> UploadSettings:
    return UploadSettings(folder=folder, extensions=IMAGE_EXTENSIONS, max_bytes=max_bytes, image=image)


def default_uploads() -> dict[UploadPurpose, UploadSettings]:
    return {
        UploadPurpose.IMAGE: image_upload("images/content", 10 * MEGABYTE, ImageSettings(width=1600, image_format="webp", quality=82)),
        UploadPurpose.AVATAR: image_upload("images/user/avatar", 5 * MEGABYTE, ImageSettings(width=256, height=256, crop=True, image_format="webp", quality=85)),
        UploadPurpose.BANNER: image_upload("images/banner", 10 * MEGABYTE, ImageSettings(width=1920, height=1080, crop=True, image_format="webp", quality=82)),
        UploadPurpose.GALLERY_PHOTO: image_upload("images/gallery", 10 * MEGABYTE, ImageSettings(width=1600, height=900, crop=True, image_format="webp", quality=82)),
        UploadPurpose.PRODUCT_IMAGE: image_upload("images/product", 10 * MEGABYTE, ImageSettings(width=1280, height=720, crop=True, image_format="webp", quality=85)),
        UploadPurpose.PLAN_IMAGE: image_upload("images/plan", 10 * MEGABYTE, ImageSettings(width=1280, height=720, crop=True, image_format="webp", quality=85)),
        UploadPurpose.PRODUCT_FILE: UploadSettings(folder="files/product", extensions=DOCUMENT_EXTENSIONS, max_bytes=512 * MEGABYTE, naming=Naming.ORIGINAL),
    }


class EmailSettings(BaseModel):
    # A message is sent, and printing it instead is the machine of whoever develops saying so: an environment that forgot to configure mail writes every recovery token into its log.
    provider: Literal["smtp", "console"] = "smtp"
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    from_name: str = NAME
    from_address: str = "no-reply@localhost"


class CaptchaSettings(BaseModel):
    """Which challenge a public form carries, where `disabled` is declared by an environment and never assumed by a failure."""

    # A challenge this server draws needs no key from anybody, so an environment that says nothing still guards its public forms.
    provider: Literal["image", "recaptcha_v3", "disabled"] = "image"
    site_key: str = ""
    secret_key: str = ""

    # What reCAPTCHA has to answer for a call to count as human.
    score_threshold: float = 0.5

    # How long a drawn challenge stays valid, which is what stops one image from answering for a whole afternoon.
    ttl: int = 600
    length: int = 5


class ConsentSettings(BaseModel):
    """What a visitor is asked to allow, and how long the answer is kept before it is asked again."""

    cookie: str = "fastkit_consent"
    max_age: int = 60 * 60 * 24 * 180

    # The answer is kept against the version it was given about, so changing what is asked asks everybody again.
    version: int = 1

    # What this instance asks about, in the order the page draws it. `necessary` is never in here: nobody is asked about it.
    optional: list[ConsentCategory] = Field(default_factory=lambda: [ConsentCategory.PREFERENCES, ConsentCategory.ANALYTICS, ConsentCategory.MARKETING])

    @model_validator(mode="after")
    def nobody_is_asked_about_what_makes_the_page_exist(self):
        if ConsentCategory.NECESSARY in self.optional:
            raise ValueError("the necessary category is what the site needs to answer at all, so it is never one a visitor is asked to allow")

        return self


class SiteSettings(BaseModel):
    """The public site, which is rendered by this process and carries a session of its own."""

    assets: Path = BASE_DIR / "webapps" / "site" / "dist"
    assets_url: str = "/static"

    # The tenant this instance serves when the host names none, which a machine with no domain of its own needs.
    default_tenant: str = ""

    # Where this instance answers, which a message written by a cron cannot read off a request that does not exist.
    domain: str = "change-me"

    # How many rows a listing of the site draws before it asks the visitor to turn the page.
    page_size: int = 20

    session_cookie: str = "fastkit_session"
    flash_cookie: str = "fastkit_flash"

    # The language a visitor chose, which is where it lives for somebody with no account to keep it in.
    language_cookie: str = "fastkit_language"
    language_max_age: int = 60 * 60 * 24 * 365

    # The palette a visitor chose, kept the same way and for the same reason as the language.
    theme_cookie: str = "fastkit_theme"
    theme_max_age: int = 60 * 60 * 24 * 365

    # The name a reader is counted by, which is kept only where somebody allowed analytics to be kept.
    visitor_cookie: str = "fastkit_visitor"
    visitor_max_age: int = 60 * 60 * 24 * 365

    consent: ConsentSettings = Field(default_factory=ConsentSettings)

    # How this environment addresses itself, which a message written by a cron cannot read off a request.
    scheme: Literal["http", "https"] = "https"

    # A cookie of a session travels over https, and the machine of whoever develops is the one that says it has none.
    cookie_secure: bool = True

    # How long a browser is told never to speak http with this host again, where zero is an installation saying not to tell it.
    hsts_max_age: int = 60 * 60 * 24 * 365
    cookie_max_age: int = 60 * 60 * 24 * 30
    csrf_ttl: int = 3600


class TenantSettings(BaseModel):
    """What one tenant overrides, where a field left out keeps whatever the environment declares."""

    email: EmailSettings | None = None


class SentrySettings(BaseModel):
    """Where a failure is reported, and an environment with no dsn reports nowhere."""

    dsn: str = ""
    traces_sample_rate: float = 0.0
    send_default_pii: bool = False
    include_local_variables: bool = False


class SecuritySettings(BaseModel):
    secret_key: str
    algorithm: str = "HS256"

    # The first key is what a secret is written with and every one of them opens what is stored, which is what makes a key able to be replaced.
    encryption_keys: list[str]

    # How many wrong passwords an account answers before it stops answering, and for how long it then stops.
    sign_in_attempts: int = 5
    sign_in_cooldown: int = 60
    sign_in_cooldown_max: int = 900

    # The cost of a hash is what protects a stolen table, and the defaults are what argon2 recommends for a server.
    password_memory_cost: int = 65_536
    password_time_cost: int = 3
    password_parallelism: int = 4


class RateLimitSettings(BaseModel):
    enabled: bool = True
    ip_limit: int = 300
    ip_window: int = 60
    total_limit: int = 3000
    total_window: int = 60

    # How many addresses the counter holds, because one that stops calling is never hit again and would sit there for as long as the process lives.
    tracked_clients: int = 50_000


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

    uploads: dict[UploadPurpose, UploadSettings] = Field(default_factory=default_uploads)
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

    @property
    def supported_languages(self) -> list[str]:
        return list(self.languages)

    def email_for(self, code: str | None) -> EmailSettings:
        """A tenant sends through what it declares, and through the environment default when it declares nothing."""
        override = self.tenants.get(code or "")

        return override.email if override and override.email else self.email


def derive(base: Settings, **overrides) -> Settings:
    """An environment starts from the one below it and states only what it changes, rebuilt so an override revalidates."""
    return Settings(**{**base.model_dump(), **overrides})
