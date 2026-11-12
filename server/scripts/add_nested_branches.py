"""Add nested demo branches to the tidsmaskinen acceptance concept
("realtidsinformation") so the timeline shows branch-of-branch lanes.

Creates (idempotently — each branch is skipped if its name already exists):

1. 'regional-nord' — a NESTED branch forking from the FIRST version of the
   existing 'regional-tolkning' branch (2024-03). Two versions (2025-02,
   2025-09) by Paulina Granvik (Övre Norrlands trafikmyndighet) that pull
   the regional reading further toward glesbygdsperspektivet.
2. 'internationell-jamforelse' — a branch from main's 2017 version. That
   version is NOT a branch head, which is fine: mode=branch works from any
   version on the concept (the branched_from edge chains back to main).
   One version (2019-05) by Konrad Ahlberg (ITF).

Result on the timeline: main + 2 trunk-level lanes + 1 nested lane
(three layers of visual complexity).

Usage:
    uv run python scripts/backup_database.py      # ALWAYS back up first
    uv run python scripts/add_nested_branches.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session  # noqa: E402

from app import graph  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Branch, Collection, Concept, User, Version  # noqa: E402

CONCEPT_ID = "2b957999-3b91-48d9-bdb6-c61fc66f9214"

DEMO_USERS: dict[str, tuple[str, str]] = {
    "paulina-granvik": ("Paulina Granvik", "Övre Norrlands trafikmyndighet"),
    "konrad-ahlberg": ("Konrad Ahlberg", "ITF – Internationella transitforumet"),
}

NORD_V1 = (
    "Trafikinformation som beskriver det faktiska trafikläget utifrån fordonens "
    "positioneringsdata. I glesbygd med få avgångar per dygn är den centrala "
    "uppgiften att bekräfta att turen faktiskt är på väg — en inställd länsbuss "
    "kan innebära flera timmars väntan till nästa avgång. Realtidsinformationen "
    "avser därför i första hand trafikbekräftelse och inställda turer, förmedlad "
    "via sms-tjänster och digitala kanaler, snarare än rullande minutprognoser. "
    "Där mobiltäckning saknas längs linjen redovisas i stället fordonets senast "
    "kända position."
)

NORD_V2 = NORD_V1 + (
    " För anropsstyrd anslutningstrafik omfattar realtidsinformationen även "
    "bekräftelse av beställd tur och beräknad hämtningstid. Vintertid "
    "kompletteras informationen med uppgifter om vägläge och väderrelaterade "
    "störningar på det inre vägnätet."
)

INTL_V1 = (
    "Realtidsinformation (eng. real-time passenger information, RTPI) avser "
    "trafikinformation som uppdateras kontinuerligt utifrån fordonens faktiska "
    "position och förmedlas till resenärerna före och under resan. I "
    "internationell praxis omfattar begreppet predicted arrival/departure times "
    "vid hållplats, service alerts vid störningar samt vehicle occupancy där "
    "sådana data finns. Utbytet sker i växande grad via standardiserade "
    "gränssnitt som SIRI (Service Interface for Real-time Information) och GTFS "
    "Realtime, vilket gör reseinformationen jämförbar över operatörs- och "
    "landsgränser."
)


def get_or_create_user(db: Session, handle: str) -> User:
    user = db.query(User).filter(User.handle == handle).first()
    if user is None:
        display, affiliation = DEMO_USERS[handle]
        user = User(handle=handle, display_name=display, affiliation=affiliation)
        db.add(user)
        db.flush()
    return user


def find_concept(db: Session) -> Concept:
    concept = db.get(Concept, CONCEPT_ID)
    if concept is not None:
        return concept
    # Fallback after a showcase rebuild (ids change): acceptance concept A is
    # the tidsmaskinen concept whose main head is "realtidsinformation".
    coll = db.query(Collection).filter(Collection.slug == "tidsmaskinen").first()
    if coll is None:
        raise SystemExit("tidsmaskinen collection not found — run build_showcase.py first")
    row = (
        db.query(Concept)
        .join(Branch, (Branch.concept_id == Concept.id) & (Branch.name == "main"))
        .join(Version, Version.id == Branch.head_version_id)
        .filter(Concept.collection_id == coll.id)
        .filter(Version.canonical_form == "realtidsinformation")
        .first()
    )
    if row is None:
        raise SystemExit("acceptance concept 'realtidsinformation' not found")
    return row


def branch_exists(db: Session, concept: Concept, name: str) -> Branch | None:
    return db.query(Branch).filter(Branch.concept_id == concept.id, Branch.name == name).first()


def main() -> None:
    db = SessionLocal()
    concept = find_concept(db)
    print(f"Concept: {concept.id}")

    created: list[str] = []

    # ── 1. Nested branch: regional-nord from regional-tolkning's v1 ────────
    if branch_exists(db, concept, "regional-nord") is not None:
        print("Branch 'regional-nord' already exists — skipping.")
    else:
        regional = branch_exists(db, concept, "regional-tolkning")
        if regional is None:
            raise SystemExit("branch 'regional-tolkning' not found — run build_showcase.py")
        base = (
            db.query(Version)
            .filter(Version.branch_id == regional.id)
            .order_by(Version.created_at)
            .first()
        )
        assert base is not None, "regional-tolkning has no versions"
        petra = get_or_create_user(db, "paulina-granvik")
        n1 = graph.add_version(
            db,
            concept=concept,
            mode="branch",
            branch_name="regional-nord",
            base_version_id=base.id,
            canonical_form="realtidsinformation",
            definition_md=NORD_V1,
            status="proposed",
            tags=["Passenger Services", "Technology & Data", "Transport Modes"],
            note=(
                "Nordlig underläsart av den regionala tolkningen: i glesbygd är "
                "trafikbekräftelse viktigare än minutprognoser när nästa tur går "
                "först om flera timmar."
            ),
            provenance={"kind": "human"},
            created_by=petra.id,
            created_at=datetime(2025, 2, 10),
        )
        n2 = graph.add_version(
            db,
            concept=concept,
            mode="revise",
            base_version_id=n1.id,
            canonical_form="realtidsinformation",
            definition_md=NORD_V2,
            status="proposed",
            tags=[
                "Demand-Responsive Transport",
                "Passenger Services",
                "Technology & Data",
                "Transport Modes",
            ],
            note=(
                "Tillägg efter samråd med kommunerna: anropsstyrd anslutningstrafik "
                "och vinterväglag ska synas i realtidsinformationen."
            ),
            provenance={"kind": "human"},
            created_by=petra.id,
            created_at=datetime(2025, 9, 15),
        )
        created += [f"regional-nord v1 = {n1.id}", f"regional-nord v2 = {n2.id}"]

    # ── 2. Trunk branch from a NON-head main version (2017) ────────────────
    if branch_exists(db, concept, "internationell-jamforelse") is not None:
        print("Branch 'internationell-jamforelse' already exists — skipping.")
    else:
        main_branch = branch_exists(db, concept, "main")
        assert main_branch is not None
        v2017 = (
            db.query(Version)
            .filter(Version.branch_id == main_branch.id)
            .filter(Version.created_at >= datetime(2017, 1, 1))
            .filter(Version.created_at < datetime(2018, 1, 1))
            .order_by(Version.created_at)
            .first()
        )
        if v2017 is None:
            raise SystemExit("main has no 2017 version — run build_showcase.py")
        thomas = get_or_create_user(db, "konrad-ahlberg")
        i1 = graph.add_version(
            db,
            concept=concept,
            mode="branch",
            branch_name="internationell-jamforelse",
            base_version_id=v2017.id,
            canonical_form="realtidsinformation",
            definition_md=INTL_V1,
            status="proposed",
            tags=["Passenger Services", "Technology & Data"],
            note=(
                "Gren för internationell jämförelse: terminologin speglad mot "
                "ITF:s och EU-standardernas engelska begreppsapparat (RTPI, "
                "SIRI, GTFS Realtime)."
            ),
            provenance={"kind": "human"},
            created_by=thomas.id,
            created_at=datetime(2019, 5, 14),
        )
        created.append(f"internationell-jamforelse v1 = {i1.id}")

    db.commit()
    if created:
        print("Created versions:")
        for line in created:
            print(f"  {line}")
    else:
        print("Nothing to do — both branches already present.")
    db.close()


if __name__ == "__main__":
    main()
