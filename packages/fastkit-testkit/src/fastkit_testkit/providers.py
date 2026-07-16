class RecordingHook:
    """Records event payloads so tests can assert that hooks fired."""

    def __init__(self):
        self.calls: list[dict] = []

    async def __call__(self, event) -> None:
        self.calls.append(dict(event.payload))

    @property
    def count(self) -> int:
        return len(self.calls)

    def last(self) -> dict:
        if not self.calls:
            raise AssertionError("hook was never called")

        return self.calls[-1]


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
