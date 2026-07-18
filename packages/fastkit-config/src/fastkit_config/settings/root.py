from pydantic import BaseModel, Field

from fastkit_config.settings.admin import AdminSettings
from fastkit_config.settings.app import AppSettings
from fastkit_config.settings.auth import AuthSettings
from fastkit_config.settings.cache import CacheSettings
from fastkit_config.settings.content import ContentSettings
from fastkit_config.settings.database import DatabaseSettings
from fastkit_config.settings.i18n import I18nSettings
from fastkit_config.settings.logging import LoggingSettings
from fastkit_config.settings.mail import MailSettings
from fastkit_config.settings.storage import StorageSettings
from fastkit_config.settings.task import TaskSettings


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
