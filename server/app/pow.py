"""Self-hosted proof-of-work bot gate for registration (migration 008).

Why PoW instead of a CAPTCHA service: no third-country dependency (GDPR:
nothing leaves the server), no accessibility wall, no vendor. The browser
must find a nonce whose SHA-256 together with a server-signed salt has
POW_BITS leading zero bits — milliseconds of human-imperceptible work per
registration, but real cost at bot scale. Modelled on ALTCHA's flow
(challenge → widget solves → verified server-side) without the dependency.

Challenge integrity is HMAC-signed with the JWT secret, carries issue and
expiry timestamps (a form submitted faster than MIN_FILL_SECONDS after the
challenge was issued is flagged for review — humans read forms), and each
salt is single-use via the used_nonces table.
"""

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .deps import JWT_SECRET
from .models import UsedNonce, utcnow

CHALLENGE_TTL = timedelta(minutes=15)


def pow_bits() -> int:
    """Leading zero bits required. 15 ≈ 32k hashes ≈ well under a second in a
    browser; tests set POW_BITS=8 to exercise the full path cheaply."""
    return int(os.getenv("POW_BITS", "15"))


def min_fill_seconds() -> float:
    """Forms submitted faster than this after the challenge was issued are
    flagged for review (humans read forms). Tests set it to 0."""
    return float(os.getenv("POW_MIN_FILL_SECONDS", "3"))


def _sign(salt: str, issued: int, expires: int, bits: int) -> str:
    payload = f"{salt}|{issued}|{expires}|{bits}"
    return hmac.new(JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


@dataclass
class Challenge:
    salt: str
    issued: int
    expires: int
    bits: int
    signature: str


def create_challenge() -> Challenge:
    now = int(utcnow().timestamp())
    expires = int((utcnow() + CHALLENGE_TTL).timestamp())
    salt = secrets.token_hex(16)
    bits = pow_bits()
    return Challenge(
        salt=salt,
        issued=now,
        expires=expires,
        bits=bits,
        signature=_sign(salt, now, expires, bits),
    )


def _leading_zero_bits(digest: bytes) -> int:
    count = 0
    for byte in digest:
        if byte == 0:
            count += 8
            continue
        count += 8 - byte.bit_length()
        break
    return count


@dataclass
class PowResult:
    ok: bool
    error: str | None = None
    # True when the form came back suspiciously fast after the challenge was
    # issued — not a rejection on its own, but a review signal.
    too_fast: bool = False


def verify_solution(
    db: Session,
    *,
    salt: str,
    issued: int,
    expires: int,
    bits: int,
    signature: str,
    number: int,
) -> PowResult:
    """Full server-side verification: signature, expiry, single-use, work."""
    if not hmac.compare_digest(signature, _sign(salt, issued, expires, bits)):
        return PowResult(ok=False, error="Ogiltig utmaning – ladda om sidan.")
    now = utcnow()
    if now.timestamp() > expires:
        return PowResult(ok=False, error="Utmaningen har gått ut – försök igen.")
    if bits < pow_bits():
        return PowResult(ok=False, error="Ogiltig utmaning – ladda om sidan.")
    digest = hashlib.sha256(f"{salt}{number}".encode()).digest()
    if _leading_zero_bits(digest) < bits:
        return PowResult(ok=False, error="Ogiltig lösning – försök igen.")

    # Single-use: claiming the salt twice hits the primary key.
    db.query(UsedNonce).filter(UsedNonce.expires_at < now).delete()
    try:
        db.add(UsedNonce(nonce=salt, expires_at=datetime.fromtimestamp(expires, tz=UTC)))
        db.flush()
    except IntegrityError:
        db.rollback()
        return PowResult(ok=False, error="Utmaningen är redan använd – försök igen.")

    return PowResult(ok=True, too_fast=(now.timestamp() - issued) < min_fill_seconds())


def solve(salt: str, bits: int, limit: int = 5_000_000) -> int:
    """Reference solver (tests + the acceptance walkthrough); the browser has
    an equivalent in TypeScript."""
    for number in range(limit):
        digest = hashlib.sha256(f"{salt}{number}".encode()).digest()
        if _leading_zero_bits(digest) >= bits:
            return number
    raise RuntimeError("no solution found within limit")
