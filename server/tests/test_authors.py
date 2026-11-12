"""Unified authors/users + admin outreach workbench (migration 003).

Covers: public author list/detail shapes and counts, org_private hiding,
super-admin guards, PATCH status/note, opt-out sanctity (409 + explicit
clear), backfill idempotency, and that the claim-on-register activation
mechanism still holds for authors surfaced here.
"""

import importlib.util
import json
import sqlite3
import sys
import uuid
from pathlib import Path

from app.models import Annotation, User
from tests.conftest import register_payload

ANON = {"X-User": ""}

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "migrate_003_authors", _SCRIPTS / "migrate_003_authors.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _register(client, handle, password="hemligt-losenord", display_name=None):
    """Email-first registration (iteration 4); handle auto-slugifies from the
    display name. Claim flows pass an explicit handle (see the claim test)."""
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            **{
                "email": f"{handle}@example.org",
                "display_name": display_name or handle.title(),
                "password": password,
            },
        ),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _bearer(auth) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['token']}"}


def _create_concept(client, collection_id, form="hållplats", headers=None, **kwargs):
    resp = client.post(
        "/api/v1/concepts",
        json={
            "collection_id": collection_id,
            "canonical_form": form,
            "definition_md": kwargs.pop("definition_md", "En definition."),
            **kwargs,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_author_annotation(db, version_id, author: User, start=0, end=5):
    db.add(
        Annotation(
            version_id=version_id,
            attr_type="author",
            start=start,
            end=end,
            value={
                "name": author.display_name,
                "affiliation": author.affiliation,
                "web_url": author.web_url,
                "user_id": author.id,
                "handle": author.handle,
            },
        )
    )
    db.commit()


def _make_author(db, handle="greta", display_name="Greta Garbo", **kwargs) -> User:
    author = User(handle=handle, display_name=display_name, **kwargs)
    db.add(author)
    db.commit()
    return author


# --------------------------------------------------------------------------
# Public author surface
# --------------------------------------------------------------------------


def test_authors_list_shape_and_counts(client, db, collection):
    # 'testare' (dev X-User) authors two concepts → 2 versions, 0 sections.
    c1 = _create_concept(client, collection.id, form="hållplats")
    _create_concept(client, collection.id, form="linje")
    # Greta has no versions but one author annotation on c1's head.
    greta = _make_author(db, affiliation="K2", web_url="https://example.org/greta")
    _add_author_annotation(db, c1["head"]["id"], greta)

    rows = {a["handle"]: a for a in client.get("/api/v1/authors").json()}
    assert set(rows) == {"testare", "greta"}

    testare = rows["testare"]
    assert testare["version_count"] == 2
    assert testare["section_count"] == 0
    assert testare["concept_count"] == 2
    assert testare["activated"] is False
    assert testare["collections"] == [{"slug": "testsamling", "name": "Testsamling"}]

    greta_row = rows["greta"]
    assert greta_row["display_name"] == "Greta Garbo"
    assert greta_row["affiliation"] == "K2"
    assert greta_row["web_url"] == "https://example.org/greta"
    assert greta_row["version_count"] == 0
    assert greta_row["section_count"] == 1
    assert greta_row["concept_count"] == 1
    assert greta_row["activated"] is False


def test_authors_list_search_and_non_authors_hidden(client, db, collection):
    _create_concept(client, collection.id)
    _make_author(db, handle="passiv", display_name="Passiv Person")  # no authorship

    all_rows = client.get("/api/v1/authors").json()
    assert [a["handle"] for a in all_rows] == ["testare"]  # passive user not listed

    assert client.get("/api/v1/authors", params={"q": "test"}).json()[0]["handle"] == "testare"
    assert client.get("/api/v1/authors", params={"q": "finnsinte"}).json() == []


def test_author_detail_concepts_deduped_and_404s(client, db, collection):
    concept = _create_concept(client, collection.id, form="hållplats")
    # Revise → 2 versions on the same concept; the concept must appear once.
    resp = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": concept["head"]["id"],
            "canonical_form": "hållplats",
            "definition_md": "Ny text.",
        },
    )
    assert resp.status_code == 201

    detail = client.get("/api/v1/authors/testare")
    assert detail.status_code == 200
    body = detail.json()
    assert body["version_count"] == 2
    assert body["concept_count"] == 1
    assert body["concepts"] == [
        {
            "id": concept["id"],
            "canonical_form": "hållplats",
            "collection_slug": "testsamling",
            "collection_name": "Testsamling",
        }
    ]

    assert client.get("/api/v1/authors/finns-inte").status_code == 404
    # Existing user without authorship is not disclosed as an author.
    _make_author(db, handle="passiv", display_name="Passiv Person")
    assert client.get("/api/v1/authors/passiv").status_code == 404


def test_authors_hide_org_private_work_from_outsiders(client, db):
    super_admin = _register(client, "root")
    anna = _register(client, "anna")
    org = client.post(
        "/api/v1/orgs", json={"name": "K2", "slug": "k2"}, headers=_bearer(anna)
    ).json()
    # Org-owned collections require an APPROVED organisation (2026-07).
    approved = client.post("/api/v1/orgs/k2/approve", headers=_bearer(super_admin))
    assert approved.status_code == 200
    coll = client.post(
        "/api/v1/collections",
        json={
            "slug": "internt",
            "name": "Internt",
            "organisation_id": org["id"],
            "visibility": "org_private",
        },
        headers=_bearer(anna),
    ).json()
    _create_concept(client, coll["id"], form="internbegrepp", headers=_bearer(anna))

    # Anonymous: anna's only authorship is org_private → not an author at all.
    assert client.get("/api/v1/authors", headers=ANON).json() == []
    assert client.get("/api/v1/authors/anna", headers=ANON).status_code == 404
    # Member and super admin see her.
    for headers in (_bearer(anna), _bearer(super_admin)):
        detail = client.get("/api/v1/authors/anna", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["collections"] == [{"slug": "internt", "name": "Internt"}]


def test_claimed_author_shows_as_activated(client, db, collection):
    greta = _make_author(db, affiliation="K2")
    concept = _create_concept(client, collection.id)
    _add_author_annotation(db, concept["head"]["id"], greta)

    assert client.get("/api/v1/authors/greta").json()["activated"] is False

    # The claim-on-register rule IS the activation mechanism: the /activate
    # flow passes the imported handle explicitly together with claim=True
    # (without the flag the API answers 409 with a claim pointer instead).
    resp = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            **{
                "email": "greta@example.org",
                "handle": "greta",
                "claim": True,
                "display_name": "Något Annat",
                "password": "hemligt-losenord",
            },
        ),
    )
    assert resp.status_code == 201, resp.text
    auth = resp.json()
    assert auth["user"]["id"] == greta.id  # claimed, not duplicated
    assert auth["user"]["display_name"] == "Greta Garbo"  # imported name kept

    row = client.get("/api/v1/authors/greta").json()
    assert row["activated"] is True
    assert row["section_count"] == 1


# --------------------------------------------------------------------------
# Admin outreach workbench
# --------------------------------------------------------------------------


def test_outreach_requires_super_admin(client, collection):
    _create_concept(client, collection.id)
    _register(client, "root")  # first registered → super admin
    vanlig = _register(client, "vanlig")

    assert client.get("/api/v1/admin/outreach", headers=ANON).status_code == 401
    assert client.get("/api/v1/admin/outreach", headers=_bearer(vanlig)).status_code == 403
    # Dev X-User signature is not a super admin either.
    assert client.get("/api/v1/admin/outreach").status_code == 403
    patch = client.patch(
        "/api/v1/admin/outreach/whatever", json={"status": "contacted"}, headers=_bearer(vanlig)
    )
    assert patch.status_code == 403


def test_outreach_list_and_patch_status_note(client, db, collection):
    greta = _make_author(db, affiliation="K2")
    concept = _create_concept(client, collection.id)
    _add_author_annotation(db, concept["head"]["id"], greta)
    root = _register(client, "root")

    rows = {
        r["handle"]: r for r in client.get("/api/v1/admin/outreach", headers=_bearer(root)).json()
    }
    assert rows["greta"]["outreach_status"] is None
    assert rows["greta"]["outreach_note"] is None
    assert rows["greta"]["outreach_updated_at"] is None
    assert rows["greta"]["section_count"] == 1

    patched = client.patch(
        f"/api/v1/admin/outreach/{greta.id}",
        json={"status": "contacted", "note": "Mejlad 2026-07-04 via LU-adressen."},
        headers=_bearer(root),
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["outreach_status"] == "contacted"
    assert body["outreach_note"] == "Mejlad 2026-07-04 via LU-adressen."
    assert body["outreach_updated_at"] is not None

    # Omitting note keeps it; invalid status → 422; unknown user → 404.
    kept = client.patch(
        f"/api/v1/admin/outreach/{greta.id}", json={"status": None}, headers=_bearer(root)
    )
    assert kept.status_code == 200
    assert kept.json()["outreach_status"] is None
    assert kept.json()["outreach_note"] == "Mejlad 2026-07-04 via LU-adressen."
    assert (
        client.patch(
            f"/api/v1/admin/outreach/{greta.id}",
            json={"status": "spammad"},
            headers=_bearer(root),
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/admin/outreach/{uuid.uuid4()}",
            json={"status": "contacted"},
            headers=_bearer(root),
        ).status_code
        == 404
    )


def test_opt_out_is_sacred(client, db, collection):
    greta = _make_author(db)
    concept = _create_concept(client, collection.id)
    _add_author_annotation(db, concept["head"]["id"], greta)
    root = _register(client, "root")
    url = f"/api/v1/admin/outreach/{greta.id}"

    opted = client.patch(url, json={"status": "opted_out"}, headers=_bearer(root))
    assert opted.status_code == 200
    assert opted.json()["outreach_status"] == "opted_out"

    # opted_out → contacted is forbidden.
    blocked = client.patch(url, json={"status": "contacted"}, headers=_bearer(root))
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "author_opted_out"

    # Clearing needs the explicit confirmation flag.
    unconfirmed = client.patch(url, json={"status": None}, headers=_bearer(root))
    assert unconfirmed.status_code == 409

    # Note updates while staying opted_out are fine.
    noted = client.patch(
        url, json={"status": "opted_out", "note": "Avböjde per telefon."}, headers=_bearer(root)
    )
    assert noted.status_code == 200
    assert noted.json()["outreach_note"] == "Avböjde per telefon."

    cleared = client.patch(
        url, json={"status": None, "confirm_clear_opt_out": True}, headers=_bearer(root)
    )
    assert cleared.status_code == 200
    assert cleared.json()["outreach_status"] is None


# --------------------------------------------------------------------------
# Migration 003 backfill
# --------------------------------------------------------------------------


def _seed_backfill_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE users (
            id VARCHAR(36) PRIMARY KEY,
            handle VARCHAR(100) NOT NULL UNIQUE,
            display_name VARCHAR(200) NOT NULL,
            affiliation VARCHAR(500),
            web_url TEXT,
            password_hash TEXT,
            is_super_admin BOOLEAN NOT NULL DEFAULT 0,
            organisation_id VARCHAR(36),
            org_role VARCHAR(20),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE annotations (
            id VARCHAR(36) PRIMARY KEY,
            version_id VARCHAR(36) NOT NULL,
            attr_type VARCHAR(50) NOT NULL,
            start INTEGER NOT NULL DEFAULT 0,
            "end" INTEGER NOT NULL DEFAULT 0,
            quote TEXT,
            value JSON NOT NULL,
            provenance JSON NOT NULL DEFAULT '{}'
        );
        """
    )
    con.execute(
        "INSERT INTO users (id, handle, display_name, affiliation) VALUES"
        " ('u-1', 'greta-garbo', 'Greta Garbo', 'K2')"
    )

    def ann(ann_id: str, value: dict) -> None:
        con.execute(
            "INSERT INTO annotations (id, version_id, attr_type, value)"
            " VALUES (?, 'v-1', 'author', ?)",
            (ann_id, json.dumps(value, ensure_ascii=False)),
        )

    ann("a-1", {"name": "Greta Garbo", "affiliation": "K2"})  # exact match
    ann("a-2", {"name": "GRETA GARBO"})  # case-insensitive match
    ann(  # no user → must be created with slugified handle + metadata
        "a-3",
        {
            "name": "Märit Öhman",
            "affiliation": "Lunds universitet",
            "web_url": "https://example.org/marit",
        },
    )
    ann("a-4", {"affiliation": "Ingen alls"})  # nameless → unmatched
    con.commit()
    con.close()


def test_backfill_resolves_creates_and_is_idempotent(tmp_path):
    migration = _load_migration()
    db_path = tmp_path / "backfill.db"
    _seed_backfill_db(db_path)

    first = migration.migrate(db_path)
    assert first == {"resolved": 2, "created": 1, "unmatched": 1, "already_linked": 0}

    con = sqlite3.connect(db_path)
    values = {
        row[0]: json.loads(row[1])
        for row in con.execute("SELECT id, value FROM annotations").fetchall()
    }
    assert values["a-1"]["user_id"] == "u-1"
    assert values["a-1"]["handle"] == "greta-garbo"
    assert values["a-2"]["user_id"] == "u-1"
    created = con.execute(
        "SELECT handle, display_name, affiliation, web_url, outreach_status FROM users"
        " WHERE display_name = 'Märit Öhman'"
    ).fetchone()
    assert created == (
        "marit-ohman",
        "Märit Öhman",
        "Lunds universitet",
        "https://example.org/marit",
        None,
    )
    assert values["a-3"]["handle"] == "marit-ohman"
    assert "user_id" not in values["a-4"]
    user_columns = {row[1] for row in con.execute("PRAGMA table_info(users)")}
    assert {"outreach_status", "outreach_note", "outreach_updated_at"} <= user_columns
    con.close()

    # Second run: nothing new — everything already linked, no duplicate users.
    second = migration.migrate(db_path)
    assert second == {"resolved": 0, "created": 0, "unmatched": 1, "already_linked": 3}
    con = sqlite3.connect(db_path)
    assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
    con.close()


# --------------------------------------------------------------------------
# Collection contributors (paket B)
# --------------------------------------------------------------------------


def test_collection_detail_lists_contributors(client, db, collection):
    """GET /collections/{slug} carries the living author list: union of
    version authors and section-annotation authors, sorted by name, with
    'Redaktörerna' filtered out (editorial credit, not a person)."""
    c1 = _create_concept(client, collection.id, form="hållplats")
    greta = _make_author(db, affiliation="K2")
    _add_author_annotation(db, c1["head"]["id"], greta)
    redaktorerna = _make_author(db, handle="redaktorerna", display_name="Redaktörerna")
    _add_author_annotation(db, c1["head"]["id"], redaktorerna, start=6, end=10)

    detail = client.get(f"/api/v1/collections/{collection.slug}").json()
    rows = {row["handle"]: row for row in detail["contributors"]}

    # The annotated author: sections only, unactivated (claimable) profile.
    assert rows["greta"]["section_count"] == 1
    assert rows["greta"]["version_count"] == 0
    assert rows["greta"]["affiliation"] == "K2"
    assert rows["greta"]["activated"] is False

    # The version author (dev user) is counted from Version.created_by.
    version_authors = [row for row in rows.values() if row["version_count"] >= 1]
    assert version_authors, rows

    # Editorial credit is filtered out of the collection list (beslut 1).
    assert "redaktorerna" not in rows

    # Sorted by display name, case-insensitively.
    names = [row["display_name"].lower() for row in detail["contributors"]]
    assert names == sorted(names)


def test_collection_list_omits_contributors(client, collection):
    """The list endpoint stays light — contributors only on the detail."""
    rows = client.get("/api/v1/collections").json()
    assert all(row.get("contributors") is None for row in rows)
