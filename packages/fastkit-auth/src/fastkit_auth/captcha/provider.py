from abc import ABC, abstractmethod


class CaptchaProvider(ABC):
    """Contract for a login captcha.

    A provider verifies the payload the browser submits with the login, describes to the client how
    to render itself, and may mount its own challenge routes (a self-hosted image captcha serves
    images, a third-party token captcha does not). The payload shape is provider-defined: a token
    captcha sends ``{"token": ...}``, an image captcha sends ``{"challenge_id": ..., "answer": ...}``.
    """

    name = "captcha"

    @property
    @abstractmethod
    def enabled(self) -> bool:
        ...

    @abstractmethod
    async def verify(self, payload: dict | None) -> None:
        ...

    def client_config(self) -> dict:
        return {"provider": self.name, "enabled": self.enabled}

    def mount_routes(self, router) -> None:
        return None
