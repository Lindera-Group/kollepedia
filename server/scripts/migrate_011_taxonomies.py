"""Migration 011 — seed the global category taxonomy.

Tables (taxonomies, taxonomy_values, concept_taxonomy_values) are created by
Base.metadata.create_all on app startup; this script seeds the GLOBAL
'kategorier' taxonomy with the 14 proven v1 categories. Idempotent — existing
taxonomy/values are left untouched.

The global vocabulary is deliberately MUTABLE: Kollepedia's super admins
curate it over time to keep global search simple (categories are a search
filter alongside parts and tags).

Run:  uv run python scripts/migrate_011_taxonomies.py [path-to-db]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GLOBAL_CATEGORIES = [
    "Passenger Services",
    "Fares & Pricing",
    "Network & Routes",
    "Scheduling & Timetables",
    "Operations",
    "Management & Statistics",
    "Technology & Data",
    "Environment",
    "Safety & Security",
    "Transport Modes",
    "Urban Mobility",
    "Demand-Responsive Transport",
    "Railway Terms",
    "Governance & Policy",
]

DESCRIPTION = (
    "Globala kategorier — den samlingsövergripande sökaxeln. Kurateras av "
    "Kollepedias superadministratörer och kan ändras över tid för att "
    "förenkla den globala sökningen. Minst 1 per begrepp rekommenderas, "
    "max 5 rekommenderas."
)


def migrate(db_path: Path) -> dict[str, int]:
    import os

    os.environ.setdefault("KOLLEPEDIA_NG_DB", str(db_path))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models import Base, Taxonomy, TaxonomyValue

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    counts = {"taxonomies_created": 0, "values_created": 0}
    with Session(engine) as db:
        tax = (
            db.query(Taxonomy)
            .filter(Taxonomy.scope == "global", Taxonomy.slug == "kategorier")
            .first()
        )
        if tax is None:
            tax = Taxonomy(
                slug="kategorier",
                name="Kategorier",
                description=DESCRIPTION,
                scope="global",
                collection_id=None,
                min_per_concept=1,
                max_per_concept=None,
            )
            db.add(tax)
            db.flush()
            counts["taxonomies_created"] = 1
            print("  + global taxonomy 'kategorier' created")
        # After 012 the seeded values carry the English name in name_en (name is
        # Swedish), so an idempotent re-run must recognise both forms.
        existing = {v.name for v in tax.values} | {v.name_en for v in tax.values if v.name_en}
        for position, name in enumerate(GLOBAL_CATEGORIES):
            if name in existing:
                continue
            db.add(TaxonomyValue(taxonomy_id=tax.id, name=name, position=position))
            counts["values_created"] += 1
        db.commit()
    if counts["values_created"]:
        print(f"  + {counts['values_created']} category value(s) seeded")
    return counts


if __name__ == "__main__":
    default = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    print(f"Migrating {db} …")
    print(f"Done: {migrate(db)}")
