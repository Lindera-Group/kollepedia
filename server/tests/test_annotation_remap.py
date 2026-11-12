"""Annotation remapping through the version DAG (paket A).

Section structure and per-span author attribution are stand-off annotations
with character offsets on immutable versions. Every version-creation path
(revise/branch/synthesize/translate/promote in app/graph.py) must carry them
forward through a word-level diff: unchanged text keeps its attribution,
shrunk spans shrink, removed spans drop, and inserted text belongs to the
new version's author (DAG blame). Without this, the first edit of a migrated
Ordbok concept silently loses its per-section bylines.
"""

from app.annotations import SpanMap
from app.models import Annotation, User

# --------------------------------------------------------------------------
# Unit level: the offset mapping itself
# --------------------------------------------------------------------------


def test_spanmap_pure_append_keeps_offsets():
    old = "En hållplats är en plats."
    new = old + " Här stannar fordon."
    span = SpanMap(old, new).remap(3, 13)  # "hållplats "
    assert span == (3, 13)


def test_spanmap_insertion_before_shifts_offsets():
    old = "hållplats är en plats"
    new = "En modern hållplats är en plats"
    start, end = SpanMap(old, new).remap(0, 9)  # "hållplats"
    assert new[start:end].startswith("hållplats")
    assert start == 10


def test_spanmap_partial_edit_shrinks_to_surviving_text():
    old = "Första meningen. Andra meningen. Tredje meningen."
    new = "Första meningen. Helt ny mitt. Tredje meningen."
    # Span covered sentences 2-3; sentence 2 was rewritten → survives as 3
    # (surviving edge whitespace may ride along — harmless for rendering).
    start, end = SpanMap(old, new).remap(17, 50)
    assert new[start:end].strip() == "Tredje meningen."


def test_spanmap_fully_removed_span_drops():
    old = "Kvarvarande text. Borttagen sektion här."
    new = "Kvarvarande text."
    assert SpanMap(old, new).remap(18, 40) is None


def test_spanmap_full_rewrite_drops_everything():
    assert SpanMap("helt gammal text", "totally new words").remap(0, 16) is None


def test_spanmap_multibyte_offsets_are_code_points():
    # å/ä/ö are single code points — offsets must not drift (parity with the
    # frontend's string slicing in lib/sections/sections.ts).
    old = "Åkeriägarnas färdtjänst är öppen."
    new = "Åkeriägarnas färdtjänst är öppen. Ny mening."
    start, end = SpanMap(old, new).remap(13, 24)
    assert new[start:end] == old[13:24] == "färdtjänst "


# --------------------------------------------------------------------------
# API level: annotations survive a revise and a section deletion
# --------------------------------------------------------------------------


def _create_concept(client, collection_id, definition_md, form="hållplats"):
    resp = client.post(
        "/api/v1/concepts",
        json={
            "collection_id": collection_id,
            "canonical_form": form,
            "definition_md": definition_md,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _annotate(db, version_id, attr_type, start, end, value):
    db.add(
        Annotation(version_id=version_id, attr_type=attr_type, start=start, end=end, value=value)
    )
    db.commit()


def _revise(client, concept, definition_md):
    resp = client.post(
        f"/api/v1/concepts/{concept['id']}/versions",
        json={
            "mode": "revise",
            "base_version_id": concept["head"]["id"],
            "canonical_form": concept["head"]["canonical_form"],
            "definition_md": definition_md,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


SECTION_1 = "Huvuddefinitionen av begreppet."
SECTION_2 = "En fördjupande sektion av Greta."
TWO_SECTIONS = f"{SECTION_1}\n\n{SECTION_2}"


def test_revise_carries_section_and_author_annotations(client, db, collection):
    concept = _create_concept(client, collection.id, TWO_SECTIONS)
    head_id = concept["head"]["id"]
    greta = User(handle="greta", display_name="Greta Garbo", affiliation="K2")
    db.add(greta)
    db.commit()
    s2_start = len(SECTION_1) + 2
    _annotate(db, head_id, "section", 0, len(SECTION_1), {"number": "0", "title": None})
    _annotate(
        db,
        head_id,
        "author",
        s2_start,
        len(TWO_SECTIONS),
        {"name": "Greta Garbo", "user_id": greta.id, "handle": "greta"},
    )

    # Append a sentence to section 1 — both annotations must survive.
    new_text = f"{SECTION_1} Ett tillägg av redaktören.\n\n{SECTION_2}"
    version = _revise(client, concept, new_text)

    remapped = {a["attr_type"]: a for a in version["annotations"]}
    assert set(remapped) == {"section", "author"}

    author = remapped["author"]
    assert new_text[author["start"] : author["end"]] == SECTION_2
    assert author["value"]["handle"] == "greta"

    section = remapped["section"]
    assert new_text[section["start"] : section["end"]] == SECTION_1


def test_revise_drops_annotations_of_deleted_section(client, db, collection):
    concept = _create_concept(client, collection.id, TWO_SECTIONS, form="linje")
    head_id = concept["head"]["id"]
    s2_start = len(SECTION_1) + 2
    _annotate(db, head_id, "author", s2_start, len(TWO_SECTIONS), {"name": "Greta Garbo"})
    _annotate(db, head_id, "section", 0, len(SECTION_1), {"number": "0"})

    # Delete section 2 entirely — its author annotation must NOT follow.
    version = _revise(client, concept, SECTION_1)

    types = [a["attr_type"] for a in version["annotations"]]
    assert types == ["section"]
    assert version["annotations"][0]["provenance"] == {
        "kind": "remap",
        "from_version": head_id,
    }


def test_remap_chains_across_multiple_revisions(client, db, collection):
    concept = _create_concept(client, collection.id, TWO_SECTIONS, form="tur")
    head_id = concept["head"]["id"]
    s2_start = len(SECTION_1) + 2
    _annotate(db, head_id, "author", s2_start, len(TWO_SECTIONS), {"name": "Greta Garbo"})

    v2_text = f"Inledning.\n\n{TWO_SECTIONS}"
    v2 = _revise(client, {"id": concept["id"], "head": concept["head"]}, v2_text)
    v3_text = f"Inledning.\n\n{SECTION_1}\n\nMittsektion.\n\n{SECTION_2}"
    v3 = _revise(client, {"id": concept["id"], "head": v2}, v3_text)

    authors = [a for a in v3["annotations"] if a["attr_type"] == "author"]
    assert len(authors) == 1
    start, end = authors[0]["start"], authors[0]["end"]
    assert v3_text[start:end] == SECTION_2
