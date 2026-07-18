from fastkit_auth.captcha.provider import CaptchaProvider


class DisabledCaptchaProvider(CaptchaProvider):
    """No captcha: verification always passes and the client renders nothing."""

    name = "disabled"

    @property
    def enabled(self) -> bool:
        return False

    async def verify(self, payload: dict | None) -> None:
        return None

    def client_config(self) -> dict:
        return {"provider": None, "enabled": False}
