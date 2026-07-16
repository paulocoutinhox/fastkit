from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_auth.models import Session
from fastkit_auth.passwords import PasswordHashService
from fastkit_auth.ratelimit import RateLimiter
from fastkit_auth.recaptcha import GoogleRecaptchaClient, RecaptchaConfig, RecaptchaVerifier, StaticRecaptchaClient
from fastkit_auth.service import AuthService
from fastkit_auth.sessions import SessionService
from fastkit_auth.tokens import TokenService


def build_recaptcha_verifier(settings) -> RecaptchaVerifier:
    recaptcha = settings.auth.recaptcha
    config = RecaptchaConfig(enabled=recaptcha.enabled, action=recaptcha.action, minimum_score=recaptcha.minimum_score, allowed_hostnames=tuple(recaptcha.allowed_hostnames))

    if recaptcha.enabled:
        client = GoogleRecaptchaClient(recaptcha.secret_key, recaptcha.timeout_seconds)
    else:
        client = StaticRecaptchaClient({"success": True, "action": recaptcha.action, "score": 1.0})

    return RecaptchaVerifier(config, client)


class AuthApp(FastKitApp):
    name = "fastkit.auth"
    label = "auth"
    version = "1.0.0"
    requires = ("fastkit.core", "fastkit.db", "fastkit.accounts")

    def register_models(self, context: BootstrapContext) -> None:
        context.models.register(Session, source=self.name)

    def register_services(self, context: BootstrapContext) -> None:
        settings = context.settings
        database = context.component("database")
        account_service = context.component("account_service")

        password_service = PasswordHashService(min_length=settings.auth.password_min_length, max_length=settings.auth.password_max_length)
        token_service = TokenService(secret_key=settings.app.secret_key, algorithm=settings.auth.jwt_algorithm, ttl_seconds=settings.auth.access_token_ttl_seconds)
        session_service = SessionService(database.session_factory, ttl_seconds=settings.auth.access_token_ttl_seconds)
        rate_limiter = RateLimiter(max_attempts=settings.auth.rate_limit_per_minute, window_seconds=60)
        recaptcha = build_recaptcha_verifier(settings)

        auth_service = AuthService(
            database.session_factory,
            account_service,
            password_service,
            session_service,
            token_service,
            rate_limiter,
            recaptcha,
            max_failed=settings.auth.max_failed_logins,
            lockout_seconds=settings.auth.lockout_seconds,
        )

        context.set_component("password_service", password_service)
        context.set_component("token_service", token_service)
        context.set_component("session_service", session_service)
        context.set_component("auth_service", auth_service)
