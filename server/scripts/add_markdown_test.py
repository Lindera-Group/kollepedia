"""Adds 'markdownprov' to the tidsmaskinen collection: a Time Machine test
where transitions 1→2 and 2→3 change ONLY formatting (bold/italic, then a
cross-reference) while the prose is untouched; 3→4 mixes text + a markdown
link. Idempotent."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph
from app.db import SessionLocal
from app.models import Collection, Concept, User, Version


def get_user(db, handle):
    return db.query(User).filter(User.handle == handle).first()


def main() -> None:
    db = SessionLocal()
    coll = db.query(Collection).filter(Collection.slug == "tidsmaskinen").one()
    exists = (
        db.query(Version)
        .join(Concept, Concept.id == Version.concept_id)
        .filter(Concept.collection_id == coll.id, Version.canonical_form == "markdownprov")
        .first()
    )
    if exists:
        print("markdownprov already exists — skipping")
        return

    anna = get_user(db, "agnes-lovdal")
    erik = get_user(db, "elis-storback")
    maria = get_user(db, "miriam-hook")
    sara = get_user(db, "signe-akerlind")

    base = (
        "En hållplats är en i förväg bestämd plats där resenärer kliver "
        "på och av kollektivtrafikens fordon. Se även bytespunkt för "
        "större knutpunkter."
    )
    concept, v1, _ = graph.create_concept(
        db,
        collection_id=coll.id,
        canonical_form="markdownprov",
        definition_md=base,
        status="draft",
        tags=["Passenger Services"],
        note="Ursprunglig oformaterad text.",
        created_by=anna.id if anna else None,
        created_at=datetime(2019, 4, 10),
    )
    v2 = graph.add_version(
        db,
        concept=concept,
        mode="revise",
        base_version_id=v1.id,
        canonical_form="markdownprov",
        definition_md=(
            "En **hållplats** är en i förväg bestämd plats där resenärer kliver "
            "*på och av* kollektivtrafikens fordon. Se även bytespunkt för "
            "större knutpunkter."
        ),
        status="proposed",
        tags=["Passenger Services"],
        note="Endast formatering: fetstil på termen och kursiv nyans — ingen text ändrad.",
        created_by=erik.id if erik else None,
        created_at=datetime(2021, 9, 2),
    )
    v3 = graph.add_version(
        db,
        concept=concept,
        mode="revise",
        base_version_id=v2.id,
        canonical_form="markdownprov",
        definition_md=(
            "En **hållplats** är en i förväg bestämd plats där resenärer kliver "
            "*på och av* kollektivtrafikens fordon. Se även [[bytespunkt]] för "
            "större knutpunkter."
        ),
        status="proposed",
        tags=["Passenger Services"],
        note="Endast formatering: korsreferensen länkad — texten oförändrad.",
        created_by=maria.id if maria else None,
        created_at=datetime(2023, 5, 20),
    )
    graph.add_version(
        db,
        concept=concept,
        mode="revise",
        base_version_id=v3.id,
        canonical_form="markdownprov",
        definition_md=(
            "En **hållplats** är en i förväg bestämd plats där resenärer stiger "
            "*på och av* kollektivtrafikens fordon. Se även [[bytespunkt]] för "
            "större knutpunkter, samt definitionen i [EN 12896]"
            "(https://transmodel-cen.eu)."
        ),
        status="proposed",
        tags=["Passenger Services", "Network & Routes"],
        note="Text + formatering: 'kliver' → 'stiger' och extern länk till standarden.",
        created_by=sara.id if sara else None,
        created_at=datetime(2025, 8, 14),
    )
    db.commit()
    print(f"markdownprov created: {concept.id}")


if __name__ == "__main__":
    main()
