"""Outbound email — fail closed (iteration 4, tightened 2026-11-10).

Nothing leaves the process unless the operator has said so explicitly, twice:

1. ``SMTP_URL`` unset (the default) → every message is stored with status
   'outbox' and never sent. The allowlist plays no part here: there is no
   backend to reach anyone with.
2. ``SMTP_URL`` set (``smtp://user:pass@host:port``, STARTTLS) → the recipient
   must pass ``EMAIL_ALLOWLIST`` (comma-separated addresses), checked in
   send() BEFORE the backend is touched. An unset or empty allowlist blocks
   EVERY recipient (status 'blocked'); the single value ``*`` is the
   production switch that lets everyone through. There is no built-in
   default address — a self-hosted instance must never carry someone else's
   mailbox as a constant.
3. The sender is ``EMAIL_FROM``, else the SMTP user name. With neither the
   message stays 'queued' and a warning is logged: a half-configured relay
   must not make the server invent a From address.
4. Every message — outboxed, blocked, queued or sent — is persisted to
   ``email_messages`` so a super admin can audit everything via
   GET /admin/outbox.

send() never raises: email is best-effort by design, and auth flows (e.g.
/auth/forgot) must not leak delivery problems to the caller. Credentials and
recipient addresses are never logged.
"""

import html
import logging
import os
import smtplib
from email.message import EmailMessage as MimeMessage
from urllib.parse import unquote, urlparse

from sqlalchemy.orm import Session

from .models import EmailMessage, utcnow

logger = logging.getLogger("kollepedia.email")

SMTP_TIMEOUT_S = 30.0


EVERYONE = "*"


def allowlist() -> set[str]:
    """The recipients we are allowed to email, lower-cased. Unset or empty
    EMAIL_ALLOWLIST is the EMPTY set — nobody — never a built-in address.
    The single value ``*`` is the production switch (see recipient_allowed)."""
    raw = os.getenv("EMAIL_ALLOWLIST", "")
    return {addr.strip().lower() for addr in raw.split(",") if addr.strip()}


def recipient_allowed(to_addr: str) -> bool:
    """The gate send() applies before any backend. ``EMAIL_ALLOWLIST=*`` opens
    it for every recipient — the deliberate production setting, where
    registration, verification and password resets must reach real users.
    Anything else (unset, empty, a list) stays a hard allowlist."""
    if allowlist() == {EVERYONE}:
        return True
    return to_addr.strip().lower() in allowlist()


def sender_address(smtp_url: str) -> str | None:
    """EMAIL_FROM, else the SMTP user name, else None (nothing is sent then)."""
    explicit = os.getenv("EMAIL_FROM", "").strip()
    if explicit:
        return explicit
    username = urlparse(smtp_url).username
    return unquote(username) if username else None


def public_origin() -> str:
    """The site's public origin (env ``PUBLIC_ORIGIN``, e.g. https://kollepedia.se),
    set per environment in the compose files. Empty in local development."""
    return os.getenv("PUBLIC_ORIGIN", "").strip().rstrip("/")


def absolute_url(path: str) -> str:
    """A link a mail client can follow: PUBLIC_ORIGIN + path. Without an origin
    the path is returned as is (local outbox only — nothing is sent there)."""
    origin = public_origin()
    return f"{origin}{path}" if origin else path


SERIF = "'Crimson Pro',Georgia,'Times New Roman',serif"
SANS = "'Familjen Grotesk',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "'Fragment Mono',ui-monospace,Menlo,Consolas,monospace"


def render_html(
    *, heading: str, name: str, intro: str, button_label: str, url: str, note: str
) -> str:
    """A transactional mail in Kollepedia's own form: warm paper, serif prose,
    the wordmark, one primary button and the link in clear text underneath.
    Colours and radii are the light theme's tokens (web/src/app.css); the fonts
    fall back to what the mail client has. Every value is escaped."""
    e = html.escape
    origin = public_origin()
    mark = (
        f'<img src="{e(origin)}/email-mark.png" width="32" height="32" alt="" '
        'style="display:block;border:0;border-radius:7px">'
        if origin
        else ""
    )
    site = f'<a href="{e(origin)}" style="color:#736a5c;">kollepedia.se</a>' if origin else ""
    site = site or "kollepedia.se"
    prose = "font-size:18px;line-height:1.55;color:#52493c;"
    small = f"font-family:{SANS};font-size:13px;line-height:1.5;color:#736a5c;"
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="sv"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width">',
            f"<title>{e(heading)}</title></head>",
            '<body style="margin:0;padding:0;background:#f6f2ea;">',
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"',
            ' style="background:#f6f2ea;"><tr><td align="center" style="padding:32px 16px;">',
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"',
            ' style="max-width:560px;background:#fdfbf6;border:1px solid #ddd4c3;',
            ' border-radius:14px;">',
            '<tr><td style="padding:28px 32px 0 32px;">',
            '<table role="presentation" cellpadding="0" cellspacing="0"><tr>',
            f'<td style="padding-right:12px;vertical-align:middle;">{mark}</td>',
            f'<td style="vertical-align:middle;font-family:{SERIF};font-size:26px;',
            ' font-weight:600;letter-spacing:-0.01em;color:#211c15;">Kollepedia<sup',
            f' style="font-family:{SANS};font-size:11px;font-weight:500;color:#736a5c;',
            ' vertical-align:top;">NG</sup></td>',
            "</tr></table></td></tr>",
            f'<tr><td style="padding:28px 32px 0 32px;font-family:{SERIF};color:#211c15;">',
            '<h1 style="margin:0 0 16px 0;font-size:24px;line-height:1.25;font-weight:600;">',
            f"{e(heading)}</h1>",
            f'<p style="margin:0 0 12px 0;{prose}">Hej {e(name)}!</p>',
            f'<p style="margin:0 0 24px 0;{prose}">{e(intro)}</p>',
            '<table role="presentation" cellpadding="0" cellspacing="0"><tr>',
            '<td style="background:#24439c;border-radius:8px;">',
            f'<a href="{e(url)}" style="display:inline-block;padding:12px 22px;',
            f" font-family:{SANS};font-size:15px;font-weight:500;line-height:1.45;",
            ' color:#fdfbf6;text-decoration:none;border-radius:8px;">',
            f"{e(button_label)}</a></td></tr></table>",
            f'<p style="margin:24px 0 0 0;{small}">',
            "Fungerar inte knappen? Kopiera länken till webbläsaren:<br>",
            f'<a href="{e(url)}" style="color:#24439c;word-break:break-all;',
            f' font-family:{MONO};font-size:12px;">{e(url)}</a></p></td></tr>',
            '<tr><td style="padding:24px 32px 28px 32px;">',
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>',
            f'<td style="border-top:1px solid #ddd4c3;padding-top:16px;{small}">',
            f"{e(note)}<br>Kollepedia · {site} · Linderå Group AB</td>",
            "</tr></table></td></tr></table></td></tr></table></body></html>",
        ]
    )


def _send_smtp(
    *,
    to_addr: str,
    subject: str,
    body_text: str,
    smtp_url: str,
    from_addr: str,
    body_html: str | None = None,
) -> None:
    """One SMTP delivery over STARTTLS. smtp://user:pass@host:port. With
    body_html the message is multipart/alternative: text first, HTML second."""
    parts = urlparse(smtp_url)
    host = parts.hostname or "localhost"
    port = parts.port or 587
    username = unquote(parts.username) if parts.username else None
    password = unquote(parts.password) if parts.password else None

    message = MimeMessage()
    message["From"] = from_addr
    message["To"] = to_addr
    message["Subject"] = subject
    message.set_content(body_text)
    if body_html:
        message.add_alternative(body_html, subtype="html")

    with smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_S) as smtp:
        smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)


def send(
    db: Session,
    *,
    to_addr: str,
    subject: str,
    body_text: str,
    template: str,
    body_html: str | None = None,
) -> EmailMessage:
    """Store-and-maybe-send. Returns the persisted EmailMessage row; the
    caller commits. The text body is what gets stored and audited; body_html
    (render_html) only travels as the mail's HTML alternative. Status outcomes:

    - 'outbox'  — no SMTP_URL: stored only, nothing can be sent
    - 'blocked' — SMTP configured but the recipient is not allowlisted
                  (NEVER sent, no backend touched)
    - 'queued'  — SMTP configured but no sender address, or delivery failed
                  (kept for retry/audit)
    - 'sent'    — SMTP delivery succeeded
    """
    message = EmailMessage(
        to_addr=to_addr,
        subject=subject,
        body_text=body_text,
        template=template,
        status="outbox",
    )
    db.add(message)

    smtp_url = os.getenv("SMTP_URL", "").strip()
    if not smtp_url:
        db.flush()
        return message

    # THE hard safety gate: enforced before any backend, regardless of config.
    if not recipient_allowed(to_addr):
        message.status = "blocked"
        db.flush()
        return message

    message.status = "queued"
    db.flush()
    from_addr = sender_address(smtp_url)
    if from_addr is None:
        logger.warning(
            "No sender address (EMAIL_FROM unset and SMTP_URL has no user name); "
            "message kept as 'queued'."
        )
        return message
    try:
        _send_smtp(
            to_addr=to_addr,
            subject=subject,
            body_text=body_text,
            smtp_url=smtp_url,
            from_addr=from_addr,
            body_html=body_html,
        )
    except Exception as exc:
        # Exception class only — SMTP errors can embed addresses/credentials.
        logger.warning("SMTP delivery failed (%s); message kept as 'queued'.", type(exc).__name__)
        return message
    message.status = "sent"
    message.sent_at = utcnow()
    db.flush()
    return message
