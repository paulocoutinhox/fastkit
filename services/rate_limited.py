class RateLimited(Exception):
    """The provider asked for a pause, and it says in the answer how long it wants."""

    def __init__(self, seconds: float):
        super().__init__(f"rate limited for {seconds}s")

        self.seconds = seconds
