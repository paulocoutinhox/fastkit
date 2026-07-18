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
