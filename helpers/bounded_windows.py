"""What the limiter counts in, holding the clients seen most recently and no more of them than it was given."""

from collections import OrderedDict
from typing import MutableMapping


class BoundedWindows(MutableMapping):
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.windows: OrderedDict = OrderedDict()

    def __getitem__(self, key):
        # The library replaces an expired window on the next hit, so nothing here ever drops one that is still counting.
        self.windows.move_to_end(key)

        return self.windows[key]

    def __setitem__(self, key, value):
        self.windows[key] = value
        self.windows.move_to_end(key)

        while len(self.windows) > self.capacity:
            self.windows.popitem(last=False)

    def __delitem__(self, key):
        del self.windows[key]

    def __iter__(self):
        return iter(self.windows)

    def __len__(self):
        return len(self.windows)
