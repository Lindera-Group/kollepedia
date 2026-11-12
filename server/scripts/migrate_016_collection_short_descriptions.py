"""Migration 016 — seed curated short descriptions into collections.locales.

The grouped collections overview (v1-spegeln 2026-07-16) renders each card's
short description from locales.<lang>.short_description, falling back to
Collection.description. v1 carried curated per-slug texts hardcoded in the
frontend (i18n.js collectionShortDescriptions); their right home in NG is the
data layer. This seeds those texts (sv+en) for the known collections.

Idempotent, UPDATE-only: a slug's text is written only when the current
short_description is NULL/missing — curated edits are never overwritten.

Run:  uv run python scripts/migrate_016_collection_short_descriptions.py [path-to-db]
"""

import json
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"

# v1:s kurerade korttexter (web/src/lib/i18n.js) + NG-tillägget nomenklatur.
SHORTS: dict[str, dict[str, str]] = {
    "kollektivtrafikordboken-2008": {
        "sv": (
            "Svensk-engelsk terminologi från den europeiska Transmodel-standarden, "
            "anpassad för svensk kollektivtrafik."
        ),
        "en": (
            "Comprehensive Swedish-English terminology from the European Transmodel "
            "standard, adapted for Swedish public transport."
        ),
    },
    "kollepedia-2012": {
        "sv": (
            "Communityunderhållen terminologiwiki från 2012, bevarad från det "
            "ursprungliga kollepedia.se-arkivet."
        ),
        "en": (
            "Community-maintained terminology wiki from 2012, preserved from the "
            "original kollepedia.se archive."
        ),
    },
    "ordbok-framtidens-resande-2024": {
        "sv": (
            "Akademisk ordlista från K2 (Nationellt kunskapscentrum för "
            "kollektivtrafik) med fokus på urban mobilitet."
        ),
        "en": (
            "Academic glossary from K2 (Swedish Knowledge Centre for Public "
            "Transport), focusing on urban mobility."
        ),
    },
    "transmodel-2021": {
        "sv": (
            "Officiell europeisk referensdatamodell för kollektivtrafik (EN 12896), "
            "version 6.0 med NM-revideringar 2021."
        ),
        "en": (
            "Official European Reference Data Model for Public Transport (EN 12896), "
            "version 6.0 with NM revisions 2021."
        ),
    },
    "samtrafiken-begreppslista-2024": {
        "sv": (
            "Samtrafikens officiella begreppslista med termer som används inom "
            "svensk kollektivtrafik."
        ),
        "en": (
            "Official glossary from Samtrafiken covering terms used in Swedish public transport."
        ),
    },
    "trafikverket-jarnvagstermer-2025": {
        "sv": (
            "Trafikverkets ordlista med vanliga järnvägstermer och förklaringar av signalsystem."
        ),
        "en": (
            "Railway terminology from Trafikverket explaining signal systems and "
            "track infrastructure."
        ),
    },
    "nomenklatur-2024": {
        "sv": "Arbetsmaterial för harmoniserad nomenklatur inom svensk kollektivtrafik.",
        "en": "Working material for harmonised public transport nomenclature in Sweden.",
    },
}


def migrate(db_path: Path) -> int:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    changed = 0
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT slug, locales FROM collections WHERE slug IN ({})".format(
                ",".join("?" * len(SHORTS))
            ),
            list(SHORTS),
        ).fetchall()
        for slug, raw in rows:
            locales = json.loads(raw) if raw else {}
            touched = []
            for lang, text in SHORTS[slug].items():
                loc = locales.setdefault(lang, {})
                if not loc.get("short_description"):
                    loc["short_description"] = text
                    touched.append(lang)
            if touched:
                con.execute(
                    "UPDATE collections SET locales = ? WHERE slug = ?",
                    (json.dumps(locales, ensure_ascii=False), slug),
                )
                changed += 1
                print(f"  · {slug}: short_description satt ({', '.join(touched)})")
            else:
                print(f"  · {slug}: redan satt – orörd")
        con.commit()
        print(f"\nMigration 016 done: {db_path}\n  {changed} collection(s) updated")
    finally:
        con.close()
    return changed


if __name__ == "__main__":
    migrate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB)
