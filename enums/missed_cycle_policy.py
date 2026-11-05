from enum import StrEnum


class MissedCyclePolicy(StrEnum):
    SKIP = "skip"
    LATEST_ONLY = "latest-only"
    CATCH_UP = "catch-up"
