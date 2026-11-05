from pydantic import BaseModel


class RateLimitSettings(BaseModel):
    enabled: bool = True
    ip_limit: int = 300
    ip_window: int = 60
    total_limit: int = 3000
    total_window: int = 60

    # How many addresses the counter holds, because one that stops calling is never hit again and would sit there for as long as the process lives.
    tracked_clients: int = 50_000
