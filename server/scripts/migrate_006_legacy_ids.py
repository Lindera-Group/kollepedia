"""Builds the legacy_ids alias table: prototype term_id → NG concept id.

Imported definitions contain [Label](#<old-term-id>) links. NG concepts got
fresh uuids at migration, so those anchors 404'd. Versions are immutable —
instead of rewriting them, _get_concept resolves legacy ids through this map.
Match: (collection slug, canonical_form) exact, then case-insensitive.
Idempotent; source DB opened read-only.
"""

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal, engine
from app.models import Base, Branch, Collection, Concept, LegacyId, Version

# PROTOTYPE_DB is the v1 database (run_migrations.py passes it through). No
# default: a path that exists on one laptop is not a default, it is a secret
# about that laptop — and a wrong guess must fail loudly, not open nothing.
OLD_DB = os.environ.get("PROTOTYPE_DB", "")


def main() -> None:
    if not OLD_DB:
        raise SystemExit("PROTOTYPE_DB must point at the v1 prototype database (no default).")
    Base.metadata.create_all(bind=engine, tables=[LegacyId.__table__])
    db = SessionLocal()

    old = sqlite3.connect(f"file:{OLD_DB}?mode=ro", uri=True)
    old_terms = old.execute(
        """SELECT t.term_id, t.canonical_form, c.slug
           FROM terms t JOIN collections c ON c.collection_id = t.collection_id"""
    ).fetchall()

    # NG lookup: (collection slug, head canonical_form) → concept id.
    rows = (
        db.query(Collection.slug, Version.canonical_form, Concept.id)
        .join(Concept, Concept.collection_id == Collection.id)
        .join(Branch, (Branch.concept_id == Concept.id) & (Branch.name == "main"))
        .join(Version, Version.id == Branch.head_version_id)
        .all()
    )
    exact: dict[tuple[str, str], str] = {}
    folded: dict[tuple[str, str], str] = {}
    for slug, form, cid in rows:
        exact.setdefault((slug, form), cid)
        folded.setdefault((slug, form.lower()), cid)

    existing = {lid for (lid,) in db.query(LegacyId.legacy_id).all()}
    created = matched = unmatched = 0
    for term_id, form, slug in old_terms:
        target = exact.get((slug, form)) or folded.get((slug, form.lower()))
        if target is None:
            unmatched += 1
            continue
        matched += 1
        if term_id in existing or term_id == target:
            continue
        db.add(LegacyId(legacy_id=term_id, concept_id=target))
        created += 1
    db.commit()
    print(
        f"old terms: {len(old_terms)}, matched: {matched}, "
        f"aliases created: {created}, unmatched: {unmatched}"
    )


if __name__ == "__main__":
    main()
