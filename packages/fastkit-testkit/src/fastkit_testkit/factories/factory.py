from fastkit_testkit.factories.sequence import Sequence


class Factory:
    """Minimal factory building dictionaries with per-call sequence values."""

    defaults: dict = {}

    def __init__(self):
        self._sequence = Sequence()

    def build(self, **overrides) -> dict:
        index = self._sequence.next()
        data = {}

        for key, value in self.defaults.items():
            data[key] = value(index) if callable(value) else value

        data.update(overrides)

        return data

    def build_batch(self, size: int, **overrides) -> list[dict]:
        return [self.build(**overrides) for _ in range(size)]
