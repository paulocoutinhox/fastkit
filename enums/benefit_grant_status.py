from enum import StrEnum


class BenefitGrantStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
