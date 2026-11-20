"""app/search.py — what matches a query and in what order (site and MCP)."""

from __future__ import annotations

from datetime import timedelta

from app.models import Branch, utcnow
from tests.test_api import _create_concept

ANON = {"X-User": ""}


def _age_main_branch(db, concept_id: str, *, days_ago: int) -> None:
    """Date the concept's entry into the bank (its main branch) back in time."""
    branch = db.query(Branch).filter(Branch.concept_id == concept_id, Branch.name == "main").one()
    branch.created_at = utcnow() - timedelta(days=days_ago)
    db.commit()


def _ids(client, **params) -> list[str]:
    resp = client.get("/api/v1/concepts", params=params, headers=ANON)
    assert resp.status_code == 200, resp.text
    return [item["id"] for item in resp.json()["items"]]


def test_equal_names_come_oldest_first(client, db, collection):
    # Written newest-first, then dated so that the LAST one written is the
    # oldest: the order must follow the dates, not the order rows were stored.
    newest = _create_concept(client, collection.id, form="zon", definition="Tredje.")
    middle = _create_concept(client, collection.id, form="zon", definition="Andra.")
    oldest = _create_concept(client, collection.id, form="zon", definition="Första.")
    _age_main_branch(db, middle["id"], days_ago=10)
    _age_main_branch(db, oldest["id"], days_ago=20)

    expected = [oldest["id"], middle["id"], newest["id"]]
    assert _ids(client, q="zon") == expected
    # The browse list (no query) breaks ties the same way.
    assert _ids(client) == expected
    # …so paging neither repeats nor skips an entry.
    assert [_ids(client, q="zon", limit=1, offset=n)[0] for n in range(3)] == expected


def test_query_whitespace_is_ignored(client, collection):
    _create_concept(client, collection.id, form="biljettresa")
    _create_concept(client, collection.id, form="biljett")
    _create_concept(client, collection.id, form="zon", definition="Gäller som biljett.")

    plain = _ids(client, q="biljett")
    assert len(plain) == 3
    assert _ids(client, q="  biljett ") == plain
    # Only whitespace is no query at all: the whole browse list.
    assert _ids(client, q="   ") == _ids(client)


def test_case_is_ignored_for_swedish_letters_too(client, collection):
    # One concept per band of the order, each spelling Å Ä Ö in another case
    # than the query: SQLite's own lower() and LIKE only fold A–Z.
    exact = _create_concept(client, collection.id, form="Ändhållplats", definition="Sist.")
    starts = _create_concept(client, collection.id, form="ÄNDHÅLLPLATSLÄGE", definition="Läge.")
    contains = _create_concept(client, collection.id, form="Linjens ändhållplats")
    in_definition = _create_concept(
        client, collection.id, form="Vändslinga", definition="Finns vid en ÄNDHÅLLPLATS."
    )
    _create_concept(client, collection.id, form="Övergång", definition="Byte.")

    expected = [exact["id"], starts["id"], contains["id"], in_definition["id"]]
    for q in ("ändhållplats", "ÄNDHÅLLPLATS", "Ändhållplats", "äNDHåLLPLATS"):
        assert _ids(client, q=q) == expected, q
