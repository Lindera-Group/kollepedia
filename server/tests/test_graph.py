"""Unit tests for the version-graph service (app/graph.py)."""

import random

import pytest
from fastapi import HTTPException

from app import graph
from app.models import Branch, Version, VersionEdge


def _make_concept(db, collection, form="hållplats", definition="En plats där bussar stannar."):
    concept, version, branch = graph.create_concept(
        db,
        collection_id=collection.id,
        canonical_form=form,
        definition_md=definition,
    )
    db.commit()
    return concept, version, branch


def test_create_concept_sets_main_head(db, collection):
    concept, version, branch = _make_concept(db, collection)

    assert version.concept_id == concept.id
    assert branch.name == "main"
    assert branch.head_version_id == version.id
    # Initial version has no parent edges.
    assert db.query(VersionEdge).filter(VersionEdge.child_id == version.id).count() == 0


def test_revise_moves_head_and_keeps_old_version(db, collection):
    concept, v1, branch = _make_concept(db, collection)
    v2 = graph.add_version(
        db,
        concept=concept,
        mode="revise",
        base_version_id=v1.id,
        canonical_form="hållplats",
        definition_md="En plats där fordon i linjetrafik stannar.",
    )
    db.commit()

    db.refresh(branch)
    assert branch.head_version_id == v2.id
    old = db.get(Version, v1.id)
    assert old.definition_md == "En plats där bussar stannar."
    edge = db.query(VersionEdge).filter(VersionEdge.child_id == v2.id).one()
    assert (edge.parent_id, edge.edge_type, edge.ordinal) == (v1.id, "revised_from", 0)


def test_revise_with_stale_base_raises_409(db, collection):
    concept, v1, _branch = _make_concept(db, collection)
    graph.add_version(
        db,
        concept=concept,
        mode="revise",
        base_version_id=v1.id,
        canonical_form="hållplats",
        definition_md="v2",
    )
    db.commit()

    with pytest.raises(HTTPException) as exc:
        graph.add_version(
            db,
            concept=concept,
            mode="revise",
            base_version_id=v1.id,  # stale: no longer the head
            canonical_form="hållplats",
            definition_md="v3",
        )
    assert exc.value.status_code == 409


def test_branch_requires_branch_name(db, collection):
    concept, v1, _branch = _make_concept(db, collection)
    with pytest.raises(HTTPException) as exc:
        graph.add_version(
            db,
            concept=concept,
            mode="branch",
            base_version_id=v1.id,
            canonical_form="hållplats",
            definition_md="gren",
        )
    assert exc.value.status_code == 422


def test_branch_creates_new_branch_with_own_head(db, collection):
    concept, v1, main = _make_concept(db, collection)
    bv = graph.add_version(
        db,
        concept=concept,
        mode="branch",
        base_version_id=v1.id,
        branch_name="alternativ-tolkning",
        canonical_form="hållplats",
        definition_md="En avvikande tolkning.",
    )
    db.commit()

    new_branch = (
        db.query(Branch)
        .filter(Branch.concept_id == concept.id, Branch.name == "alternativ-tolkning")
        .one()
    )
    assert new_branch.head_version_id == bv.id
    db.refresh(main)
    assert main.head_version_id == v1.id  # main untouched
    edge = db.query(VersionEdge).filter(VersionEdge.child_id == bv.id).one()
    assert (edge.parent_id, edge.edge_type) == (v1.id, "branched_from")


def test_duplicate_branch_name_raises_409(db, collection):
    concept, v1, _main = _make_concept(db, collection)
    graph.add_version(
        db,
        concept=concept,
        mode="branch",
        base_version_id=v1.id,
        branch_name="gren",
        canonical_form="hållplats",
        definition_md="a",
    )
    db.commit()
    with pytest.raises(HTTPException) as exc:
        graph.add_version(
            db,
            concept=concept,
            mode="branch",
            base_version_id=v1.id,
            branch_name="gren",
            canonical_form="hållplats",
            definition_md="b",
        )
    assert exc.value.status_code == 409


def test_synthesize_creates_ordered_parent_edges_and_moves_head(db, collection):
    concept, v1, main = _make_concept(db, collection)
    bv = graph.add_version(
        db,
        concept=concept,
        mode="branch",
        base_version_id=v1.id,
        branch_name="gren",
        canonical_form="hållplats",
        definition_md="grentext",
    )
    sv = graph.add_version(
        db,
        concept=concept,
        mode="synthesize",
        base_version_id=v1.id,  # main head
        extra_parent_ids=[bv.id],
        canonical_form="hållplats",
        definition_md="syntes av båda",
    )
    db.commit()

    edges = (
        db.query(VersionEdge)
        .filter(VersionEdge.child_id == sv.id)
        .order_by(VersionEdge.ordinal)
        .all()
    )
    assert [(e.parent_id, e.edge_type, e.ordinal) for e in edges] == [
        (v1.id, "synthesized_from", 0),
        (bv.id, "synthesized_from", 1),
    ]
    db.refresh(main)
    assert main.head_version_id == sv.id


def test_promote_copies_content_and_links_lineage(db, collection):
    concept, v1, main = _make_concept(db, collection, definition="ursprunglig text")
    v2 = graph.add_version(
        db,
        concept=concept,
        mode="revise",
        base_version_id=v1.id,
        canonical_form="hållplats",
        definition_md="nyare text",
    )
    promoted = graph.promote(db, concept=concept, version_id=v1.id)
    db.commit()

    assert promoted.id not in (v1.id, v2.id)  # a brand-new version, not a pointer move
    assert promoted.definition_md == "ursprunglig text"
    db.refresh(main)
    assert main.head_version_id == promoted.id
    edges = {
        e.edge_type: e.parent_id
        for e in db.query(VersionEdge).filter(VersionEdge.child_id == promoted.id)
    }
    assert edges == {"promoted_from": v1.id, "revised_from": v2.id}


def test_status_vocabulary_has_no_endorsed(db, collection):
    """'Fastställd' is not a status (endorsement rework 2026-07-11) — it is an
    organisation's flag on a version. Legacy 'endorsed' payloads coerce to
    'proposed' at every creation point; the real vocabulary passes through."""
    assert graph.coerce_status("endorsed") == "proposed"
    for status in ("draft", "proposed", "deprecated", "superseded"):
        assert graph.coerce_status(status) == status

    concept, v1, _branch = graph.create_concept(
        db,
        collection_id=collection.id,
        canonical_form="hållplats",
        definition_md="text",
        status="endorsed",
    )
    assert v1.status == "proposed"
    v2 = graph.add_version(
        db,
        concept=concept,
        mode="revise",
        base_version_id=v1.id,
        canonical_form="hållplats",
        definition_md="nyare text",
        status="endorsed",
    )
    assert v2.status == "proposed"
    promoted = graph.promote(db, concept=concept, version_id=v1.id, status="endorsed")
    db.commit()
    assert promoted.status == "proposed"


def test_promote_with_content_overrides_edits_the_restored_text(db, collection):
    """The 'edit a historical version' flow: promote carries edits but keeps
    the promote lineage (promoted_from old + revised_from previous head)."""
    concept, v1, main = _make_concept(db, collection, definition="ursprunglig text")
    v2 = graph.add_version(
        db,
        concept=concept,
        mode="revise",
        base_version_id=v1.id,
        canonical_form="hållplats",
        definition_md="nyare text",
    )
    promoted = graph.promote(
        db,
        concept=concept,
        version_id=v1.id,
        canonical_form="hållplatsområde",
        definition_md="ursprunglig text, putsad",
        tags=["Infrastruktur"],
        status="proposed",
    )
    db.commit()

    assert promoted.canonical_form == "hållplatsområde"
    assert promoted.definition_md == "ursprunglig text, putsad"
    assert promoted.tags == ["Infrastruktur"]
    assert promoted.status == "proposed"
    db.refresh(main)
    assert main.head_version_id == promoted.id
    edges = {
        e.edge_type: e.parent_id
        for e in db.query(VersionEdge).filter(VersionEdge.child_id == promoted.id)
    }
    assert edges == {"promoted_from": v1.id, "revised_from": v2.id}


def test_translated_from_at_concept_creation(db, collection):
    _sv_concept, sv_version, _b = _make_concept(db, collection, form="hållplats")
    _en_concept, en_version, _b2 = graph.create_concept(
        db,
        collection_id=collection.id,
        canonical_form="stop",
        language="en",
        definition_md="A place where vehicles stop.",
        translated_from_version_id=sv_version.id,
    )
    db.commit()

    edge = db.query(VersionEdge).filter(VersionEdge.child_id == en_version.id).one()
    assert (edge.parent_id, edge.edge_type) == (sv_version.id, "translated_from")


def test_random_operation_sequence_stays_acyclic(db, collection):
    """15 mixed operations, then verify the lineage DAG has no cycles and
    every non-initial version carries at least one parent edge."""
    rng = random.Random(1337)
    concept, v1, main = _make_concept(db, collection)
    branch_count = 0

    def versions():
        return db.query(Version).filter(Version.concept_id == concept.id).all()

    for i in range(15):
        op = rng.choice(["revise", "branch", "synthesize", "promote"])
        all_versions = versions()
        concept_branches = db.query(Branch).filter(Branch.concept_id == concept.id).all()
        heads = [b for b in concept_branches if b.head_version_id]
        if op == "revise":
            branch = rng.choice(heads)
            graph.add_version(
                db,
                concept=concept,
                mode="revise",
                base_version_id=branch.head_version_id,
                canonical_form="hållplats",
                definition_md=f"revision {i}",
            )
        elif op == "branch":
            branch_count += 1
            graph.add_version(
                db,
                concept=concept,
                mode="branch",
                base_version_id=rng.choice(all_versions).id,
                branch_name=f"gren-{branch_count}",
                canonical_form="hållplats",
                definition_md=f"gren {i}",
            )
        elif op == "synthesize":
            branch = rng.choice(heads)
            extra = rng.choice(all_versions)
            graph.add_version(
                db,
                concept=concept,
                mode="synthesize",
                base_version_id=branch.head_version_id,
                extra_parent_ids=[extra.id],
                canonical_form="hållplats",
                definition_md=f"syntes {i}",
            )
        else:  # promote
            db.refresh(main)
            candidates = [v for v in all_versions if v.id != main.head_version_id]
            if not candidates:
                continue
            graph.promote(db, concept=concept, version_id=rng.choice(candidates).id)
    db.commit()

    all_versions = versions()
    assert len(all_versions) > 10
    edges = (
        db.query(VersionEdge)
        .filter(VersionEdge.child_id.in_([v.id for v in all_versions]))
        .all()
    )
    parents: dict[str, list[str]] = {}
    for e in edges:
        parents.setdefault(e.child_id, []).append(e.parent_id)

    # Every non-initial version has at least one parent edge.
    for v in all_versions:
        if v.id != v1.id:
            assert parents.get(v.id), f"version {v.id} has no parent edge"

    # Walking parent edges from every version terminates without revisiting
    # a node on the current path (no cycles).
    def assert_acyclic_from(start: str) -> None:
        stack = [(start, iter(parents.get(start, [])))]
        on_path = {start}
        steps = 0
        while stack:
            steps += 1
            assert steps < 10_000, "walk did not terminate"
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                stack.pop()
                on_path.discard(node)
                continue
            assert nxt not in on_path, f"cycle through {nxt}"
            stack.append((nxt, iter(parents.get(nxt, []))))
            on_path.add(nxt)

    for v in all_versions:
        assert_acyclic_from(v.id)
