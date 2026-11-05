"""A page of the account reached by somebody with no session, which is a redirect and never an error page."""


class SignInRequired(Exception):
    pass
