"""Night-2 import tests: template, CSV/XLSX pipeline, dry-run, AI extraction."""

import csv
import io

import openpyxl

from app.routers.imports import COLUMNS
from tests.conftest import register_payload

HEADERS = {"X-User": "Importtestare"}
BASE = "/api/v1/collections/testsamling"


def _csv_bytes(rows: list[dict], delimiter: str = ",") -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, delimiter=delimiter)
    writer.writeheader()
    for row in rows:
        writer.writerow({**dict.fromkeys(COLUMNS, ""), **row})
    return buffer.getvalue().encode("utf-8")


def _post_file(client, content: bytes, *, dry_run=False, filename="termer.csv", headers=HEADERS):
    return client.post(
        f"{BASE}/import?dry_run={'true' if dry_run else 'false'}",
        files={"file": (filename, content, "text/csv")},
        headers=headers,
    )


def _concepts(client):
    return client.get("/api/v1/concepts", params={"collection": "testsamling"}).json()


def _concept_by_form(client, form: str) -> dict:
    items = _concepts(client)["items"]
    match = next(i for i in items if i["canonical_form"] == form)
    return client.get(f"/api/v1/concepts/{match['id']}").json()


SAMPLE_ROWS = [
    {
        "canonical_form": "hållplats",
        "language": "sv",
        "definition": "Plats där resenärer väntar på fordon.",
        "status": "fastställd",
        "tags": "Infrastruktur;Drift",
        "note": "Grundterm.",
        "author": "Anna Andersson",
        "author_affiliation": "K2",
        "variants": "hållplatsen;hpl",
        "related_to": "bytespunkt",
        "source": "Transmodel v6.0",
    },
    {"canonical_form": "bytespunkt", "definition": "Plats där resenärer byter fordon."},
    {
        "canonical_form": "stop",
        "language": "en",
        "definition": "A place where passengers wait.",
        "translation_of": "hållplats",
    },
]


# --------------------------------------------------------------------------
# Template
# --------------------------------------------------------------------------


def test_import_template_csv(client, collection):
    resp = client.get(f"{BASE}/import/template", params={"format": "csv"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert 'filename="testsamling-import-mall.csv"' in resp.headers["content-disposition"]
    reader = csv.reader(io.StringIO(resp.text))
    header, example = next(reader), next(reader)
    assert header == COLUMNS
    assert example[0] == "hållplats"
    assert client.get(f"{BASE}/import/template", params={"format": "xlsx"}).status_code == 422


# --------------------------------------------------------------------------
# File import — CSV
# --------------------------------------------------------------------------


def test_csv_happy_path_full_pipeline(client, collection):
    resp = _post_file(client, _csv_bytes(SAMPLE_ROWS))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "rows_total": 3,
        "created": 3,
        "errors": [],
        "warnings": [],
        "dry_run": False,
    }
    assert _concepts(client)["total"] == 3

    hallplats = _concept_by_form(client, "hållplats")
    head = hallplats["head"]
    assert head["status"] == "proposed"  # "fastställd" is no longer a status — lands as proposed
    assert head["tags"] == ["Infrastruktur", "Drift"]
    assert head["note"] == "Grundterm."
    assert head["provenance"] == {"kind": "import", "source": "termer.csv", "row": 1}
    # Author became a user (resolve-or-create) and is the version's creator.
    assert head["created_by"]["display_name"] == "Anna Andersson"
    assert head["created_by"]["affiliation"] == "K2"
    # Variants + source citation live as annotations on the initial version.
    annotations = {
        (a["attr_type"], a["value"].get("form") or a["value"].get("text"))
        for a in head["annotations"]
    }
    assert annotations == {
        ("variant", "hållplatsen"),
        ("variant", "hpl"),
        ("source_citation", "Transmodel v6.0"),
    }
    # Relation resolved within the same file.
    relations = [(r["relation_type"], r["other_canonical_form"]) for r in hallplats["relations"]]
    assert ("related_to", "bytespunkt") in relations
    # translation_of created a translated_from edge between the initial versions.
    translations = [(t["language"], t["canonical_form"]) for t in hallplats["translations"]]
    assert translations == [("en", "stop")]


def test_csv_delimiter_sniffing_semicolon(client, collection):
    content = _csv_bytes(SAMPLE_ROWS, delimiter=";")
    resp = _post_file(client, content)
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 3
    head = _concept_by_form(client, "hållplats")["head"]
    assert head["tags"] == ["Infrastruktur", "Drift"]


def test_csv_status_swedish_labels_and_api_values(client, collection):
    mapping = {
        "utkast": "draft",
        "föreslagen": "proposed",
        "fastställd": "proposed",  # legacy label — endorsement rework 2026-07-11
        "utfasad": "deprecated",
        "ersatt": "superseded",
        "proposed": "proposed",  # API values pass straight through
        "": "draft",  # default
    }
    rows = [
        {"canonical_form": f"term-{i}", "definition": "En definition.", "status": label}
        for i, label in enumerate(mapping)
    ]
    resp = _post_file(client, _csv_bytes(rows))
    assert resp.json()["created"] == len(mapping)
    for i, (label, expected) in enumerate(mapping.items()):
        assert _concept_by_form(client, f"term-{i}")["head"]["status"] == expected, label
    # Unknown status is a per-row error, not a crash.
    bad = _post_file(
        client, _csv_bytes([{"canonical_form": "x", "definition": "d", "status": "godkänd"}])
    )
    body = bad.json()
    assert body["created"] == 0
    assert "okänd status 'godkänd'" in body["errors"][0]["message"]


def test_csv_partial_import_reports_row_errors(client, collection):
    rows = [
        {"canonical_form": "buss", "definition": "Ett vägfordon för många resenärer."},
        {"canonical_form": "tåg", "definition": ""},  # error: definition saknas
        {"canonical_form": "spårvagn", "definition": "Ett spårfordon.", "language": "de"},
        {"canonical_form": "färja", "definition": "Ett fartyg i linjetrafik."},
    ]
    resp = _post_file(client, _csv_bytes(rows))
    body = resp.json()
    assert body["rows_total"] == 4
    assert body["created"] == 2
    assert [e["row"] for e in body["errors"]] == [2, 3]
    assert "definition saknas" in body["errors"][0]["message"]
    assert "okänt språk 'de'" in body["errors"][1]["message"]
    # The valid rows really imported.
    forms = {i["canonical_form"] for i in _concepts(client)["items"]}
    assert forms == {"buss", "färja"}


def test_dry_run_validates_but_writes_nothing(client, collection):
    resp = _post_file(client, _csv_bytes(SAMPLE_ROWS), dry_run=True)
    body = resp.json()
    assert body["dry_run"] is True
    assert body["created"] == 3
    assert body["errors"] == [] and body["warnings"] == []
    assert _concepts(client)["total"] == 0
    # Not even the author user survives a dry run.
    assert client.get("/api/v1/users", params={"q": "anna-andersson"}).json() == []


def test_unresolved_relation_is_warning_and_existing_concepts_resolve(client, collection):
    existing = client.post(
        "/api/v1/concepts",
        json={
            "collection_id": collection.id,
            "canonical_form": "fordon",
            "definition_md": "Något som rullar.",
        },
        headers=HEADERS,
    ).json()
    rows = [
        {
            "canonical_form": "buss",
            "definition": "Ett vägfordon.",
            "broader": "fordon",
            "related_to": "finns-inte",
        }
    ]
    body = _post_file(client, _csv_bytes(rows)).json()
    assert body["created"] == 1
    assert body["errors"] == []
    assert len(body["warnings"]) == 1
    assert "finns-inte" in body["warnings"][0]
    buss = _concept_by_form(client, "buss")
    assert [(r["relation_type"], r["other_concept_id"]) for r in buss["relations"]] == [
        ("broader", existing["id"])
    ]


def test_import_limits_and_auth(client, collection):
    # 5000-row limit → 413 with a structured detail.
    lines = ["canonical_form,definition"] + [f"term{i},def{i}" for i in range(5001)]
    resp = _post_file(client, "\n".join(lines).encode())
    assert resp.status_code == 413
    detail = resp.json()["detail"]
    assert detail["code"] == "import_too_many_rows"
    assert detail["params"]["max_rows"] == 5000
    # 5 MB limit → 413.
    big = b"canonical_form,definition\n" + b"a" * (5 * 1024 * 1024)
    assert _post_file(client, big).status_code == 413
    # Writes require an acting user (the client fixture's default X-User is
    # blanked to simulate anonymity).
    anonymous = {"X-User": ""}
    assert _post_file(client, _csv_bytes(SAMPLE_ROWS), headers=anonymous).status_code == 401
    assert (
        client.post(
            f"{BASE}/import-rows", json={"rows": [], "dry_run": True}, headers=anonymous
        ).status_code
        == 401
    )


def test_csv_rejects_missing_required_columns_and_bad_encoding(client, collection):
    resp = _post_file(client, b"name,description\nfoo,bar")
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["code"] == "import_bad_columns"
    assert "canonical_form" in detail["params"]["missing"]
    latin1 = "canonical_form,definition\nhållplats,En plats.".encode("latin-1")
    resp = _post_file(client, latin1)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "file_not_utf8"


# --------------------------------------------------------------------------
# File import — XLSX
# --------------------------------------------------------------------------


def test_xlsx_happy_path(client, collection):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(COLUMNS)
    for row in SAMPLE_ROWS:
        sheet.append([row.get(column, "") for column in COLUMNS])
    stream = io.BytesIO()
    workbook.save(stream)

    resp = client.post(
        f"{BASE}/import?dry_run=false",
        files={
            "file": (
                "termer.xlsx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 3
    hallplats = _concept_by_form(client, "hållplats")
    assert hallplats["head"]["provenance"]["source"] == "termer.xlsx"
    assert [t["canonical_form"] for t in hallplats["translations"]] == ["stop"]


# --------------------------------------------------------------------------
# JSON rows import (the AI flow's write path)
# --------------------------------------------------------------------------


def test_import_rows_same_pipeline_with_rows_provenance(client, collection):
    payload = {
        "rows": [
            {"canonical_form": "biljett", "definition": "Färdbevis.", "status": "utkast"},
            {"canonical_form": "", "definition": "saknar term"},
        ],
        "dry_run": False,
    }
    resp = client.post(f"{BASE}/import-rows", json=payload, headers=HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rows_total"] == 2 and body["created"] == 1
    assert "canonical_form saknas" in body["errors"][0]["message"]
    head = _concept_by_form(client, "biljett")["head"]
    assert head["provenance"] == {"kind": "import", "source": "rows", "row": 1}
    assert head["status"] == "draft"


# --------------------------------------------------------------------------
# /ai/extract
# --------------------------------------------------------------------------


def test_ai_extract_requires_key_and_caps_length(client):
    resp = client.post("/api/v1/ai/extract", json={"text": "hållplats: en plats."})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "ai_key_missing"
    resp = client.post(
        "/api/v1/ai/extract",
        json={"text": "x" * 50_001},
        headers={"X-LLM-Key": "sk-test"},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["code"] == "text_too_long"
    assert detail["params"]["max"] == 50000


def test_ai_extract_mocked_happy_path(client, monkeypatch):
    from app.routers import ai as ai_module

    captured: dict = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "```json\n"
                            '[{"canonical_form": "hållplats", "definition": "En plats.", '
                            '"tags": ["Infrastruktur", "Drift"], "related_to": "bytespunkt"},'
                            ' {"canonical_form": "bytespunkt", "definition": "En annan plats."},'
                            ' {"definition": "rad utan term ignoreras"}]\n'
                            "```"
                        ),
                    }
                ]
            }

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, body=json, headers=headers)
        return FakeResponse()

    monkeypatch.setattr(ai_module.httpx, "post", fake_post)
    resp = client.post(
        "/api/v1/ai/extract",
        json={"text": "hållplats — en plats. Se även bytespunkt.", "language": "sv"},
        headers={"X-LLM-Key": "sk-test-123"},
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()["rows"]
    assert rows == [
        {
            "canonical_form": "hållplats",
            "definition": "En plats.",
            "tags": "Infrastruktur;Drift",  # lists are ';'-joined
            "related_to": "bytespunkt",
        },
        {"canonical_form": "bytespunkt", "definition": "En annan plats."},
    ]
    assert captured["headers"]["x-api-key"] == "sk-test-123"
    assert captured["body"]["max_tokens"] == ai_module.EXTRACT_MAX_TOKENS
    assert "JSON array" in captured["body"]["system"]
    assert "hållplats — en plats." in captured["body"]["messages"][0]["content"]


def test_ai_extract_tolerates_rows_wrapper_and_extracted_rows_import(
    client, collection, monkeypatch
):
    from app.routers import ai as ai_module

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"rows": [{"canonical_form": "zon", "definition": "Ett område."}]}'
                        ),
                    }
                ]
            }

    monkeypatch.setattr(ai_module.httpx, "post", lambda *a, **kw: FakeResponse())
    resp = client.post(
        "/api/v1/ai/extract",
        json={"text": "zon: ett område."},
        headers={"X-LLM-Key": "sk-test"},
    )
    rows = resp.json()["rows"]
    assert rows == [{"canonical_form": "zon", "definition": "Ett område."}]
    # The extracted rows flow straight into the same import pipeline.
    imported = client.post(
        f"{BASE}/import-rows", json={"rows": rows, "dry_run": False}, headers=HEADERS
    ).json()
    assert imported["created"] == 1


def _xlsx_bytes(rows: list[dict]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(COLUMNS)
    for row in rows:
        sheet.append([row.get(column, "") for column in COLUMNS])
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def test_row_cap_is_enforced_while_parsing_csv_and_xlsx(client, collection, monkeypatch):
    """The cap trips during parsing (413) instead of after the whole file has
    been materialised — a 5 MB workbook may hold millions of empty rows."""
    from app.routers import imports as imports_module

    monkeypatch.setattr(imports_module, "MAX_ROWS", 3)
    rows = [{"canonical_form": f"term-{i}", "definition": "d"} for i in range(4)]
    for content, filename in ((_csv_bytes(rows), "många.csv"), (_xlsx_bytes(rows), "många.xlsx")):
        resp = _post_file(client, content, filename=filename)
        assert resp.status_code == 413, filename
        detail = resp.json()["detail"]
        assert detail["code"] == "import_too_many_rows"
        assert detail["params"]["max_rows"] == 3
    # Exactly at the cap is fine.
    assert _post_file(client, _csv_bytes(rows[:3])).json()["created"] == 3
    # The JSON rows path keeps its own check.
    rows_resp = client.post(f"{BASE}/import-rows", json={"rows": rows}, headers=HEADERS)
    assert rows_resp.status_code == 413


def test_file_type_is_decided_by_content_not_extension(client, collection):
    # CSV bytes under an .xlsx name: rejected as not-Excel, not misparsed.
    wrong = _post_file(client, _csv_bytes(SAMPLE_ROWS), filename="termer.xlsx")
    assert wrong.status_code == 400
    assert wrong.json()["detail"]["code"] == "file_not_xlsx"
    # A real workbook under a .csv name is still read as a workbook.
    resp = _post_file(client, _xlsx_bytes(SAMPLE_ROWS), filename="termer.csv")
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 3


def test_author_column_only_attributes_to_unclaimed_profiles_or_the_importer(
    client, collection, db
):
    """A row's `author` must never sign a real person's account (history is
    immutable): claimed accounts keep their attribution and affiliation, and
    the name lands as provenance text instead."""
    from app.models import User

    claimed = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            email="anna@example.org",
            display_name="Anna Andersson",  # handle anna-andersson, has a password
            password="hemligt123-abc",
        ),
    ).json()
    assert claimed["user"]["handle"] == "anna-andersson"
    db.add(User(handle="bo-berg", display_name="Bo Berg"))  # imported, unclaimed
    db.commit()

    rows = [
        {
            "canonical_form": "a",
            "definition": "d",
            "author": "Anna Andersson",
            "author_affiliation": "K2",
        },
        {
            "canonical_form": "b",
            "definition": "d",
            "author": "Bo Berg",
            "author_affiliation": "SL",
        },
        {"canonical_form": "c", "definition": "d", "author": "Importtestare"},
        {
            "canonical_form": "d",
            "definition": "d",
            "author": "Ny Person",
            "author_affiliation": "X",
        },
    ]
    resp = _post_file(client, _csv_bytes(rows))
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 4

    # Claimed account: the importer signs, the name is provenance text only.
    a = _concept_by_form(client, "a")["head"]
    assert a["created_by"]["handle"] == "importtestare"
    assert a["provenance"]["author_name"] == "Anna Andersson"
    assert a["provenance"]["author_affiliation"] == "K2"
    anna = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {claimed['token']}"})
    assert anna.json()["affiliation"] is None  # never touched by an import

    # Unclaimed profile: attributed, affiliation filled while empty.
    b = _concept_by_form(client, "b")["head"]
    assert b["created_by"]["handle"] == "bo-berg"
    assert b["created_by"]["affiliation"] == "SL"
    assert "author_name" not in b["provenance"]

    # The importer naming themself: plain attribution.
    c = _concept_by_form(client, "c")["head"]
    assert c["created_by"]["handle"] == "importtestare"
    assert "author_name" not in c["provenance"]

    # An unknown name still becomes a fresh unclaimed profile.
    d = _concept_by_form(client, "d")["head"]
    assert d["created_by"]["display_name"] == "Ny Person"
    assert d["created_by"]["affiliation"] == "X"


def test_import_respects_collection_permissions(client):
    """Imports are bulk writes: org_private hides the slug (404) and org-owned
    collections require membership (403) — the security gap found in the
    parity double-check."""
    admin = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            client,
            **{
                "email": "org-admin@example.org",
                "display_name": "Org Admin",
                "password": "hemligt123-abc",
            },
        ),
    ).json()
    admin_headers = {"Authorization": f"Bearer {admin['token']}"}
    org = client.post(
        "/api/v1/orgs", json={"name": "Importorg", "slug": "importorg"}, headers=admin_headers
    ).json()
    client.post(
        "/api/v1/collections",
        json={
            "slug": "org-import-coll",
            "name": "Orgsamling",
            "organisation_id": org["id"],
            "visibility": "org_private",
        },
        headers=admin_headers,
    )
    files = {"file": ("t.csv", b"canonical_form;definition\nterm x;En definition.", "text/csv")}

    # Stranger with a bare signature: org_private must not even confirm the slug.
    r = client.post(
        "/api/v1/collections/org-import-coll/import?dry_run=true",
        files=files,
        headers={"X-User": "frammling"},
    )
    assert r.status_code == 404
    r = client.get(
        "/api/v1/collections/org-import-coll/import/template",
        headers={"X-User": "frammling"},
    )
    assert r.status_code == 404

    # Public but org-owned: visible, yet writing requires membership.
    client.patch(
        "/api/v1/collections/org-import-coll",
        json={"visibility": "public"},
        headers=admin_headers,
    )
    files = {"file": ("t.csv", b"canonical_form;definition\nterm x;En definition.", "text/csv")}
    r = client.post(
        "/api/v1/collections/org-import-coll/import?dry_run=true",
        files=files,
        headers={"X-User": "frammling"},
    )
    assert r.status_code == 403

    files = {"file": ("t.csv", b"canonical_form;definition\nterm x;En definition.", "text/csv")}
    r = client.post(
        "/api/v1/collections/org-import-coll/import?dry_run=true",
        files=files,
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["rows_total"] == 1


def test_import_categories_and_part_columns(client, collection, db):
    """Plan NG_TAXONOMIES follow-up: `categories` validates against the global
    vocabulary (sv or en names), `part` against the collection's exact-one
    taxonomy; unknown names are hard row errors."""
    from app.models import Taxonomy, TaxonomyValue

    tax = Taxonomy(slug="kategorier", name="Kategorier", scope="global", min_per_concept=1)
    db.add(tax)
    db.flush()
    db.add(TaxonomyValue(taxonomy_id=tax.id, name="Drift", name_en="Operations", position=0))
    parts = Taxonomy(
        slug="parts",
        name="Delar",
        scope="collection",
        collection_id=collection.id,
        min_per_concept=1,
        max_per_concept=1,
    )
    db.add(parts)
    db.flush()
    db.add(TaxonomyValue(taxonomy_id=parts.id, name="Del 2 — Network", position=0))
    db.commit()

    rows = [
        {
            "canonical_form": "resa",
            "definition": "d",
            "categories": "Operations",
            "part": "Del 2 — Network",
        },
        {"canonical_form": "tur", "definition": "d", "categories": "Finns inte"},
        {"canonical_form": "zon", "definition": "d", "part": "Del 99"},
    ]
    resp = _post_file(client, _csv_bytes(rows))
    body = resp.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 2
    assert "okänd kategori" in body["errors"][0]["message"]
    assert "okänd part" in body["errors"][1]["message"]

    concept = _concept_by_form(client, "resa")
    slugs = {t["taxonomy_slug"]: [v["name"] for v in t["values"]] for t in concept["taxonomies"]}
    assert slugs == {"kategorier": ["Drift"], "parts": ["Del 2 — Network"]}
