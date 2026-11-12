"""Mail links are absolute when PUBLIC_ORIGIN is set, and the HTML alternative
carries the wordmark, the button and the link in clear text. (The first
production mail, 2026-11-09, had a bare relative path and no button.)"""

from __future__ import annotations

import re

from app import email as email_service
from tests.test_night4 import _register

ORIGIN = "https://kollepedia.example"


def _token(body: str) -> str:
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    assert match, body
    return match.group(1)


def test_absolute_url_uses_public_origin(monkeypatch):
    monkeypatch.delenv("PUBLIC_ORIGIN", raising=False)
    assert email_service.absolute_url("/reset?token=x") == "/reset?token=x"
    monkeypatch.setenv("PUBLIC_ORIGIN", f"{ORIGIN}/")
    assert email_service.absolute_url("/reset?token=x") == f"{ORIGIN}/reset?token=x"


def test_render_html_carries_brand_button_and_escapes(monkeypatch):
    monkeypatch.setenv("PUBLIC_ORIGIN", ORIGIN)
    out = email_service.render_html(
        heading="Återställ ditt lösenord",
        name="<Anna> & Co",
        intro="Välj ett nytt lösenord.",
        button_label="Välj nytt lösenord",
        url=f"{ORIGIN}/reset?token=abc",
        note="Gäller i 24 timmar.",
    )
    assert "Kollepedia" in out and "NG</sup>" in out
    assert f'src="{ORIGIN}/email-mark.png"' in out
    assert out.count(f'href="{ORIGIN}/reset?token=abc"') == 2  # button + clear-text link
    assert "Välj nytt lösenord</a>" in out
    assert "&lt;Anna&gt; &amp; Co" in out and "<Anna>" not in out
    assert "#24439c" in out and "#f6f2ea" in out  # accent button on warm paper


def test_registration_and_reset_mails_are_absolute_and_html(client, monkeypatch):
    sent: list[dict] = []
    monkeypatch.setattr(email_service, "_send_smtp", lambda **kw: sent.append(kw))
    monkeypatch.setenv("SMTP_URL", "smtp://user:pass@smtp-relay.brevo.com:587")
    monkeypatch.setenv("EMAIL_ALLOWLIST", "*")
    monkeypatch.setenv("PUBLIC_ORIGIN", ORIGIN)

    _register(client, "anna", email="anna@example.org")
    verify = next(m for m in sent if m["to_addr"] == "anna@example.org")
    assert f"{ORIGIN}/verify-email?token=" in verify["body_text"]
    assert f'href="{ORIGIN}/verify-email?token=' in verify["body_html"]
    assert "Bekräfta e-postadressen</a>" in verify["body_html"]

    token = _token(verify["body_text"])
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 204
    forgot = client.post("/api/v1/auth/forgot", json={"handle_or_email": "anna@example.org"})
    assert forgot.status_code == 204
    reset = sent[-1]
    assert reset["to_addr"] == "anna@example.org"
    assert f"{ORIGIN}/reset?token=" in reset["body_text"]
    assert f'href="{ORIGIN}/reset?token=' in reset["body_html"]
    assert "Välj nytt lösenord</a>" in reset["body_html"]
    assert _token(reset["body_text"]) == _token(reset["body_html"])
