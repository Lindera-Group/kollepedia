"""Migration 019 — alias the prototype id behind the dead "fordonspass" links.

Sixteen definitions in Kollektivtrafikordboken link to
[fordonspass](#bfdc1642-…), a prototype term id that migrate_006 found no
concept for, so the links 404. Every one of them means the vehicle block:
the work of a vehicle between two stays at a parking point. That entry is
spelled "Fordonpass" in the glossary (its English counterpart is "Block");
the entry spelled "Fordonspass" is only a "Se vagnomlopp." pointer and is
not the target.

Versions are immutable, so the links are repaired the way all prototype
links are: one row in legacy_ids, which the concept lookup resolves
(graph.find_concept).

Idempotent, INSERT-only. The target is found by collection slug and the
main branch's head spelling; a database without exactly one such concept
(fresh seed, test data) is left untouched and the migration still counts
as applied.

Run:  uv run python scripts/migrate_019_fordonspass_alias.py [path-to-db]
"""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"
LEGACY_ID = "bfdc1642-9a0a-498b-84dc-55934c204dac"
SLUG = "kollektivtrafikordboken-2008"
TERM = "Fordonpass"


def migrate(db_path: Path) -> dict[str, int]:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    counts = {"targets": 0, "created": 0}
    con = sqlite3.connect(db_path)
    try:
        targets = [
            row[0]
            for row in con.execute(
                """SELECT c.id
                   FROM concepts c
                   JOIN collections col ON col.id = c.collection_id
                   JOIN branches b ON b.concept_id = c.id AND b.name = 'main'
                   JOIN versions v ON v.id = b.head_version_id
                   WHERE col.slug = ? AND v.canonical_form = ? AND v.language = 'sv'""",
                (SLUG, TERM),
            )
        ]
        counts["targets"] = len(targets)
        if len(targets) != 1:
            print(
                f"Migration 019: {len(targets)} concepts spelled {TERM!r} in {SLUG} "
                f"({db_path}) — nothing to do"
            )
            return counts
        cur = con.execute(
            "INSERT OR IGNORE INTO legacy_ids (legacy_id, concept_id) VALUES (?, ?)",
            (LEGACY_ID, targets[0]),
        )
        counts["created"] = cur.rowcount
        con.commit()
        print(
            f"Migration 019 done: {db_path}\n"
            f"  · {LEGACY_ID} → {targets[0]} ({TERM})"
            + ("" if counts["created"] else " (alias already present)")
        )
    finally:
        con.close()
    return counts


if __name__ == "__main__":
    migrate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB)
