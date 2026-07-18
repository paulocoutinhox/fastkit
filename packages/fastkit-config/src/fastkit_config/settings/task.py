from pydantic import BaseModel


class TaskSettings(BaseModel):
    provider: str = "database"
    worker_lease_seconds: int = 60
    run_worker: bool = False
    worker_id: str = "in-process"
    worker_queues: list[str] | None = None
    poll_interval_seconds: float = 1.0
