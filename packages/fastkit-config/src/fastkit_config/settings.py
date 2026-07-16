from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    name: str = "FastKit App"
    environment: str = "dev"
    debug: bool = False
    timezone: str = "UTC"
    secret_key: str = "change-me"


class DatabaseSettings(BaseModel):
    url: str = "sqlite+aiosqlite:///./data/app.db"
    pool_pre_ping: bool = True
    echo: bool = False


class RecaptchaSettings(BaseModel):
    enabled: bool = False
    provider: str = "google_v3"
    site_key: str = ""
    secret_key: str = ""
    action: str = "admin_login"
    minimum_score: float = 0.5
    allowed_hostnames: list[str] = Field(default_factory=list)
    timeout_seconds: int = 5


class AuthSettings(BaseModel):
    login_identifier_types: list[str] = Field(default_factory=lambda: ["email", "username", "phone"])
    session_cookie_name: str = "fastkit_session"
    password_min_length: int = 12
    password_max_length: int = 128
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 3600
    max_failed_logins: int = 5
    lockout_seconds: int = 900
    rate_limit_per_minute: int = 10
    recaptcha: RecaptchaSettings = Field(default_factory=RecaptchaSettings)


class AdminSettings(BaseModel):
    enabled: bool = True
    path: str = "/admin"
    api_path: str = "/api"
    theme: str = "tabler"
    page_size: int = 25
    page_size_options: list[int] = Field(default_factory=lambda: [10, 25, 50, 100])


class CacheSettings(BaseModel):
    provider: str = "file"
    default_ttl_seconds: int = 300
    directory: str = "./data/cache"
    redis_url: str = "redis://localhost:6379/0"


class TaskSettings(BaseModel):
    provider: str = "database"
    worker_lease_seconds: int = 60
    run_worker: bool = False
    worker_id: str = "in-process"
    worker_queues: list[str] | None = None
    poll_interval_seconds: float = 1.0


class StorageSettings(BaseModel):
    provider: str = "local"
    root: str = "./data/media"
    base_url: str = "/media"


class MailSettings(BaseModel):
    provider: str = "smtp"
    host: str = "localhost"
    port: int = 1025
    username: str = ""
    password: str = ""
    use_tls: bool = False
    default_from: str = "no-reply@fastkit.local"


class I18nSettings(BaseModel):
    default_locale: str = "en"
    supported_locales: list[str] = Field(default_factory=lambda: ["en", "pt"])


class LoggingSettings(BaseModel):
    level: str = "INFO"
    file: str = "logs/app.log"
    system_log_enabled: bool = True


class ContentSettings(BaseModel):
    sanitize_html: bool = True


class FastKitSettings(BaseModel):
    installed_apps: list[str] = Field(default_factory=list)
    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    admin: AdminSettings = Field(default_factory=AdminSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    tasks: TaskSettings = Field(default_factory=TaskSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    mail: MailSettings = Field(default_factory=MailSettings)
    i18n: I18nSettings = Field(default_factory=I18nSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    content: ContentSettings = Field(default_factory=ContentSettings)
