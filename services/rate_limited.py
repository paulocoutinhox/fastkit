from services.silent import Silent


class RateLimited(Silent):
    """The provider asked for a pause and says in the answer how long it wants, which is a silence a request answers at once and only the sweep waits out."""

    def __init__(self, seconds: float):
        super().__init__(f"rate limited for {seconds}s")

        self.seconds = seconds
