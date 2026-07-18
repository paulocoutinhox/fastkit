from pydantic import BaseModel


class LoggingSettings(BaseModel):
    level: str = "INFO"
    file: str = "logs/app.log"
    system_log_enabled: bool = True
