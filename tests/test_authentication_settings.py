import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import ValidationError

from config.authentication_settings import AuthenticationSettings
from config.environment_helper import EnvironmentHelper
from enums.social_provider import SocialProvider
from helpers.settings import settings


def test_optional_authentication_is_disabled_without_credentials():
    configuration = AuthenticationSettings()

    assert not configuration.email.enabled
    assert not configuration.social
    assert not AuthenticationSettings(social={"google": {}}).social[SocialProvider.GOOGLE].enabled


@pytest.mark.parametrize("provider,values,message", [("google", {"client_secret": "secret"}, "client_id"), ("google", {"client_id": "client"}, "client_secret"), ("apple", {"client_id": "service"}, "team_id")])
def test_enabled_providers_refuse_incomplete_credentials(provider, values, message):
    with pytest.raises(ValidationError, match=message):
        AuthenticationSettings(social={provider: {"enabled": True, **values}})


def test_apple_credentials_are_validated_before_serving_requests(social_keys):
    configuration = AuthenticationSettings(social={"apple": {"enabled": True, "client_id": "service", "team_id": "team", "key_id": "key", "private_key": social_keys["apple"]}})

    assert configuration.social[SocialProvider.APPLE].enabled
    assert social_keys["apple"] not in repr(configuration)


@pytest.mark.parametrize("key_type", ["rsa", "wrong-curve", "invalid-pem"])
def test_apple_refuses_keys_that_cannot_sign_es256(social_keys, key_type):
    key = social_keys["private"].private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()

    if key_type == "wrong-curve":
        key = ec.generate_private_key(ec.SECP384R1()).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()

    if key_type == "invalid-pem":
        key = "not a private key"

    with pytest.raises(ValidationError):
        AuthenticationSettings(social={"apple": {"enabled": True, "client_id": "service", "team_id": "team", "key_id": "key", "private_key": key}})


@pytest.mark.parametrize("scheme,secure", [("http", False), ("http", True), ("https", False)])
def test_apple_requires_https_and_secure_cookies(social_keys, scheme, secure):
    authentication = AuthenticationSettings(social={"apple": {"enabled": True, "client_id": "service", "team_id": "team", "key_id": "key", "private_key": social_keys["apple"]}})

    with pytest.raises(ValidationError, match="apple"):
        EnvironmentHelper.derive(settings, site={"scheme": scheme, "cookie_secure": secure}, authentication=authentication)


def test_secure_apple_configuration_is_accepted(social_keys):
    authentication = AuthenticationSettings(social={"apple": {"enabled": True, "client_id": "service", "team_id": "team", "key_id": "key", "private_key": social_keys["apple"]}})
    configured = EnvironmentHelper.derive(settings, site={"scheme": "https", "cookie_secure": True}, authentication=authentication)

    assert configured.authentication.social[SocialProvider.APPLE].enabled


@pytest.mark.parametrize("values", [{"email": {"code_ttl": 1}}, {"email": {"max_attempts": 0}}, {"email": {"resend_interval": 0}}, {"social_ttl": 0}, {"ticket_ttl": 600}, {"social": {"unknown": {}}}, {"social": {"microsoft": {"microsoft_tenant": "common"}}}])
def test_authentication_settings_refuse_unsafe_limits_and_unknown_dispatch(values):
    with pytest.raises(ValidationError):
        AuthenticationSettings(**values)
