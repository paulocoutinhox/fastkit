from enum import StrEnum


class EmailProvider(StrEnum):
    SMTP = "smtp"

    # Printing a message instead of sending it is the machine of whoever develops saying so, and it is a provider like any other so that nothing chooses one by falling through.
    CONSOLE = "console"
