from enum import StrEnum


class EmailProvider(StrEnum):
    SMTP = "smtp"

    # Printing a message instead of sending it is the machine of whoever develops saying so, and it is a provider like any other so that nothing chooses one by falling through.
    CONSOLE = "console"


class OutboundEmailStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"

    # The server refused the address itself, so trying again is writing to somebody who is not there.
    REFUSED = "refused"
