from pydantic import BaseModel


class SentrySettings(BaseModel):
    """Where a failure is reported, and an environment with no dsn reports nowhere."""

    dsn: str = ""
    traces_sample_rate: float = 0.0
    user_info: bool = False
    include_local_variables: bool = False
