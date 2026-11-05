"""A form whose page went stale, which is the page drawn again with a notice and never a body of JSON."""


class PageExpired(Exception):
    pass
