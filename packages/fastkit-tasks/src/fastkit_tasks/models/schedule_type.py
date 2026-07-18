from enum import Enum


class ScheduleType(str, Enum):
    once = "once"
    interval = "interval"
    cron = "cron"
