class Unreadable(Exception):
    """The gateway cannot be read — no key, or a key it refuses — and answering zero would read as a purchase that was handled."""
