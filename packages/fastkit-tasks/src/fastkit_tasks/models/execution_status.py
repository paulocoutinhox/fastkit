from enum import Enum


class ExecutionStatus(str, Enum):
    pending = "pending"
    running = "running"
    retrying = "retrying"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
