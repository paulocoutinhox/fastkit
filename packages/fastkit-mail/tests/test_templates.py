import pytest

from fastkit_core.errors.exceptions import FastKitError
from fastkit_mail.templates import MailTemplateRenderer


def test_render_default_template(renderer):
    rendered = renderer.render(
        "accounts.password_reset", {"user_name": "Ada", "reset_url": "https://x/y"}
    )

    assert rendered.subject == "Reset your password"
    assert "Ada" in rendered.html_body
    assert "https://x/y" in rendered.text_body
    assert rendered.template_path == "accounts/password_reset"


def test_project_override_wins(tmp_path, package_templates):
    override_dir = tmp_path / "accounts" / "welcome"
    override_dir.mkdir(parents=True)
    (override_dir / "subject.txt").write_text("Company welcome")
    (override_dir / "body.html").write_text("<p>hi</p>")
    (override_dir / "body.txt").write_text("hi")

    renderer = MailTemplateRenderer(search_dirs=[str(tmp_path), package_templates])
    rendered = renderer.render(
        "accounts.welcome", {"user_name": "Ada", "app_name": "Acme"}
    )

    assert rendered.subject == "Company welcome"


def test_missing_default_template_raises(package_templates):
    renderer = MailTemplateRenderer(search_dirs=[package_templates])

    with pytest.raises(FastKitError) as exc:
        renderer.render("accounts.does_not_exist", {})

    assert exc.value.error_code.code == "email.template_not_found"
