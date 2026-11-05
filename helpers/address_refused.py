"""The server refused the recipient rather than the message, which is the only refusal that says nobody is there."""


class AddressRefused(Exception):
    pass
