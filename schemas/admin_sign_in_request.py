from schemas.challenged import Challenged
from schemas.sign_in_request import SignInRequest


class AdminSignInRequest(SignInRequest, Challenged):
    """The admin is a form somebody types into, so it carries the challenge the environment declared."""
