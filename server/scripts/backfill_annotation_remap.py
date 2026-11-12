"""One-off backfill (plan NG_ATTRIBUTION_OCH_FELHANTERING, paket A).

Carries section/author annotations onto child versions that were created
BEFORE remap-on-write shipped in app/graph.py. Walks version edges in
child-creation order; for every child that (a) has a same-lineage parent
(revised/branched/synthesized/promoted — never translated_from) carrying
section/author annotations and (b) has none itself, it runs the exact same
remap as the live write path.

Dry-run by default — pass --apply to write. Take a database backup first
(scripts-level policy):  cp data/kollepedia.db data/backups/…

Usage:
    uv run python scripts/backfill_annotation_remap.py [--apply]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.annotations import REMAPPED_TYPES, remap_annotations  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Annotation, Version, VersionEdge  # noqa: E402

SAME_LINEAGE = ("revised_from", "branched_from", "synthesized_from", "promoted_from")


def main() -> None:
    apply = "--apply" in sys.argv
    db = SessionLocal()
    try:
        carried_total = 0
        children_touched = 0
        edges = (
            db.query(VersionEdge)
            .filter(VersionEdge.edge_type.in_(SAME_LINEAGE), VersionEdge.ordinal == 0)
            .join(Version, Version.id == VersionEdge.child_id)
            .order_by(Version.created_at.asc())
            .all()
        )
        for edge in edges:
            child = db.get(Version, edge.child_id)
            parent = db.get(Version, edge.parent_id)
            if child is None or parent is None:
                continue
            has_own = (
                db.query(Annotation.id)
                .filter(
                    Annotation.version_id == child.id,
                    Annotation.attr_type.in_(REMAPPED_TYPES),
                )
                .first()
                is not None
            )
            if has_own:
                continue
            carried = remap_annotations(db, parent=parent, child=child)
            if carried:
                children_touched += 1
                carried_total += carried
                print(f"  {child.id}: {carried} annotation(s) from {parent.id}")
        if apply:
            db.commit()
            print(f"APPLIED: {carried_total} annotations onto {children_touched} versions.")
        else:
            db.rollback()
            print(
                f"DRY RUN: would carry {carried_total} annotations onto "
                f"{children_touched} versions. Re-run with --apply."
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
