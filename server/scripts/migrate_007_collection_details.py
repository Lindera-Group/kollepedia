"""Migration 007 — rich collection metadata restored from the old site.

The prototype carried per-collection provenance (source_url, archive_url,
credits, a sources_json array) and — the treasure — `collection_locales`:
bilingual sv/en name + short_description + long description (~18.5k chars per
language across the real collections). NG collections only kept a one-line
description. This migration

1. adds, if missing (idempotent ALTER — never drops anything):
   collections.source_url TEXT, archive_url TEXT, credits TEXT,
   sources JSON, locales JSON,
2. backfills them from the old DB (opened read-only), matching old → NG
   collections by slug. NG-only collections are skipped gracefully.
   sources_json is parsed (empty/invalid → NULL); locales become
   {sv: {name, short_description, description}, en: {…}}.

Collection.description is NEVER overwritten — it stays the short fallback;
the locales JSON is the rich layer. Fields are only filled where currently
NULL, so re-runs are no-ops and manual edits survive.

Run:  uv run python scripts/backup_database.py   (first!)
      uv run python scripts/migrate_007_collection_details.py [ng-db] <old-db>

The old database has no default path: pass it as the second argument or set
PROTOTYPE_DB (run_migrations.py does the latter).
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"

COLUMNS: list[tuple[str, str]] = [
    ("source_url", "TEXT"),
    ("archive_url", "TEXT"),
    ("credits", "TEXT"),
    ("sources", "JSON"),
    ("locales", "JSON"),
]
FIELDS = tuple(name for name, _ in COLUMNS)


def _clean(value: Any) -> str | None:
    """Old rows use '' and NULL interchangeably — normalise both to None."""
    text = str(value).strip() if value is not None else ""
    return text or None


def _parse_sources(raw: Any) -> list[Any] | None:
    """sources_json → parsed array; empty/invalid/non-array all become None."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, list) and parsed else None


def _build_locales(rows: list[tuple[str, Any, Any, Any]]) -> dict[str, Any] | None:
    """collection_locales rows → {sv: {name, short_description, description}, …}.
    Languages whose three fields are all empty are dropped entirely."""
    locales: dict[str, Any] = {}
    for language, name, short_description, description in rows:
        entry = {
            "name": _clean(name),
            "short_description": _clean(short_description),
            "description": _clean(description),
        }
        if any(entry.values()):
            locales[language] = entry
    return locales or None


def _read_old(old_db_path: Path) -> dict[str, dict[str, Any]]:
    """slug → the five enrichment values, read from the old DB (read-only)."""
    old = sqlite3.connect(f"file:{old_db_path}?mode=ro", uri=True)
    try:
        locales_by_collection: dict[str, list[tuple[str, Any, Any, Any]]] = {}
        for cid, language, name, short_desc, desc in old.execute(
            "SELECT collection_id, language, name, short_description, description"
            " FROM collection_locales ORDER BY language"
        ):
            locales_by_collection.setdefault(cid, []).append((language, name, short_desc, desc))

        by_slug: dict[str, dict[str, Any]] = {}
        for cid, slug, source_url, archive_url, credits, sources_json in old.execute(
            "SELECT collection_id, slug, source_url, archive_url, credits, sources_json"
            " FROM collections"
        ):
            by_slug[slug] = {
                "source_url": _clean(source_url),
                "archive_url": _clean(archive_url),
                "credits": _clean(credits),
                "sources": _parse_sources(sources_json),
                "locales": _build_locales(locales_by_collection.get(cid, [])),
            }
        return by_slug
    finally:
        old.close()


def _describe(values: dict[str, Any]) -> str:
    """Human summary of what a collection gained, for the per-collection log."""
    parts: list[str] = []
    locales = values.get("locales")
    if locales:
        langs = ", ".join(
            f"{lang}={len(entry.get('description') or '')} tecken"
            for lang, entry in sorted(locales.items())
        )
        parts.append(f"locales({langs})")
    if values.get("credits"):
        parts.append(f"credits='{values['credits']}'")
    if values.get("sources"):
        parts.append(f"sources={len(values['sources'])}")
    if values.get("source_url"):
        parts.append("source_url")
    if values.get("archive_url"):
        parts.append("archive_url")
    return ", ".join(parts) or "inget att hämta"


def migrate(db_path: Path, old_db_path: Path | None) -> dict[str, int]:
    if old_db_path is None:
        raise SystemExit("Old database path required: second argument or PROTOTYPE_DB.")
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    if not old_db_path.exists():
        raise SystemExit(f"Old database not found: {old_db_path}")

    counts = {
        "columns_added": 0,
        "collections_enriched": 0,
        "fields_set": 0,
        "skipped_no_match": 0,
    }
    old_by_slug = _read_old(old_db_path)

    con = sqlite3.connect(db_path)
    try:
        # -- 1. ALTER ADD COLUMN if missing ---------------------------------
        existing = {row[1] for row in con.execute("PRAGMA table_info(collections)")}
        for name, ddl in COLUMNS:
            if name in existing:
                print(f"  = collections.{name} already present — skipped")
            else:
                con.execute(f"ALTER TABLE collections ADD COLUMN {name} {ddl}")
                counts["columns_added"] += 1
                print(f"  + collections.{name} added ({ddl})")

        # -- 2. backfill from the old DB, matched by slug -------------------
        field_list = ", ".join(FIELDS)
        for row in con.execute(f"SELECT id, slug, {field_list} FROM collections"):
            ng_id, slug = row[0], row[1]
            current = dict(zip(FIELDS, row[2:], strict=True))
            values = old_by_slug.get(slug)
            if values is None:
                counts["skipped_no_match"] += 1
                print(f"  ~ {slug}: ingen motsvarighet i gamla databasen — hoppas över")
                continue

            updates: dict[str, Any] = {}
            for field in FIELDS:
                new = values[field]
                if new is None or current[field] is not None:
                    continue  # nothing to add, or already set (idempotent re-run)
                updates[field] = (
                    json.dumps(new, ensure_ascii=False) if field in ("sources", "locales") else new
                )
            if not updates:
                print(f"  = {slug}: redan berikad — hoppas över")
                continue

            assignments = ", ".join(f"{field} = ?" for field in updates)
            con.execute(
                f"UPDATE collections SET {assignments} WHERE id = ?",
                (*updates.values(), ng_id),
            )
            counts["collections_enriched"] += 1
            counts["fields_set"] += len(updates)
            enriched = {field: values[field] for field in updates}
            print(f"  + {slug}: {_describe(enriched)}")
        con.commit()
    finally:
        con.close()

    print(f"\nMigration 007 done: {db_path}")
    print(
        f"  {counts['columns_added']} columns added, "
        f"{counts['collections_enriched']} collections enriched "
        f"({counts['fields_set']} fields), "
        f"{counts['skipped_no_match']} without old counterpart"
    )
    return counts


if __name__ == "__main__":
    prototype = os.environ.get("PROTOTYPE_DB", "")
    migrate(
        Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB,
        Path(sys.argv[2]) if len(sys.argv) > 2 else (Path(prototype) if prototype else None),
    )
