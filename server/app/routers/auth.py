"""Auth: register / login / me / refresh / logout / password / reset / email.

- argon2 password hashes, JWT HS256 access tokens (12-hour exp, sub = user id).
- Refresh tokens (iteration 3): opaque 30-day tokens in the httpOnly cookie
  `kollepedia_refresh` (SameSite=Lax, path=/api/v1/auth), stored server-side
  as SHA-256 hashes and ROTATED on every /auth/refresh — replaying a revoked
  token is a hard 401. Logout revokes and clears the cookie.
- Identity is EMAIL-FIRST (iteration 4): register requires a unique email (the
  login identifier) + display_name + password; the handle is internal and
  auto-slugified from the display name (numeric de-dup). An explicit handle
  is only passed by the author-activation flow (/activate) to claim an
  imported identity — claiming an unclaimed handle (password_hash IS NULL)
  keeps its display name; a handle that already has a password → 409.
  A verification email is sent on register (outbox/allowlist rules).
- Login takes {identifier, password} — email first, then handle — and still
  accepts the old {handle, password} body shape.
- The first user to register a password becomes super admin.
- /auth/reset consumes a one-time token minted by a super admin
  (routers/admin_users.py) or by /auth/forgot (verified email required) and
  revokes all of the user's refresh tokens. Changing the password or the
  email address revokes every OTHER session's refresh token (the browser
  doing the change keeps its own) — stolen-session containment without
  logging the legitimate user out.
- The refresh cookie is Secure unless the X-User dev fallback is on (plain
  http in local development only).
- Login always runs one argon2 verification, against a dummy hash when the
  account is unknown or has no password, so response time does not reveal
  which identifiers exist or are unclaimed.
"""

import hashlib
import os
import re
import secrets
import unicodedata
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import email as email_service
from .. import ratelimit
from ..db import get_db
from ..deps import create_token, dev_auth_enabled, require_user
from ..errors import api_error
from ..models import (
    ActivationToken,
    EmailVerifyToken,
    RefreshToken,
    RegistrationEvent,
    ResetToken,
    User,
    utcnow,
)
from ..pow import create_challenge, verify_solution

router = APIRouter(prefix="/auth", tags=["auth"])

_hasher = PasswordHasher()
# Verified against when there is no real hash to check (unknown identifier or
# unclaimed imported profile), so every login attempt costs the same argon2
# work. Random per process: it can never match a submitted password.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))

REFRESH_COOKIE = "kollepedia_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"
REFRESH_TTL = timedelta(days=30)
VERIFY_TTL = timedelta(hours=48)
FORGOT_RESET_TTL = timedelta(hours=24)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _as_utc(dt: datetime) -> datetime:
    """SQLite hands back naive datetimes — normalise before comparing."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_refresh_cookie(db: Session, user: User, response: Response) -> None:
    """Mint a fresh refresh token (hash in DB, raw value in the cookie)."""
    raw = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=utcnow() + REFRESH_TTL,
        )
    )
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=int(REFRESH_TTL.total_seconds()),
        httponly=True,
        # Secure whenever this is a real instance: the browser then never sends
        # the token over plain http, whatever the proxy in front answers on.
        secure=not dev_auth_enabled(),
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def revoke_all_refresh_tokens(db: Session, user_id: str) -> int:
    return (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .update({RefreshToken.revoked: True})
    )


def revoke_other_refresh_tokens(db: Session, user_id: str, request: Request) -> int:
    """Revoke every live refresh token except the one this browser presents
    in its cookie (if any). Used when credentials change: other devices —
    including a thief's — must log in again, the acting session stays."""
    query = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)
    )
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        query = query.filter(RefreshToken.token_hash != hash_token(raw))
    return query.update({RefreshToken.revoked: True})


def normalise_handle(handle: str) -> str:
    return handle.strip().lower().replace(" ", "-")


def normalise_email(email: str) -> str:
    return email.strip().lower()


def slugify_handle(display_name: str) -> str:
    """Derive an internal handle from a display name: ASCII-fold, lower-case,
    non-alphanumerics → hyphen, collapsed. Never returns an empty string."""
    folded = unicodedata.normalize("NFKD", display_name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    return slug[:100] or "anvandare"


def derive_handle(db: Session, display_name: str) -> str:
    """Auto-slugified handle with numeric de-dup (anna, anna-2, anna-3 …).
    Existing handles are never silently claimed — claiming requires an
    explicit handle (the /activate flow)."""
    base = slugify_handle(display_name)
    handle = base
    suffix = 2
    while db.query(User).filter(User.handle == handle).first() is not None:
        handle = f"{base[: 100 - len(str(suffix)) - 1]}-{suffix}"
        suffix += 1
    return handle


class PowSolutionIn(BaseModel):
    """A solved proof-of-work challenge (see app/pow.py). Required on every
    registration — the browser widget solves it in the background."""

    salt: str = Field(max_length=64)
    issued: int
    expires: int
    bits: int = Field(ge=1, le=32)
    signature: str = Field(max_length=64)
    number: int = Field(ge=0)


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=200)
    # The public username, chosen at registration. The author-activation flow
    # (/activate) also passes it, together with claim=True, to take over an
    # imported identity.
    handle: str | None = Field(default=None, min_length=2, max_length=100)
    claim: bool = False
    # Personal activation-link token (minted from the outreach workbench).
    # A valid token makes the claim verified — no manual review needed.
    claim_token: str | None = Field(default=None, max_length=200)
    # Bot defence: solved PoW challenge + honeypot (a hidden field humans
    # never see — any content is a hard reject).
    pow: PowSolutionIn | None = None
    website: str = ""


class ChallengeOut(BaseModel):
    salt: str
    issued: int
    expires: int
    bits: int
    signature: str


class LoginIn(BaseModel):
    # identifier matches email first, then handle. The old {handle, password}
    # body shape is still accepted (claimed authors, older clients).
    identifier: str | None = None
    handle: str | None = None
    password: str


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=200)


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=12, max_length=200)


class OrgRefOut(BaseModel):
    id: str
    slug: str
    name: str
    role: str
    kind: str = "member"
    is_public: bool = True
    is_owner: bool = False


class AuthUserOut(BaseModel):
    id: str
    handle: str
    display_name: str
    affiliation: str | None = None
    bio: str | None = None
    web_url: str | None = None
    email: str | None = None
    email_verified: bool = False
    is_super_admin: bool = False
    review_status: str = "approved"
    # Multi-org (2026-07): all ACTIVE memberships.
    memberships: list[OrgRefOut] = []


class AuthOut(BaseModel):
    token: str
    user: AuthUserOut


def auth_user_out(user: User) -> AuthUserOut:
    memberships = [
        OrgRefOut(
            id=m.organisation.id,
            slug=m.organisation.slug,
            name=m.organisation.name,
            role=m.role,
            kind=m.kind,
            is_public=m.is_public,
            is_owner=m.organisation.owner_user_id == user.id,
        )
        for m in user.memberships
        if m.ended_at is None
    ]
    memberships.sort(key=lambda m: m.name.lower())
    return AuthUserOut(
        id=user.id,
        handle=user.handle,
        display_name=user.display_name,
        affiliation=user.affiliation,
        bio=user.bio,
        web_url=user.web_url,
        email=user.email,
        email_verified=user.email_verified,
        is_super_admin=user.is_super_admin,
        review_status=user.review_status,
        memberships=memberships,
    )


def send_verification_email(db: Session, user: User) -> None:
    """Mint a 48-hour one-time token and email the verification link. The
    link is a relative path — the frontend prefixes its own origin."""
    if not user.email:
        return
    raw = secrets.token_urlsafe(32)
    db.add(
        EmailVerifyToken(
            user_id=user.id,
            email=user.email,
            token_hash=hash_token(raw),
            expires_at=utcnow() + VERIFY_TTL,
        )
    )
    url = email_service.absolute_url(f"/verify-email?token={raw}")
    note = (
        "Länken gäller i 48 timmar. Om du inte begärde detta kan du ignorera det här meddelandet."
    )
    email_service.send(
        db,
        to_addr=user.email,
        subject="Bekräfta din e-postadress på Kollepedia",
        body_text=(
            f"Hej {user.display_name}!\n\n"
            f"Bekräfta din e-postadress genom att öppna länken:\n\n{url}\n\n{note}"
        ),
        body_html=email_service.render_html(
            heading="Bekräfta din e-postadress",
            name=user.display_name,
            intro=(
                "Ett tryck på knappen bekräftar att adressen är din och att "
                "Kollepedia får skicka post till den."
            ),
            button_label="Bekräfta e-postadressen",
            url=url,
            note=note,
        ),
        template="verify_email",
    )


# Bot/SPAM defence (migration 008). The history is immutable — junk accounts
# would write junk into it forever — so registration is hardened in layers:
# PoW (cost), honeypot (naive bots), disposable-domain + source-velocity +
# fill-time heuristics (suspicious → manual review by a super admin).
DISPOSABLE_DOMAINS = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "guerrillamail.de",
        "10minutemail.com",
        "10minutemail.net",
        "tempmail.com",
        "temp-mail.org",
        "throwawaymail.com",
        "yopmail.com",
        "sharklasers.com",
        "getnada.com",
        "dispostable.com",
        "maildrop.cc",
        "mintemail.com",
        "trashmail.com",
        "mailnesia.com",
        "fakeinbox.com",
        "spamgourmet.com",
        "mytemp.email",
        "burnermail.io",
    }
)
VELOCITY_WINDOW = timedelta(hours=24)


def _velocity_limit() -> int:
    """Registrations per source per window before review. Env-tunable
    (tests raise it — the TestClient has a single constant source IP)."""
    return int(os.getenv("REG_VELOCITY_LIMIT", "3"))


def _client_ip_hash(request: Request) -> str:
    """Source key for the velocity heuristic — the same proxy-aware address
    as the rate limiter (last X-Forwarded-For entry, never the first, which
    a registrant could set freely to dodge the count)."""
    return hashlib.sha256(ratelimit.client_ip(request).encode("utf-8")).hexdigest()


def _suspicion_reasons(db: Session, email: str, ip_hash: str, too_fast: bool) -> list[str]:
    reasons: list[str] = []
    domain = email.rsplit("@", 1)[-1].lower()
    if domain in DISPOSABLE_DOMAINS:
        reasons.append("engångsadress (disposable e-postdomän)")
    cutoff = utcnow() - VELOCITY_WINDOW
    db.query(RegistrationEvent).filter(RegistrationEvent.created_at < cutoff).delete()
    recent = (
        db.query(func.count(RegistrationEvent.id))
        .filter(RegistrationEvent.ip_hash == ip_hash, RegistrationEvent.created_at >= cutoff)
        .scalar()
        or 0
    )
    if recent >= _velocity_limit():
        reasons.append(f"{recent} registreringar från samma källa på 24 timmar")
    if too_fast:
        reasons.append("formuläret skickades snabbare än en människa läser det")
    return reasons


def _notify_review_pending(db: Session, user: User) -> None:
    """Tell every super admin with an email that an account awaits review.
    Goes through the hard allowlist/outbox gate like all mail."""
    admins = db.query(User).filter(User.is_super_admin.is_(True), User.email.isnot(None)).all()
    for admin in admins:
        email_service.send(
            db,
            to_addr=admin.email or "",
            subject="Kollepedia: nytt konto väntar på granskning",
            body_text=(
                f"Kontot '{user.handle}' ({user.email}) har flaggats vid "
                f"registreringen och väntar på manuell granskning.\n\n"
                f"Orsak: {user.review_reason}\n\n"
                f"Granska under /admin/users (filter: väntar på granskning). "
                f"Kontot kan läsa men inte skriva förrän det godkänts."
            ),
            template="account_review",
        )


@router.get("/challenge", response_model=ChallengeOut)
def challenge() -> ChallengeOut:
    """Proof-of-work challenge for registration. Self-hosted (no third-party
    CAPTCHA, nothing leaves the EU server); single-use; 15-minute expiry."""
    c = create_challenge()
    return ChallengeOut(
        salt=c.salt, issued=c.issued, expires=c.expires, bits=c.bits, signature=c.signature
    )


@router.post("/register", response_model=AuthOut, status_code=201)
def register(
    payload: RegisterIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthOut:
    email = normalise_email(payload.email)
    if not EMAIL_RE.match(email):
        raise api_error(422, "invalid_email", "Invalid email address.")
    display_name = payload.display_name.strip()

    # Honeypot: the field is invisible in the real form — content means a bot.
    if payload.website.strip():
        raise api_error(400, "registration_rejected", "Registration could not be completed.")

    # Proof-of-work: mandatory, verified server-side, single-use.
    if payload.pow is None:
        raise api_error(
            400,
            "pow_missing",
            "Robot check is missing — reload the page and try again.",
        )
    pow_result = verify_solution(
        db,
        salt=payload.pow.salt,
        issued=payload.pow.issued,
        expires=payload.pow.expires,
        bits=payload.pow.bits,
        signature=payload.pow.signature,
        number=payload.pow.number,
    )
    if not pow_result.ok:
        raise api_error(
            400,
            "pow_invalid",
            "Robot check failed — reload the page and try again.",
            reason=pow_result.error,
        )

    user: User | None = None
    if payload.handle:
        handle = normalise_handle(payload.handle)
        if not handle or len(handle) < 2:
            raise api_error(422, "invalid_handle", "Invalid handle.")
        existing = db.query(User).filter(User.handle == handle).first()
        if existing is not None and existing.password_hash is not None:
            raise api_error(
                409,
                "handle_taken",
                "Handle is taken — choose another or log in.",
                handle=handle,
            )
        if existing is not None and not existing.is_active:
            raise api_error(403, "account_suspended", "Account is suspended.")
        if existing is not None and not payload.claim:
            # The username belongs to an imported, unclaimed author. Claiming
            # is a deliberate act (/activate) — point there instead of silently
            # taking over the identity.
            raise api_error(
                409,
                "handle_unclaimed",
                "The handle belongs to an imported author profile — claim it via the author page.",
                handle=handle,
            )
        user = existing
    else:
        # Legacy shape (no username chosen): derive from the display name.
        handle = derive_handle(db, display_name or "anvandare")

    # True when this registration takes over an imported, unclaimed identity.
    # A personal activation token (outreach workbench) verifies the claim by
    # construction; without one the claim goes through manual review below.
    claiming_import = user is not None
    claim_verified = False
    if claiming_import and payload.claim_token:
        assert user is not None
        token_row = (
            db.query(ActivationToken)
            .filter(ActivationToken.token_hash == hash_token(payload.claim_token))
            .first()
        )
        if (
            token_row is None
            or token_row.consumed_at is not None
            or _as_utc(token_row.expires_at) <= utcnow()
            or token_row.user_id != user.id
        ):
            raise api_error(
                400,
                "activation_token_invalid",
                "Activation link is invalid, already used, or expired.",
            )
        token_row.consumed_at = utcnow()
        claim_verified = True

    email_owner = db.query(User).filter(func.lower(User.email) == email).first()
    if email_owner is not None and (user is None or email_owner.id != user.id):
        if email_owner.password_hash is None:
            # The address sits on an imported, unclaimed author profile —
            # lead the person to the claim flow instead of a dead end.
            raise api_error(
                409,
                "email_unclaimed",
                "The email address belongs to an imported author profile — "
                "claim it via the author page.",
                handle=email_owner.handle,
            )
        raise api_error(
            409,
            "email_taken",
            "Email address is already registered — log in instead.",
        )

    # First account with a password becomes super admin.
    first_account = db.query(User).filter(User.password_hash.isnot(None)).count() == 0

    if user is None:
        user = User(handle=handle, display_name=display_name or handle)
        db.add(user)
        db.flush()
    elif user.display_name == user.handle and display_name:
        # Claimed identity keeps its display name — except a bare placeholder
        # (auto-created in dev, display_name == handle) which is upgraded.
        user.display_name = display_name

    if user.email != email:
        user.email = email
        user.email_verified = False
        user.email_verified_at = None
    user.password_hash = _hasher.hash(payload.password)
    if first_account:
        user.is_super_admin = True

    # Suspicion heuristics → manual review (never for the bootstrap account).
    ip_hash = _client_ip_hash(request)
    db.add(RegistrationEvent(ip_hash=ip_hash))
    db.flush()  # the velocity count below must see this attempt (autoflush off)
    if not first_account:
        reasons = _suspicion_reasons(db, email, ip_hash, pow_result.too_fast)
        if claiming_import and not claim_verified:
            # Anyone can claim any unclaimed author with any email address —
            # by construction an identity takeover. A super admin must approve
            # before the account gets write access (2026-08-12). A personal
            # activation token (2026-08-13) IS that verification.
            reasons.append("anspråk på importerad författarprofil – kräver manuell verifiering")
        if reasons:
            user.review_status = "pending"
            user.review_reason = "; ".join(reasons)
            _notify_review_pending(db, user)

    issue_refresh_cookie(db, user, response)
    send_verification_email(db, user)
    db.commit()
    return AuthOut(token=create_token(user.id), user=auth_user_out(user))


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> AuthOut:
    identifier = (payload.identifier or payload.handle or "").strip()
    if not identifier:
        raise api_error(422, "identifier_required", "Provide an email address or handle.")
    # Email first, then handle (claimed authors and old accounts still work).
    user = db.query(User).filter(func.lower(User.email) == identifier.lower()).first()
    if user is None:
        user = db.query(User).filter(User.handle == normalise_handle(identifier)).first()
    # Constant work: unknown identifiers and passwordless (unclaimed imported)
    # profiles are verified against the dummy hash so the 401 takes as long
    # as a wrong password does.
    stored_hash = user.password_hash if user is not None and user.password_hash else _DUMMY_HASH
    try:
        _hasher.verify(stored_hash, payload.password)
    except (VerificationError, InvalidHashError) as exc:
        raise api_error(401, "wrong_credentials", "Wrong credentials or password.") from exc
    if user is None or not user.password_hash:
        # Unreachable in practice (the dummy never verifies) — kept so the
        # type checker and a future hash change cannot turn this into a login.
        raise api_error(401, "wrong_credentials", "Wrong credentials or password.")
    if not user.is_active:
        raise api_error(403, "account_suspended", "Account is suspended.")
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _hasher.hash(payload.password)
    issue_refresh_cookie(db, user, response)
    db.commit()
    return AuthOut(token=create_token(user.id), user=auth_user_out(user))


@router.post("/refresh", response_model=AuthOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> AuthOut:
    """Rotate the refresh token: validate + revoke the presented one, issue a
    new cookie and a new access token."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise api_error(401, "refresh_token_missing", "No refresh token.")
    token = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(raw)).first()
    if token is None or token.revoked or _as_utc(token.expires_at) <= utcnow():
        raise api_error(401, "refresh_token_invalid", "Refresh token is invalid — log in again.")
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise api_error(403, "account_suspended", "Account is suspended.")
    token.revoked = True
    issue_refresh_cookie(db, user, response)
    db.commit()
    return AuthOut(token=create_token(user.id), user=auth_user_out(user))


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    """Revoke the presented refresh token (if any) and clear the cookie."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        token = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(raw)).first()
        if token is not None and not token.revoked:
            token.revoked = True
            db.commit()
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


@router.post("/password", status_code=204)
def change_password(
    payload: PasswordChangeIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    if not user.password_hash:
        raise api_error(
            403,
            "password_not_set",
            "Account has no password — register first.",
        )
    try:
        _hasher.verify(user.password_hash, payload.current_password)
    except (VerificationError, InvalidHashError) as exc:
        raise api_error(403, "wrong_current_password", "Wrong current password.") from exc
    user.password_hash = _hasher.hash(payload.new_password)
    # A password change is how a user evicts someone holding their session.
    revoke_other_refresh_tokens(db, user.id, request)
    db.commit()


@router.post("/reset", status_code=204)
def reset_password(payload: ResetIn, db: Session = Depends(get_db)) -> None:
    """Consume a one-time reset token: set the password and revoke every
    refresh token the user holds (stolen-session containment)."""
    token = db.query(ResetToken).filter(ResetToken.token_hash == hash_token(payload.token)).first()
    if token is None or token.consumed_at is not None or _as_utc(token.expires_at) <= utcnow():
        raise api_error(
            400,
            "reset_token_invalid",
            "Reset link is invalid, already used, or expired.",
        )
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise api_error(403, "account_suspended", "Account is suspended.")
    token.consumed_at = utcnow()
    user.password_hash = _hasher.hash(payload.new_password)
    revoke_all_refresh_tokens(db, user.id)
    db.commit()


@router.get("/me", response_model=AuthUserOut)
def me(user: User = Depends(require_user)) -> AuthUserOut:
    return auth_user_out(user)


class ProfilePatchIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    affiliation: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None, max_length=2000)
    web_url: str | None = Field(default=None, max_length=1000)


@router.patch("/me", response_model=AuthUserOut)
def patch_me(
    payload: ProfilePatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> AuthUserOut:
    """Individual profile fields (bio + URL etc.). Empty string clears."""
    data = payload.model_dump(exclude_unset=True)
    if "display_name" in data and data["display_name"]:
        user.display_name = data["display_name"].strip()
    if "affiliation" in data:
        user.affiliation = (data["affiliation"] or "").strip() or None
    if "bio" in data:
        user.bio = (data["bio"] or "").strip() or None
    if "web_url" in data:
        url = (data["web_url"] or "").strip()
        if url and not re.match(r"^https?://", url):
            raise api_error(422, "invalid_web_url", "Web URL must start with http:// or https://.")
        user.web_url = url or None
    db.commit()
    return auth_user_out(user)


# ── Iteration 4: email verification + forgot-password ──


class EmailIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class VerifyEmailIn(BaseModel):
    token: str


class ForgotIn(BaseModel):
    handle_or_email: str


@router.post("/email", status_code=204)
def set_email(
    payload: EmailIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    """Set (or change) the account's email and send a verification link.
    Changing the address always re-verifies and, because the address is the
    login identifier and the reset channel, logs every other session out."""
    email = normalise_email(payload.email)
    if not EMAIL_RE.match(email):
        raise api_error(422, "invalid_email", "Invalid email address.")
    owner = db.query(User).filter(func.lower(User.email) == email).first()
    if owner is not None and owner.id != user.id:
        raise api_error(409, "email_taken", "Email address is already used by another account.")
    if user.email != email:
        user.email = email
        user.email_verified = False
        user.email_verified_at = None
        revoke_other_refresh_tokens(db, user.id, request)
    send_verification_email(db, user)
    db.commit()


@router.post("/verify-email", status_code=204)
def verify_email(payload: VerifyEmailIn, db: Session = Depends(get_db)) -> None:
    """Consume a one-time verification token (48 h). Public — the link may be
    opened in a logged-out browser."""
    token = (
        db.query(EmailVerifyToken)
        .filter(EmailVerifyToken.token_hash == hash_token(payload.token))
        .first()
    )
    if token is None or token.consumed_at is not None or _as_utc(token.expires_at) <= utcnow():
        raise api_error(
            400,
            "verify_token_invalid",
            "Verification link is invalid, already used, or expired.",
        )
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise api_error(403, "account_suspended", "Account is suspended.")
    if user.email != token.email:
        # The address changed after this link was minted — a fresh link exists.
        raise api_error(
            400,
            "verify_email_mismatch",
            "Email address changed since the link was sent — request a new one.",
        )
    token.consumed_at = utcnow()
    user.email_verified = True
    user.email_verified_at = utcnow()
    db.commit()


@router.post("/forgot", status_code=204)
def forgot_password(payload: ForgotIn, db: Session = Depends(get_db)) -> None:
    """ALWAYS 204 — account existence is never disclosed (no enumeration).
    A reset link is emailed only when the account has a VERIFIED address;
    the link reuses the ordinary /auth/reset flow."""
    identifier = payload.handle_or_email.strip()
    if not identifier:
        return
    user = db.query(User).filter(func.lower(User.email) == identifier.lower()).first()
    if user is None:
        user = db.query(User).filter(User.handle == normalise_handle(identifier)).first()
    if user is None or not user.is_active or not user.email or not user.email_verified:
        return
    raw = secrets.token_urlsafe(32)
    db.add(
        ResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=utcnow() + FORGOT_RESET_TTL,
        )
    )
    url = email_service.absolute_url(f"/reset?token={raw}")
    note = (
        "Länken gäller i 24 timmar och kan bara användas en gång. "
        "Om du inte begärde detta kan du ignorera det här meddelandet – "
        "lösenordet ändras inte."
    )
    email_service.send(
        db,
        to_addr=user.email,
        subject="Återställ ditt lösenord på Kollepedia",
        body_text=(
            f"Hej {user.display_name}!\n\n"
            f"Återställ ditt lösenord genom att öppna länken:\n\n{url}\n\n{note}"
        ),
        body_html=email_service.render_html(
            heading="Återställ ditt lösenord",
            name=user.display_name,
            intro="Välj ett nytt lösenord genom att trycka på knappen.",
            button_label="Välj nytt lösenord",
            url=url,
            note=note,
        ),
        template="reset_password",
    )
    db.commit()
