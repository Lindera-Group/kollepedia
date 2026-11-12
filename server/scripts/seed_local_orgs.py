"""Seed the LOCAL dev database with the test organisations and memberships
that mirror old Kollepedia (plan: NG_ORGANISATIONER_OCH_MEDLEMSKAP, Fas 8).

Idempotent — look up before insert, safe to re-run. Run with the server
stopped, AFTER migration 014 and a fresh backup:

    uv run python scripts/backup_database.py
    uv run python scripts/migrate_014_memberships.py
    SEED_PASSWORD=... uv run python scripts/seed_local_orgs.py

What it does:
1. Superadmin swap: SEED_SUPERADMIN_EMAIL (default superadmin@example.org)
   → super admin (no memberships, owns nothing); SEED_MEMBER_EMAIL (default
   medlem@example.org) → regular multi-org member. Both accounts must already
   exist in the local database.
2. Organisations (approved, typed): K2 (academy), Samtrafiken (commercial),
   Svensk Kollektivtrafik (industry_association, NEW), SUTI
   (industry_association, NEW), Linderå Group AB (commercial, NEW).
3. Owner accounts on example.org addresses (k2-admin@example.org, …) with
   the shared dev password SEED_PASSWORD (default 'lokal-utveckling-byt-mig')
   — each owner + admin + member of their org. Nothing here is a real
   mailbox: the seed is for a laptop, never for an instance that sends mail.
4. The member account: owner/admin of Linderå Group AB, admin member of
   SUTI, guest editor of K2 and Svensk Kollektivtrafik.
5. The nomenklatur import (slug 'trdsfsdfdsg') becomes Svensk
   Kollektivtrafik's ORG-PRIVATE collection 'nomenklatur-2024' (beslut
   2026-07-12 — arbetsmaterial, inte publikt); the
   'import-smoke-test' collection becomes a private sandbox. The four
   historical public collections + tidsmaskinen stay org-less system
   collections (mirrors v1).
6. NULL-org endorsements are linked by exact body match (migration 010's
   rule); unmatched bodies are listed and stay super-admin-managed history.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from argon2 import PasswordHasher  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Collection,
    Endorsement,
    Organisation,
    OrgMembership,
    User,
    utcnow,
)

SEED_PASSWORD = os.getenv("SEED_PASSWORD", "lokal-utveckling-byt-mig")
# The two pre-existing local accounts the seed rearranges (step 1).
SUPERADMIN_EMAIL = os.getenv("SEED_SUPERADMIN_EMAIL", "superadmin@example.org")
MEMBER_EMAIL = os.getenv("SEED_MEMBER_EMAIL", "medlem@example.org")

ORGS = [
    # (slug, name, org_type) — K2/Samtrafiken exist already (created member-less
    # by earlier work); the seed types and approves them too.
    ("k2", "K2 – Nationellt kunskapscentrum för kollektivtrafik", "academy"),
    ("samtrafiken", "Samtrafiken i Sverige AB", "commercial"),
    ("svensk-kollektivtrafik", "Svensk Kollektivtrafik", "industry_association"),
    ("suti", "SUTI", "industry_association"),
    ("lindera-group", "Linderå Group AB", "commercial"),
]

# Owner accounts on reserved example.org addresses (RFC 2606 — never
# deliverable). Linderå Group's owner is the MEMBER_EMAIL account.
OWNER_ACCOUNTS = {
    "k2": ("k2-admin", "k2-admin@example.org", "K2 Admin"),
    "samtrafiken": ("samtrafiken-admin", "samtrafiken-admin@example.org", "Samtrafiken Admin"),
    "svensk-kollektivtrafik": (
        "svk-admin",
        "svk-admin@example.org",
        "Svensk Kollektivtrafik Admin",
    ),
    "suti": ("suti-admin", "suti-admin@example.org", "SUTI Admin"),
}

# The member account's memberships: (org_slug, role, kind, owner?)
LINDERA_MEMBERSHIPS = [
    ("lindera-group", "admin", "member", True),
    ("suti", "admin", "member", False),
    ("k2", "editor", "guest", False),
    ("svensk-kollektivtrafik", "editor", "guest", False),
]

NOMENKLATUR_OLD_SLUG = "trdsfsdfdsg"
NOMENKLATUR = {
    "slug": "nomenklatur-2024",
    "name": "Nomenklatur (arbetsmaterial)",
    "year": 2024,
}


def ensure_membership(db, user, org, *, role, kind):
    membership = (
        db.query(OrgMembership)
        .filter(
            OrgMembership.user_id == user.id,
            OrgMembership.organisation_id == org.id,
            OrgMembership.ended_at.is_(None),
        )
        .first()
    )
    if membership is None:
        db.add(OrgMembership(user_id=user.id, organisation_id=org.id, role=role, kind=kind))
        print(f"  + medlemskap: {user.handle} → {org.slug} ({role}/{kind})")
    elif membership.role != role or membership.kind != kind:
        membership.role = role
        membership.kind = kind
        print(f"  ~ medlemskap uppdaterat: {user.handle} → {org.slug} ({role}/{kind})")


def main() -> None:
    db = SessionLocal()
    hasher = PasswordHasher()
    try:
        # ── 1. Superadmin swap ──
        martin = db.query(User).filter(User.email == SUPERADMIN_EMAIL).first()
        lindera = db.query(User).filter(User.email == MEMBER_EMAIL).first()
        if martin is None or lindera is None:
            raise SystemExit(
                f"Förväntade användarna {SUPERADMIN_EMAIL} och {MEMBER_EMAIL} finns inte i "
                "databasen — avbryter (SEED_SUPERADMIN_EMAIL / SEED_MEMBER_EMAIL styr)."
            )
        ended = 0
        for m in martin.memberships:
            if m.ended_at is None:
                m.ended_at = utcnow()
                ended += 1
        owned = db.query(Organisation).filter(Organisation.owner_user_id == martin.id).first()
        if owned is not None:
            owned.owner_user_id = None
            print(f"  ~ {martin.handle} fråntagen ägarskapet av {owned.slug} (G1)")
        if not martin.is_super_admin:
            martin.is_super_admin = True
            print(f"  ~ {martin.handle} ({martin.email}) är nu superadministratör")
        if ended:
            print(f"  ~ {ended} medlemskap avslutade för superadministratören (G1)")
        if lindera.is_super_admin:
            lindera.is_super_admin = False
            print(f"  ~ {lindera.handle} ({lindera.email}) är inte längre superadministratör")

        # ── 2. Organisationer ──
        orgs: dict[str, Organisation] = {}
        for slug, name, org_type in ORGS:
            org = db.query(Organisation).filter(Organisation.slug == slug).first()
            if org is None:
                org = Organisation(slug=slug, name=name, created_by=martin.id)
                db.add(org)
                db.flush()
                print(f"  + organisation: {name} ({slug})")
            org.name = name
            org.org_type = org_type
            org.is_approved = True
            orgs[slug] = org

        # ── 3. Ägarkonton (plus-adresser) ──
        for slug, (handle, email, display_name) in OWNER_ACCOUNTS.items():
            org = orgs[slug]
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = db.query(User).filter(User.handle == handle).first()
            if user is None:
                user = User(
                    handle=handle,
                    display_name=display_name,
                    email=email,
                    email_verified=True,
                    password_hash=hasher.hash(SEED_PASSWORD),
                )
                db.add(user)
                db.flush()
                print(f"  + användare: {handle} ({email})")
            elif user.password_hash is None:
                user.password_hash = hasher.hash(SEED_PASSWORD)
            ensure_membership(db, user, org, role="admin", kind="member")
            if org.owner_user_id is None:
                org.owner_user_id = user.id
                print(f"  ~ ägare: {org.slug} → {user.handle}")

        # ── 4. linderas medlemskap ──
        for slug, role, kind, is_owner in LINDERA_MEMBERSHIPS:
            org = orgs[slug]
            ensure_membership(db, lindera, org, role=role, kind=kind)
            if is_owner and org.owner_user_id != lindera.id:
                org.owner_user_id = lindera.id
                print(f"  ~ ägare: {org.slug} → {lindera.handle}")

        # ── 5. Samlingar ──
        svk = orgs["svensk-kollektivtrafik"]
        nomenklatur = (
            db.query(Collection).filter(Collection.slug == NOMENKLATUR["slug"]).first()
            or db.query(Collection).filter(Collection.slug == NOMENKLATUR_OLD_SLUG).first()
        )
        if nomenklatur is None:
            print("  ! nomenklatur-samlingen hittades inte — hoppar över")
        else:
            nomenklatur.slug = NOMENKLATUR["slug"]
            nomenklatur.name = NOMENKLATUR["name"]
            nomenklatur.year = NOMENKLATUR["year"]
            nomenklatur.organisation_id = svk.id
            # Arbetsmaterial — organisationsintern, inte publik (2026-07-12).
            nomenklatur.visibility = "org_private"
            nomenklatur.edit_policy = "org"
            print(
                f"  ~ samling: {NOMENKLATUR['slug']} → Svensk Kollektivtrafik "
                "(org_private, edit_policy=org)"
            )
        smoke = db.query(Collection).filter(Collection.slug == "import-smoke-test").first()
        if smoke is not None and smoke.visibility != "private":
            smoke.visibility = "private"
            print("  ~ samling: import-smoke-test → privat sandlåda")

        # ── 6. Endorsement-länkning (010-regeln: exakt body-match) ──
        # Migration 013:s partiella unika index tillåter EN aktiv stämpel per
        # org och begrepp — vid kollision behåller vi den senaste och
        # auto-återkallar äldre (flaggan flyttar, posten raderas aldrig).
        unlinked = (
            db.query(Endorsement)
            .filter(Endorsement.organisation_id.is_(None))
            .order_by(Endorsement.created_at.asc())
            .all()
        )
        # Case-insensitive on name/slug — 'Samtrafiken' ska träffa sluggen
        # 'samtrafiken' trots att org-namnet är 'Samtrafiken i Sverige AB'.
        by_key = {org.name.lower(): org for org in orgs.values()}
        by_key.update({org.slug.lower(): org for org in orgs.values()})
        unmatched: set[str] = set()
        linked = 0
        active_seen: dict[tuple[str, str], Endorsement] = {}
        for endorsement in unlinked:
            org = by_key.get(endorsement.body.strip().lower())
            if org is None:
                unmatched.add(endorsement.body)
                continue
            endorsement.organisation_id = org.id
            if endorsement.concept_id is None and endorsement.version is not None:
                endorsement.concept_id = endorsement.version.concept_id
            if endorsement.withdrawn_at is None and endorsement.concept_id:
                key = (org.id, endorsement.concept_id)
                existing = active_seen.get(key) or (
                    db.query(Endorsement)
                    .filter(
                        Endorsement.organisation_id == org.id,
                        Endorsement.concept_id == endorsement.concept_id,
                        Endorsement.withdrawn_at.is_(None),
                        Endorsement.id != endorsement.id,
                    )
                    .first()
                )
                if existing is not None:
                    existing.withdrawn_at = utcnow()
                    existing.withdrawal_note = (
                        "Ersatt av nytt intyg för en annan version av begreppet."
                    )
                active_seen[key] = endorsement
            linked += 1
        if linked:
            print(f"  ~ {linked} historiska fastställanden länkade via body-match")
        if unmatched:
            print("  ! omatchade endorsement-bodies (förblir superadmin-hanterad historik):")
            for body in sorted(unmatched):
                print(f"      - {body!r}")

        db.commit()
        print("Klart.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
