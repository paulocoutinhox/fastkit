from enum import StrEnum


class OutboundEmailStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"

    # The server refused the address itself, so trying again is writing to somebody who is not there.
    REFUSED = "refused"
