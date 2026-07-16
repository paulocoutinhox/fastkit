import pytest

from fastkit_config.loader import ConfigError, load_settings
from fastkit_config.public import is_sensitive_key, mask_value, public_frontend_config
from fastkit_config.settings import FastKitSettings


def write(directory, name, content):
    (directory / name).write_text(content)


def test_defaults_when_no_files(tmp_path):
    settings = load_settings(tmp_path, environment="dev", environ={})

    assert isinstance(settings, FastKitSettings)
    assert settings.app.environment == "dev"
    assert settings.auth.password_min_length == 12
    assert settings.admin.page_size == 25


def test_base_and_environment_merge(tmp_path):
    write(tmp_path, "base.toml", '[app]\nname = "Base"\ndebug = false\n[auth]\npassword_min_length = 8\n')
    write(tmp_path, "prod.toml", '[app]\ndebug = true\n')

    settings = load_settings(tmp_path, environment="prod", environ={})

    assert settings.app.name == "Base"
    assert settings.app.debug is True
    assert settings.auth.password_min_length == 8


def test_env_variable_override(tmp_path):
    write(tmp_path, "base.toml", '[app]\nname = "Base"\n')

    environ = {"FASTKIT__APP__NAME": "FromEnv", "FASTKIT__AUTH__PASSWORD_MIN_LENGTH": "20", "FASTKIT__APP__DEBUG": "true"}
    settings = load_settings(tmp_path, environment="dev", environ=environ)

    assert settings.app.name == "FromEnv"
    assert settings.auth.password_min_length == 20
    assert settings.app.debug is True


def test_env_override_into_a_scalar_path_is_a_clean_validation_error(tmp_path):
    import pydantic

    write(tmp_path, "base.toml", '[auth]\npassword_min_length = 8\n')

    # `auth.password_min_length` is a scalar, so nesting below it is malformed input; the loader
    # must surface a Pydantic ValidationError, never a bare TypeError from walking into a str
    with pytest.raises(pydantic.ValidationError):
        load_settings(tmp_path, environment="dev", environ={"FASTKIT__AUTH__PASSWORD_MIN_LENGTH__X": "1"})


def test_env_override_ignores_unrelated_vars(tmp_path):
    settings = load_settings(tmp_path, environment="dev", environ={"PATH": "/usr/bin", "FASTKIT__APP__TIMEZONE": "Europe/Lisbon"})

    assert settings.app.timezone == "Europe/Lisbon"


def test_app_env_selects_environment(tmp_path):
    write(tmp_path, "test.toml", '[app]\nname = "Testing"\n')

    settings = load_settings(tmp_path, environ={"APP_ENV": "test"})

    assert settings.app.name == "Testing"
    assert settings.app.environment == "test"


def test_invalid_environment_raises(tmp_path):
    with pytest.raises(ConfigError, match="unknown environment"):
        load_settings(tmp_path, environment="production", environ={})


def test_env_coercion_keeps_strings(tmp_path):
    settings = load_settings(tmp_path, environment="dev", environ={"FASTKIT__APP__NAME": "42abc"})

    assert settings.app.name == "42abc"


def test_public_config_excludes_secrets(tmp_path):
    settings = load_settings(tmp_path, environment="dev", environ={"FASTKIT__AUTH__RECAPTCHA__SITE_KEY": "public-key"})

    config = public_frontend_config(settings)

    assert config["recaptcha"]["siteKey"] == "public-key"
    assert config["adminApiBaseUrl"] == "/api"
    assert "secret_key" not in str(config)
    assert config["supportedLocales"] == ["en", "pt"]


def test_sensitive_key_detection():
    assert is_sensitive_key("secret_key")
    assert is_sensitive_key("AUTH_TOKEN")
    assert not is_sensitive_key("name")


def test_mask_value():
    assert mask_value("ab") == "****"
    assert mask_value("supersecret") == "su****et"
