"""Operational tasks run inside the server container (Actions workflow `Ops`).

Kvarnen has no SSH route to the VPS, so the things a super admin would
otherwise do by hand in the database go through this script, invoked by
`.github/workflows/ops.yml` as `docker exec <container> python scripts/ops.py …`.
Every run is a workflow run: who, what and when stay in the Actions log.

Actions:
  report          Organisations, their members and account totals. E-mail
                  addresses are masked (j***@example.org) — the log is the
                  audience, not the inbox.
  provision-user  Create (or complete) an account and attach it to an
                  existing organisation. The account is approved and its
                  e-mail marked verified; its password is an unusable random
                  hash (never NULL — a NULL hash is a claimable author
                  profile), so the printed reset link (7 days) is the only
                  way in. Idempotent: an existing account with the same
                  e-mail only gets the membership/role it lacks, and a NULL
                  hash is replaced.
  reset-link      A fresh reset link for an existing account.

Arguments come from the CLI or from OPS_* environment variables (the
workflow passes them as `docker exec -e`), environment taking precedence.

The reset link is printed to the workflow log, which only repository
collaborators can read. Treat it as the secret it is: hand it to the person,
then delete the run's log (`gh api -X DELETE repos/<owner>/<repo>/actions/runs/<id>/logs`).
A new link invalidates the account's earlier unused ones, links are never
issued for super-admin accounts, and a used link is consumed by the app.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path

from argon2 import PasswordHasher
from sqlalchemy import func, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.models import (  # noqa: E402
    ORG_ROLES,
    Organisation,
    OrgMembership,
    ResetToken,
    User,
    utcnow,
)
from app.routers.auth import (  # noqa: E402
    EMAIL_RE,
    hash_token,
    normalise_handle,
    slugify_handle,
)

PROVISION_RESET_TTL = timedelta(days=7)
_hasher = PasswordHasher()


def unusable_password_hash() -> str:
    """An argon2 hash of a random secret nobody keeps. The account is then
    neither claimable through /activate (claiming needs password_hash IS NULL)
    nor usable for login; the only way in is a reset link."""
    return _hasher.hash(secrets.token_urlsafe(32))


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "–"
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}"


def report(db: Session) -> str:
    lines: list[str] = []
    total = db.scalar(select(func.count()).select_from(User)) or 0
    supers = sorted(db.scalars(select(User.handle).where(User.is_super_admin)).all())
    pending = (
        db.scalar(select(func.count()).select_from(User).where(User.review_status == "pending"))
        or 0
    )
    without_pw = (
        db.scalar(select(func.count()).select_from(User).where(User.password_hash.is_(None))) or 0
    )
    lines.append(
        f"Konton: {total} (superadmin: {', '.join(supers) or '–'}; "
        f"väntar på granskning: {pending}; utan lösenord: {without_pw})"
    )
    orgs = db.scalars(select(Organisation).order_by(Organisation.name)).all()
    lines.append(f"Organisationer: {len(orgs)}")
    for org in orgs:
        owner = db.get(User, org.owner_user_id) if org.owner_user_id else None
        flags = "godkänd" if org.is_approved else "EJ GODKÄND"
        if org.is_suspended:
            flags += ", avstängd"
        lines.append(
            f"  {org.slug} | {org.name} | {org.org_type or '–'} | {flags} | "
            f"ägare: {owner.handle if owner else '–'}"
        )
        rows = db.execute(
            select(OrgMembership, User)
            .join(User, User.id == OrgMembership.user_id)
            .where(OrgMembership.organisation_id == org.id)
            .order_by(User.handle)
        ).all()
        if not rows:
            lines.append("      (inga medlemmar)")
        for membership, user in rows:
            lines.append(
                f"      {user.handle} | {user.display_name} | {membership.role}/{membership.kind}"
                f" | {mask_email(user.email)} | lösenord: {'ja' if user.password_hash else 'nej'}"
                f" | verifierad: {'ja' if user.email_verified else 'nej'}"
            )
    return "\n".join(lines)


def reset_link(db: Session, handle: str, origin: str = "") -> str:
    user = db.scalar(select(User).where(User.handle == normalise_handle(handle)))
    if user is None:
        raise SystemExit(f"Kontot {handle!r} finns inte.")
    if not user.is_active:
        raise SystemExit(f"Kontot {handle!r} är avstängt — aktivera det först.")
    if user.is_super_admin:
        raise SystemExit("Inga återställningslänkar för superadmin-konton via ops — använd appen.")
    # One live link per account: earlier unused tokens die when a new one is issued.
    now = utcnow()
    for stale in db.scalars(
        select(ResetToken).where(ResetToken.user_id == user.id, ResetToken.consumed_at.is_(None))
    ):
        stale.consumed_at = now
    raw = secrets.token_urlsafe(32)
    db.add(
        ResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=now + PROVISION_RESET_TTL,
        )
    )
    db.commit()
    return f"{origin.rstrip('/')}/reset?token={raw}"


def provision_user(
    db: Session,
    *,
    display_name: str,
    email: str,
    org_slug: str,
    role: str = "editor",
    handle: str = "",
    owner: bool = False,
    origin: str = "",
) -> dict[str, object]:
    if role not in ORG_ROLES:
        raise SystemExit(f"Ogiltig roll {role!r}; välj bland {', '.join(ORG_ROLES)}.")
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise SystemExit(f"Ogiltig e-postadress {email!r}.")
    display_name = display_name.strip()
    if len(display_name) < 2:
        raise SystemExit("Visningsnamnet behöver minst två tecken.")
    org = db.scalar(select(Organisation).where(Organisation.slug == org_slug.strip().lower()))
    if org is None:
        raise SystemExit(f"Organisationen {org_slug!r} finns inte — skapa den i appen först.")

    wanted_handle = normalise_handle(handle) if handle.strip() else slugify_handle(display_name)
    created = False
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = db.scalar(select(User).where(User.handle == wanted_handle))
        if user is not None and user.email and user.email != email:
            raise SystemExit(
                f"Användarnamnet {wanted_handle!r} tillhör ett konto med annan e-post."
            )
        if user is None:
            user = User(
                handle=wanted_handle,
                display_name=display_name,
                email=email,
                email_verified=True,
                email_verified_at=utcnow(),
                is_active=True,
                review_status="approved",
                password_hash=unusable_password_hash(),
            )
            db.add(user)
            db.flush()
            created = True
        else:
            # An unclaimed author profile with this handle: attach the e-mail.
            user.email = email
            user.email_verified = True
            user.email_verified_at = utcnow()
            user.review_status = "approved"
    if user.password_hash is None:
        # Never leave a provisioned account claimable through /activate.
        user.password_hash = unusable_password_hash()
    if not user.affiliation:
        user.affiliation = org.name

    membership = db.scalar(
        select(OrgMembership).where(
            OrgMembership.user_id == user.id, OrgMembership.organisation_id == org.id
        )
    )
    membership_created = membership is None
    if membership is None:
        db.add(
            OrgMembership(
                user_id=user.id,
                organisation_id=org.id,
                role=role,
                kind="member",
                is_public=True,
            )
        )
    elif membership.role != role:
        membership.role = role
    if owner:
        org.owner_user_id = user.id
    db.commit()

    return {
        "handle": user.handle,
        "display_name": user.display_name,
        "email": mask_email(user.email),
        "created": created,
        "membership_created": membership_created,
        "role": role,
        "org": org.slug,
        "owner": owner,
        "reset_link": reset_link(db, user.handle, origin),
    }


def _arg(args: argparse.Namespace, name: str, default: str = "") -> str:
    return os.getenv(f"OPS_{name.upper()}", "") or (getattr(args, name, None) or default)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("report")
    p = sub.add_parser("provision-user")
    p.add_argument("--display-name", dest="display_name", default="")
    p.add_argument("--email", default="")
    p.add_argument("--org", default="")
    p.add_argument("--role", default="")
    p.add_argument("--handle", default="")
    p.add_argument("--owner", default="")
    p.add_argument("--origin", default="")
    r = sub.add_parser("reset-link")
    r.add_argument("--handle", default="")
    r.add_argument("--origin", default="")
    args = ap.parse_args(argv)

    from app.db import SessionLocal

    with SessionLocal() as db:
        if args.action == "report":
            print(report(db))
        elif args.action == "provision-user":
            result = provision_user(
                db,
                display_name=_arg(args, "display_name"),
                email=_arg(args, "email"),
                org_slug=_arg(args, "org"),
                role=_arg(args, "role", "editor"),
                handle=_arg(args, "handle"),
                owner=_arg(args, "owner").lower() in {"1", "true", "yes", "ja"},
                origin=_arg(args, "origin"),
            )
            verb = "skapat" if result["created"] else "fanns redan"
            print(
                f"Konto {result['handle']} ({result['display_name']}, {result['email']}): {verb}; "
                f"medlem i {result['org']} som {result['role']}"
                + (" (nytt medlemskap)" if result["membership_created"] else "")
                + (", satt som ägare" if result["owner"] else "")
            )
            print(f"Återställningslänk (7 dagar): {result['reset_link']}")
        elif args.action == "reset-link":
            link = reset_link(db, _arg(args, "handle"), _arg(args, "origin"))
            print(f"Återställningslänk (7 dagar): {link}")


if __name__ == "__main__":
    main()
