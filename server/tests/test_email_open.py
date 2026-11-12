"""EMAIL_ALLOWLIST=* is the one explicit way to let mail reach everyone."""

from __future__ import annotations

from app import email as email_service


def test_star_opens_the_gate_for_every_recipient(db, monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(email_service, "_send_smtp", lambda **kw: calls.append(kw))
    monkeypatch.setenv("SMTP_URL", "smtp://user:pass@smtp-relay.brevo.com:587")
    monkeypatch.setenv("EMAIL_ALLOWLIST", "*")

    sent = email_service.send(
        db, to_addr="ny.anvandare@example.org", subject="Hej", body_text="Välkommen", template="t"
    )
    assert sent.status == "sent"
    assert calls and calls[0]["to_addr"] == "ny.anvandare@example.org"


def test_star_inside_a_list_or_empty_value_never_opens_the_gate(db, monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(email_service, "_send_smtp", lambda **kw: calls.append(kw))
    monkeypatch.setenv("SMTP_URL", "smtp://user:pass@mail.example.org:587")

    monkeypatch.setenv("EMAIL_ALLOWLIST", "*, annan@example.org")
    mixed = email_service.send(
        db, to_addr="x@example.org", subject="s", body_text="b", template="t"
    )
    assert mixed.status == "blocked"

    monkeypatch.setenv("EMAIL_ALLOWLIST", "")
    empty = email_service.send(
        db, to_addr="x@example.org", subject="s", body_text="b", template="t"
    )
    assert empty.status == "blocked"
    assert calls == []
