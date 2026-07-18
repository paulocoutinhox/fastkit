class FakeMailbox:
    """Generic in-memory mailbox for asserting on sent messages."""

    def __init__(self):
        self.messages: list[dict] = []

    def deliver(self, to: list[str], subject: str, body: str) -> None:
        self.messages.append({"to": to, "subject": subject, "body": body})

    def to(self, address: str) -> list[dict]:
        return [message for message in self.messages if address in message["to"]]

    def clear(self) -> None:
        self.messages.clear()
