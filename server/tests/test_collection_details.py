"""Rich collection metadata restored from the old site (migration 007).

Covers: the serializer exposing source_url/archive_url/credits/sources/locales,
PATCH accepting exactly the three editable fields (sources/locales silently
ignored — imported provenance), and migration 007's slug-matched backfill
being idempotent, description-preserving and tolerant of bad sources_json.
"""

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

from app.models import Collection

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

LOCALES = {
    "sv": {
        "name": "Kollepedia",
        "short_description": None,
        "description": "En lång svensk beskrivning av samlingen.",
    },
    "en": {
        "name": "Kollepedia",
        "short_description": None,
        "description": "A long English description of the collection.",
    },
}
SOURCES = [
    {
        "label_sv": "Källa 1",
        "label_en": "Source 1",
        "url": "https://source.se",
        "filename": None,
        "type": "web",
    }
]


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "migrate_007_collection_details", _SCRIPTS / "migrate_007_collection_details.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# API surface
# --------------------------------------------------------------------------


def test_collection_out_exposes_rich_metadata(client, db):
    coll = Collection(
        slug="rik-samling",
        name="Rik samling",
        description="Kort fallback.",
        source_url="http://www.kollepedia.se",
        archive_url="https://web.archive.org/web/2012/http://www.kollepedia.se",
        credits="KTH Järnvägsgruppen m.fl.",
        sources=SOURCES,
        locales=LOCALES,
    )
    db.add(coll)
    db.commit()

    body = client.get("/api/v1/collections/rik-samling").json()
    assert body["description"] == "Kort fallback."
    assert body["source_url"] == "http://www.kollepedia.se"
    assert body["archive_url"] == "https://web.archive.org/web/2012/http://www.kollepedia.se"
    assert body["credits"] == "KTH Järnvägsgruppen m.fl."
    assert body["sources"] == SOURCES
    assert body["locales"] == LOCALES
    # The list endpoint carries the same fields.
    listed = {c["slug"]: c for c in client.get("/api/v1/collections").json()}
    assert listed["rik-samling"]["locales"] == LOCALES


def test_rich_metadata_defaults_to_null(client, collection):
    body = client.get(f"/api/v1/collections/{collection.slug}").json()
    for field in ("source_url", "archive_url", "credits", "sources", "locales"):
        assert body[field] is None


def test_patch_accepts_credits_and_provenance_urls(client):
    # X-User 'testare' creates a PRIVATE sandbox (org-less public → 422 since
    # the 2026-07 funnel) → the creator may manage it.
    coll = client.post(
        "/api/v1/collections",
        json={"slug": "min-samling", "name": "Min samling", "visibility": "private"},
    ).json()
    patched = client.patch(
        f"/api/v1/collections/{coll['slug']}",
        json={
            "credits": "Svensk Kollektivtrafik",
            "source_url": "https://example.org/ordbok",
            "archive_url": "https://web.archive.org/web/2020/https://example.org/ordbok",
        },
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["credits"] == "Svensk Kollektivtrafik"
    assert body["source_url"] == "https://example.org/ordbok"
    assert body["archive_url"] == "https://web.archive.org/web/2020/https://example.org/ordbok"
    # Persisted, and explicit null clears again (normal PATCH semantics).
    assert client.get("/api/v1/collections/min-samling").json()["credits"] == (
        "Svensk Kollektivtrafik"
    )
    cleared = client.patch("/api/v1/collections/min-samling", json={"credits": None})
    assert cleared.status_code == 200
    assert cleared.json()["credits"] is None


def test_patch_silently_ignores_sources_and_locales(client, db):
    # Private sandbox: 'testare' both creates and manages it (see above).
    coll = client.post(
        "/api/v1/collections",
        json={"slug": "importerad", "name": "Importerad", "visibility": "private"},
    ).json()
    stored = db.get(Collection, coll["id"])
    stored.sources = SOURCES
    stored.locales = LOCALES
    db.commit()

    resp = client.patch(
        "/api/v1/collections/importerad",
        json={"credits": "CEN TC 278", "sources": [], "locales": {"sv": {"name": "Hackad"}}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["credits"] == "CEN TC 278"  # the editable field applied…
    assert body["sources"] == SOURCES  # …the imported provenance untouched
    assert body["locales"] == LOCALES


# --------------------------------------------------------------------------
# Migration 007 backfill
# --------------------------------------------------------------------------


def _seed_ng_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE collections (
            id VARCHAR(36) PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT
        );
        """
    )
    con.executemany(
        "INSERT INTO collections (id, slug, name, description) VALUES (?, ?, ?, ?)",
        [
            ("ng-1", "kollepedia-2012", "Kollepedia", "Kort NG-beskrivning."),
            ("ng-2", "trasig-2020", "Trasig", None),
            ("ng-3", "tidsmaskinen", "Tidsmaskinen", "NG-egen samling."),
        ],
    )
    con.commit()
    con.close()


def _seed_old_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE collections (
            collection_id TEXT PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            description TEXT,
            source_url TEXT,
            archive_url TEXT,
            credits TEXT,
            sources_json TEXT
        );
        CREATE TABLE collection_locales (
            locale_id TEXT PRIMARY KEY,
            collection_id TEXT NOT NULL,
            language TEXT NOT NULL,
            name TEXT NOT NULL,
            short_description TEXT,
            description TEXT
        );
        """
    )
    con.execute(
        "INSERT INTO collections VALUES ('old-1', 'kollepedia-2012',"
        " 'En mycket längre gammal beskrivning som INTE får skriva över NG:s.',"
        " 'http://www.kollepedia.se', 'https://web.archive.org/2012',"
        " 'KTH Järnvägsgruppen m.fl.', ?)",
        (json.dumps(SOURCES, ensure_ascii=False),),
    )
    # Broken sources_json + empty credits/urls → everything except locales NULL.
    con.execute(
        "INSERT INTO collections VALUES ('old-2', 'trasig-2020', '', '', NULL, '', 'inte json')"
    )
    # Old-only collection (test junk) — must be skipped gracefully.
    con.execute(
        "INSERT INTO collections VALUES ('old-3', 'testsamling-gammal', '', NULL,"
        " NULL, 'Cred', '[]')"
    )
    con.executemany(
        "INSERT INTO collection_locales VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("l-1", "old-1", "sv", "Kollepedia", None, "Lång svensk text om samlingen."),
            ("l-2", "old-1", "en", "Kollepedia", None, "Long English text about it."),
            ("l-3", "old-2", "sv", "Trasig", "Kort.", ""),
            ("l-4", "old-2", "en", "", "", ""),  # all-empty → language dropped
        ],
    )
    con.commit()
    con.close()


def test_migration_007_backfills_and_is_idempotent(tmp_path):
    migration = _load_migration()
    ng_path, old_path = tmp_path / "ng.db", tmp_path / "old.db"
    _seed_ng_db(ng_path)
    _seed_old_db(old_path)

    first = migration.migrate(ng_path, old_path)
    assert first == {
        "columns_added": 5,
        "collections_enriched": 2,
        "fields_set": 5 + 1,  # kollepedia-2012 all five; trasig-2020 locales only
        "skipped_no_match": 1,  # tidsmaskinen has no old counterpart
    }

    con = sqlite3.connect(ng_path)
    rows = {
        row[0]: row
        for row in con.execute(
            "SELECT slug, description, source_url, archive_url, credits,"
            " sources, locales FROM collections"
        )
    }
    slug, desc, src, arch, credits, sources, locales = rows["kollepedia-2012"]
    assert desc == "Kort NG-beskrivning."  # NEVER overwritten by the old long one
    assert (src, arch, credits) == (
        "http://www.kollepedia.se",
        "https://web.archive.org/2012",
        "KTH Järnvägsgruppen m.fl.",
    )
    assert json.loads(sources) == SOURCES
    assert json.loads(locales) == {
        "sv": {
            "name": "Kollepedia",
            "short_description": None,
            "description": "Lång svensk text om samlingen.",
        },
        "en": {
            "name": "Kollepedia",
            "short_description": None,
            "description": "Long English text about it.",
        },
    }
    trasig = rows["trasig-2020"]
    assert trasig[2:6] == (None, None, None, None)  # ''/invalid json → NULL
    assert json.loads(trasig[6]) == {
        "sv": {"name": "Trasig", "short_description": "Kort.", "description": None}
    }
    assert rows["tidsmaskinen"][2:] == (None, None, None, None, None)
    con.close()

    # Second run: columns exist, every field already set → pure no-op.
    second = migration.migrate(ng_path, old_path)
    assert second == {
        "columns_added": 0,
        "collections_enriched": 0,
        "fields_set": 0,
        "skipped_no_match": 1,
    }
