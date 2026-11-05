from pydantic import BaseModel


class RetentionSettings(BaseModel):
    """How long an operational table keeps what nothing will ever act on again, where zero keeps it forever."""

    system_log_days: int = 180
    app_event_days: int = 90
    webhook_event_days: int = 90
    outbound_email_days: int = 90
    client_request_days: int = 30
    banner_impression_days: int = 90
    cron_run_days: int = 30
    authentication_days: int = 1

    # The first pass of a table nobody ever trimmed would lock it for minutes, so it walks out in bites.
    batch: int = 1000
