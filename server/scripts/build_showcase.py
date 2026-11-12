"""Build the "Tidsmaskinen" demo collection — the front-page showcase.

Runs AFTER scripts/migrate_from_prototype.py and only adds data (re-running it
first removes and rebuilds the tidsmaskinen collection itself; the migrated
collections are never touched).

Three kinds of content:

1. Eight stitched concepts: Swedish terms that exist in several migrated source
   collections get ONE concept whose main-branch history replays the source
   definitions chronologically by collection year. Where a term exists in only
   two eligible collections it is completed either with the Transmodel
   definition (found via the migrated translated_from edges) or with a
   hand-written intermediate revision. Three of the richest concepts also get
   a branch ("alternativ-tolkning") carrying Nordisk Resesamordning's divergent reading
   plus an AI-marked synthesis back onto main.
2. Acceptance concept A ("realtidsinformation"): 13 main versions, 2008→2026,
   uneven spacing, 7 authors, tiny/medium/large edits, a title change, tag
   churn, status arc draft→proposed→endorsed→proposed, a promote, a branch
   ("regional-tolkning") and a synthesis.
3. Acceptance concept B ("anropsstyrd trafik"): 7 versions, 6 authors.

Usage: uv run python scripts/build_showcase.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import graph  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Annotation,
    Branch,
    Collection,
    Concept,
    ConceptRelation,
    Endorsement,
    ListItem,
    User,
    Version,
    VersionEdge,
)

MIGRATED_SLUGS = [
    "kollektivtrafikordboken-2008",
    "kollepedia-2012",
    "transmodel-2021",
    "ordbok-framtidens-resande-2024",
    "samtrafiken-begreppslista-2024",
    "trafikverket-jarnvagstermer-2025",
]

SLUG_TO_HANDLE = {
    "kollektivtrafikordboken-2008": "branschordboksredaktionen",
    "kollepedia-2012": "kollepedia-gemenskapen",
    "transmodel-2021": "referensmodellgruppen",
    "ordbok-framtidens-resande-2024": "irf-forskargruppen",
    "samtrafiken-begreppslista-2024": "resesamordningen-redaktionen",
    "trafikverket-jarnvagstermer-2025": "sparinfrastrukturverket-redaktionen",
}

DEMO_USERS: dict[str, tuple[str, str]] = {
    "branschordboksredaktionen": ("KTO-redaktionen", "Kollektivtrafikbranschens samorganisation"),
    "kollepedia-gemenskapen": ("Kollepedia-gemenskapen", "kollepedia.se"),
    "referensmodellgruppen": ("Transmodel WG3", "ESR – Europeiska standardgruppen för resedata"),
    "irf-forskargruppen": (
        "IRF forskargruppen",
        "IRF – Institutet för resandeforskning",
    ),
    "resesamordningen-redaktionen": ("Nordisk Resesamordning", "Nordisk Resesamordning AB"),
    "sparinfrastrukturverket-redaktionen": ("Spårinfrastrukturverket", "Spårinfrastrukturverket"),
    "harmoniserings-boten": ("Harmonisering (AI-utkast)", "Kollepedia NG"),
    # Acceptance-demo editors (word-level blame needs many hands).
    "agnes-lovdal": ("Agnes Lövdal", "Sydlänstrafiken"),
    "elis-storback": ("Elis Storbäck", "Mälardalstrafik"),
    "miriam-hook": ("Miriam Höök", "Västlänstrafiken"),
    "jakob-renhagen": ("Jakob Renhagen", "Spårinfrastrukturverket"),
    "signe-akerlind": ("Signe Åkerlind", "IRF"),
    "linnea-fjallmark": ("Linnea Fjällmark", "Nordbanan"),
}

LLM_PROVENANCE = {
    "kind": "llm",
    "model": "claude-fable-5",
    "provider": "anthropic",
    "prompt_id": "harmonise-v1",
}

BRANCH_DATE = datetime(2024, 9, 15)
SYNTHESIS_DATE = datetime(2026, 5, 20)

# Classic concepts first (spec preference), then strong fallbacks.
PREFERRED = [
    "hållplats",
    "linje",
    "resa",
    "biljett",
    "taxa",
    "bytespunkt",
    "trafikutbud",
    "reseplanerare",
    "färdbevis",
    "tidtabell",
    "zon",
    "förare",
    "försening",
    "ankomst",
    "kund",
    "resenär",
]

# Hand-written intermediate revisions for terms that only exist in two
# eligible collections (so every showcase concept reaches >= 3 versions).
INTERMEDIATES: dict[str, dict] = {
    "bytespunkt": {
        "year": 2018,
        "date": datetime(2018, 6, 15),
        "author": "kollepedia-gemenskapen",
        "definition": (
            "Med bytespunkt avses en hållplats eller terminal som trafikeras av flera "
            "linjer och där byte är planerat för resenärerna. Bytespunkter lokaliseras "
            "till viktiga knutpunkter i linjenätet för buss- och spårtrafik, och "
            "utformningen ska minimera bytesmotståndet: korta gångvägar, god "
            "orienterbarhet och väderskydd. Eftersom ett byte alltid betraktas som en "
            "uppoffring för resenären är samordnade tidtabeller vid bytespunkterna "
            "centralt."
        ),
        "note": (
            "Redaktionell revidering: bytesmotstånd och tidtabellssamordning "
            "förtydligade; språklig modernisering."
        ),
    },
    "tidtabell": {
        "year": 2016,
        "date": datetime(2016, 6, 15),
        "author": "branschordboksredaktionen",
        "definition": (
            "En plan för trafikturer som anger när fordonen avgår från och ankommer "
            "till linjens hållplatser, med minst den information som behövs för att "
            "informera passagerarna. Tidtabellen publiceras allt oftare digitalt och "
            "kompletteras med realtidsinformation om faktiska avgångs- och "
            "ankomsttider."
        ),
        "note": (
            "Reviderad: digital publicering och realtidsinformation tillagd; "
            "formuleringen om tryckta dokument nedtonad."
        ),
    },
    "färdbevis": {
        "year": 2016,
        "date": datetime(2016, 9, 15),
        "author": "branschordboksredaktionen",
        "definition": (
            "Bevis på rätten att konsumera en kollektivtrafiktjänst, köpt eller "
            "tillhandahållen utan kostnad. Färdbeviset har historiskt varit i "
            "pappersformat men bärs allt oftare som plastkort eller i digital form i "
            "mobiltelefonen."
        ),
        "note": "Reviderad: digitala bärare (kort, mobil) tillagda vid sidan av pappersbiljetten.",
    },
    "försening": {
        "year": 2019,
        "date": datetime(2019, 6, 15),
        "author": "kollepedia-gemenskapen",
        "definition": (
            "Den tid som ett fordon i kollektivtrafik ligger efter sin tidtabell. Inom "
            "järnvägen räknas fjärrtåg vanligen som försenade från fem minuter efter "
            "tidtabellstid, regionaltåg från cirka tre minuter och godståg från femton "
            "minuter. Begreppet används alltmer även om avvikelser från beräknad tid i "
            "realtidsinformationen."
        ),
        "note": (
            "Reviderad: breddad från enbart tåg till kollektivtrafik i allmänhet; "
            "realtidsperspektiv tillagt."
        ),
    },
}

# The three richest concepts get a branch (Nordisk Resesamordning's divergent reading)
# and an AI-drafted synthesis on main. Texts are hand-written merges of the
# two parents' substance.
SYNTHESIS_TEXTS: dict[str, str] = {
    "linje": (
        "En linje är en namngiven eller numrerad grupp av körmönster som trafikeras "
        "regelbundet och är känd för allmänheten under ett gemensamt namn eller "
        "nummer. Linjen har en tidsmässig dimension (tidtabell) och en geografisk "
        "(linjesträckning med hållplatssekvens), och resenärer kan stiga på och av "
        "vid linjens hållplatser eller stationer. En linje kan passera hållplatser "
        "där den inte gör planmässigt uppehåll."
    ),
    "hållplats": (
        "En plats där fordon i linjetrafik gör uppehåll för att släppa av och ta "
        "ombord passagerare, ofta markerad med stolpe med topptavla eller "
        "väderskydd. Vid hållplatsen kan det finnas vänteplats och anslutande "
        "parkering, och utformningen varierar från enkel fickhållplats till avskild "
        "hållplats. Inom järnvägen avses en plats på linjen för av- och påstigning "
        "utan växel eller rörlig bro i huvudspåret."
    ),
    "bytespunkt": (
        "Ett samlingsnamn för hållplatser och resecentrum där byte mellan linjer "
        "eller trafikslag är planerat för resenärerna. Bytespunkter lokaliseras till "
        "viktiga knutpunkter i linjenätet, och utformning och utrustning följer vad "
        "som gäller för hållplatser eller terminaler beroende på punktens storlek. "
        "Eftersom ett byte är en stor uppoffring för resenären är god utformning och "
        "tidtabellssamordning vid bytespunkten avgörande för resans kvalitet."
    ),
}


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def edited(base: str, old: str, new: str) -> str:
    assert old in base, f"edit target not found: {old[:50]!r}"
    return base.replace(old, new)


def get_or_create_user(db: Session, handle: str) -> User:
    user = db.query(User).filter(User.handle == handle).first()
    if user is None:
        display, affiliation = DEMO_USERS[handle]
        user = User(handle=handle, display_name=display, affiliation=affiliation)
        db.add(user)
        db.flush()
    return user


def remove_existing_showcase(db: Session) -> None:
    """Delete a previous tidsmaskinen build (explicit order: branches ↔
    versions form an FK cycle, so both pointer columns are nulled first)."""
    coll = db.query(Collection).filter(Collection.slug == "tidsmaskinen").first()
    if coll is None:
        return
    concept_ids = [c.id for c in db.query(Concept).filter(Concept.collection_id == coll.id)]
    if concept_ids:
        version_ids = [v.id for v in db.query(Version).filter(Version.concept_id.in_(concept_ids))]
        if version_ids:
            for model in (Annotation, Endorsement):
                db.query(model).filter(model.version_id.in_(version_ids)).delete(
                    synchronize_session=False
                )
            db.query(ListItem).filter(ListItem.version_id.in_(version_ids)).delete(
                synchronize_session=False
            )
            db.query(VersionEdge).filter(
                or_(
                    VersionEdge.child_id.in_(version_ids),
                    VersionEdge.parent_id.in_(version_ids),
                )
            ).delete(synchronize_session=False)
        db.query(ListItem).filter(ListItem.concept_id.in_(concept_ids)).delete(
            synchronize_session=False
        )
        db.query(ConceptRelation).filter(
            or_(
                ConceptRelation.from_concept_id.in_(concept_ids),
                ConceptRelation.to_concept_id.in_(concept_ids),
            )
        ).delete(synchronize_session=False)
        db.query(Branch).filter(Branch.concept_id.in_(concept_ids)).update(
            {Branch.head_version_id: None}, synchronize_session=False
        )
        db.query(Version).filter(Version.concept_id.in_(concept_ids)).update(
            {Version.branch_id: None}, synchronize_session=False
        )
        db.flush()
        db.query(Version).filter(Version.concept_id.in_(concept_ids)).delete(
            synchronize_session=False
        )
        db.query(Branch).filter(Branch.concept_id.in_(concept_ids)).delete(
            synchronize_session=False
        )
        db.query(Concept).filter(Concept.id.in_(concept_ids)).delete(synchronize_session=False)
    db.delete(coll)
    db.commit()
    print("Removed existing tidsmaskinen collection (rebuild).")


def load_source_heads(db: Session) -> dict[str, dict]:
    """slug → {lower(canonical_form) → source entry} for main-branch heads."""
    rows = (
        db.query(Version, Concept, Collection)
        .join(Concept, Concept.id == Version.concept_id)
        .join(Branch, (Branch.concept_id == Concept.id) & (Branch.name == "main"))
        .join(Collection, Collection.id == Concept.collection_id)
        .filter(Branch.head_version_id == Version.id, Collection.slug.in_(MIGRATED_SLUGS))
        .all()
    )
    by_slug: dict[str, dict] = defaultdict(dict)
    for version, concept, collection in rows:
        entry = {
            "slug": collection.slug,
            "name": collection.name,
            "year": collection.year,
            "version": version,
            "concept": concept,
        }
        by_slug[collection.slug].setdefault(version.canonical_form.lower(), entry)
    return by_slug


def eligible_entries(by_slug: dict[str, dict], form: str) -> list[dict]:
    """Swedish sources with a >=100-char definition, deduped on identical text."""
    entries = []
    for slug in MIGRATED_SLUGS:
        entry = by_slug[slug].get(form)
        if entry is None:
            continue
        version = entry["version"]
        if version.language != "sv" or len(version.definition_md) < 100:
            continue
        entries.append(entry)
    entries.sort(key=lambda e: (e["year"], MIGRATED_SLUGS.index(e["slug"])))
    seen: set[str] = set()
    distinct = []
    for entry in entries:
        key = normalize(entry["version"].definition_md)
        if key in seen:
            continue  # e.g. Kollepedia 2012 inherited KTO texts verbatim
        seen.add(key)
        distinct.append(entry)
    return distinct


def transmodel_bridge(db: Session, entries: list[dict], by_slug: dict[str, dict]) -> dict | None:
    """KTO sv term → translated_from edge → en form → Transmodel concept."""
    kto = next((e for e in entries if e["slug"] == "kollektivtrafikordboken-2008"), None)
    if kto is None:
        return None
    edges = (
        db.query(VersionEdge)
        .filter(
            VersionEdge.parent_id == kto["version"].id,
            VersionEdge.edge_type == "translated_from",
        )
        .all()
    )
    en_forms = sorted(
        {
            child.canonical_form.lower()
            for child in (db.get(Version, e.child_id) for e in edges)
            if child is not None
        }
    )
    tm = by_slug["transmodel-2021"]
    for form in en_forms:
        entry = tm.get(form)
        if entry is not None and len(entry["version"].definition_md) >= 100:
            return entry
    return None


def select_showcase_forms(db: Session, by_slug: dict[str, dict]) -> list[str]:
    forms = {form for slug_map in by_slug.values() for form in slug_map}
    cands = {form: eligible_entries(by_slug, form) for form in forms}
    three_plus = sorted(
        (f for f, e in cands.items() if len(e) >= 3),
        key=lambda f: (PREFERRED.index(f) if f in PREFERRED else 99, f),
    )
    picks = list(three_plus)
    for form in PREFERRED:
        if len(picks) >= 8:
            break
        if form in picks or len(cands.get(form, [])) != 2:
            continue
        # Only fill with terms we can complete to >= 3 versions.
        if form in INTERMEDIATES or transmodel_bridge(db, cands[form], by_slug):
            picks.append(form)
    assert len(picks) == 8, f"expected 8 showcase picks, got {picks}"
    return picks


def add_endorsement(db: Session, version: Version, body: str, note: str, stamped_by: User) -> None:
    db.add(
        Endorsement(
            version_id=version.id,
            body=body,
            note=note,
            stamped_by=stamped_by.id,
            created_at=version.created_at,
        )
    )


def build_stitched_concept(
    db: Session,
    showcase: Collection,
    form: str,
    entries: list[dict],
    by_slug: dict[str, dict],
) -> tuple[Concept, int, int]:
    branch_entry = None
    if form in SYNTHESIS_TEXTS:
        branch_entry = next(
            (e for e in entries if e["slug"] == "samtrafiken-begreppslista-2024"), None
        )
    main_entries = [e for e in entries if e is not branch_entry]
    tm_entry = transmodel_bridge(db, main_entries, by_slug)
    if tm_entry is not None:
        main_entries.append(tm_entry)

    events: list[dict] = [{"kind": "source", **e} for e in main_entries]
    if form in INTERMEDIATES:
        events.append({"kind": "intermediate", **INTERMEDIATES[form]})
    events.sort(key=lambda ev: ev["year"])

    first = events[0]
    assert first["kind"] == "source"
    v1 = first["version"]
    concept, version, _branch = graph.create_concept(
        db,
        collection_id=showcase.id,
        canonical_form=v1.canonical_form,
        language="sv",
        definition_md=v1.definition_md,
        status="proposed",
        tags=list(v1.tags or []),
        note=f"Ursprunglig definition ur {first['name']} ({first['year']})",
        provenance={"kind": "import", "source": first["slug"]},
        created_by=get_or_create_user(db, SLUG_TO_HANDLE[first["slug"]]).id,
        created_at=datetime(first["year"], 3, 15),
    )
    main_versions = [version]
    sources_used = [first]

    for i, event in enumerate(events[1:], start=1):
        if event["kind"] == "source":
            src = event["version"]
            is_tm = event["slug"] == "transmodel-2021"
            note = (
                f"Reviderad mot Transmodel/EN 12896 ({event['year']}): harmoniserad med "
                f"det europeiska referensbegreppet '{src.canonical_form}'."
                if is_tm
                else (
                    f"Reviderad mot {event['name']} ({event['year']}): definitionen "
                    "uppdaterad till källans lydelse."
                )
            )
            new_version = graph.add_version(
                db,
                concept=concept,
                mode="revise",
                base_version_id=main_versions[-1].id,
                canonical_form=src.canonical_form,
                definition_md=src.definition_md,
                status="endorsed" if is_tm else "proposed",
                tags=list(src.tags or []),
                note=note,
                provenance={"kind": "import", "source": event["slug"]},
                created_by=get_or_create_user(db, SLUG_TO_HANDLE[event["slug"]]).id,
                created_at=datetime(event["year"], (3 + 2 * i) % 12, 15),
            )
            if is_tm:
                add_endorsement(
                    db,
                    new_version,
                    body="ESR / Transmodel",
                    note="Motsvarar EN 12896-begrepp",
                    stamped_by=get_or_create_user(db, "referensmodellgruppen"),
                )
            sources_used.append(event)
        else:
            new_version = graph.add_version(
                db,
                concept=concept,
                mode="revise",
                base_version_id=main_versions[-1].id,
                canonical_form=main_versions[-1].canonical_form,
                definition_md=event["definition"],
                status="proposed",
                tags=list(main_versions[-1].tags or []),
                note=event["note"],
                provenance={"kind": "human"},
                created_by=get_or_create_user(db, event["author"]).id,
                created_at=event["date"],
            )
        main_versions.append(new_version)

    branch_count = 0
    if branch_entry is not None:
        branch_count = 1
        candidates = [v for v in main_versions if v.created_at < BRANCH_DATE]
        base = candidates[min(1, len(candidates) - 1)]  # "the v2 or middle version"
        src = branch_entry["version"]
        branch_head = graph.add_version(
            db,
            concept=concept,
            mode="branch",
            branch_name="alternativ-tolkning",
            base_version_id=base.id,
            canonical_form=src.canonical_form,
            definition_md=src.definition_md,
            status="proposed",
            tags=list(src.tags or []),
            note=(
                f"Gren: avvikande läsart ur {branch_entry['name']} "
                f"({branch_entry['year']}) — den operativa branschtolkningen skiljer "
                "sig från huvudlinjens."
            ),
            provenance={"kind": "import", "source": branch_entry["slug"]},
            created_by=get_or_create_user(db, SLUG_TO_HANDLE[branch_entry["slug"]]).id,
            created_at=BRANCH_DATE,
        )
        sources_used.append(branch_entry)

        head = main_versions[-1]
        synthesis = graph.add_version(
            db,
            concept=concept,
            mode="synthesize",
            base_version_id=head.id,
            extra_parent_ids=[branch_head.id],
            canonical_form=head.canonical_form,
            definition_md=SYNTHESIS_TEXTS[form],
            status="draft",
            tags=sorted(set(head.tags or []) | set(branch_head.tags or [])),
            note=(
                "AI-utkast: syntes av huvudlinjen och grenen 'alternativ-tolkning'. "
                "Kräver mänsklig granskning."
            ),
            provenance=dict(LLM_PROVENANCE),
            created_by=get_or_create_user(db, "harmoniserings-boten").id,
            created_at=SYNTHESIS_DATE,
        )
        main_versions.append(synthesis)

    for event in sources_used:
        db.add(
            ConceptRelation(
                relation_type="exact_match",
                from_concept_id=concept.id,
                to_concept_id=event["concept"].id,
                note=f"Källbegrepp för versionen från {event['year']}",
                provenance={"kind": "import", "source": "build_showcase"},
            )
        )
    db.flush()
    total_versions = len(main_versions) + branch_count
    assert total_versions >= 3, f"{form}: only {total_versions} versions"
    return concept, total_versions, branch_count


# --------------------------------------------------------------------------
# Acceptance concept A: realtidsinformation (13 main versions, 2 branch).
# --------------------------------------------------------------------------


def build_acceptance_a(db: Session, showcase: Collection) -> tuple[Concept, int, int]:
    u = {h: get_or_create_user(db, h) for h in DEMO_USERS}

    a1 = (
        "Information om trafikläget som uppdateras löpande och visas för resenärer "
        "på skyltar vid hållplatser. Uppgifterna hämtas från fordonens radiosystem "
        "och anger beräknad ankomsttid i minuter. Systemet omfattar i dag endast "
        "stombussar i innerstaden."
    )
    a2 = edited(a1, "radiosystem", "positioneringssystem")
    a3 = edited(
        a2,
        "i minuter. Systemet",
        "i minuter. Prognoserna räknas om varje gång fordonet passerar en mätpunkt "
        "längs linjen. Systemet",
    )
    a4 = (
        "Trafikinformation som beskriver det faktiska trafikläget och uppdateras "
        "kontinuerligt utifrån fordonens positioneringsdata. Realtidsinformation "
        "visas på hållplatsskyltar, ombord i fordonen och i mobila reseplanerare, "
        "och anger beräknad ankomst- och avgångstid. Prognoserna räknas om varje "
        "gång fordonet passerar en mätpunkt längs linjen."
    )
    a5 = edited(
        a4, "ankomst- och avgångstid.", "ankomst- och avgångstid samt eventuella störningar."
    )
    a6 = a5 + (
        " Uppgifterna tillgängliggörs allt oftare som öppna data för tredjepartsutvecklare."
    )
    a7 = a6 + (
        "\n\nInom branschsamarbetet utbyts realtidsinformation mellan "
        "trafikhuvudmännen i standardiserade format, vilket gör det möjligt att visa "
        "ett samlat trafikläge för hela landet oavsett vilken app resenären använder."
    )
    a8 = edited(
        a7,
        " Prognoserna räknas om varje gång fordonet passerar en mätpunkt längs linjen.",
        "",
    )
    a10 = edited(a7, "mobila reseplanerare", "digitala reseplanerare")
    a11 = edited(
        a10,
        "Inom branschsamarbetet utbyts realtidsinformation mellan trafikhuvudmännen "
        "i standardiserade format, vilket gör det möjligt att visa ett samlat "
        "trafikläge för hela landet oavsett vilken app resenären använder.",
        "Genom branschgemensamma standarder utbyts realtidsinformation mellan "
        "trafikhuvudmän och operatörer, så att resenären möter samma trafikläge "
        "oavsett kanal.",
    )
    a12 = a11 + (
        " Kraven på att dela realtidsdata följer av EU:s förordning 2017/1926 om "
        "multimodala reseinformationstjänster."
    )

    tags_v1 = ["Technology & Data"]
    tags_v4 = ["Passenger Services", "Technology & Data"]
    tags_v6 = ["Operations", "Passenger Services", "Technology & Data"]
    tags_v11 = ["Passenger Services", "Technology & Data", "Urban Mobility"]

    concept, v1, _branch = graph.create_concept(
        db,
        collection_id=showcase.id,
        canonical_form="realtidsinfo",
        language="sv",
        definition_md=a1,
        status="draft",
        tags=tags_v1,
        note="Första utkast utifrån Mälardalstrafik:s skyltprojekt.",
        provenance={"kind": "human"},
        created_by=u["elis-storback"].id,
        created_at=datetime(2008, 1, 20),
    )

    def revise(base, form, text, status, tags, note, author, when, provenance=None):
        return graph.add_version(
            db,
            concept=concept,
            mode="revise",
            base_version_id=base.id,
            canonical_form=form,
            definition_md=text,
            status=status,
            tags=tags,
            note=note,
            provenance=provenance or {"kind": "human"},
            created_by=u[author].id,
            created_at=when,
        )

    v2 = revise(
        v1,
        "realtidsinfo",
        a2,
        "draft",
        tags_v1,
        "Rättelse: uppgifterna kommer från positioneringssystemet, inte radiosystemet.",
        "agnes-lovdal",
        datetime(2009, 2, 10),
    )
    v3 = revise(
        v2,
        "realtidsinfo",
        a3,
        "proposed",
        tags_v1,
        "Förtydligande av hur prognoserna beräknas; status höjd till föreslagen.",
        "elis-storback",
        datetime(2009, 3, 25),
    )
    v4 = revise(
        v3,
        "realtidsinformation",
        a4,
        "proposed",
        tags_v4,
        "Genomgripande omarbetning: begreppet breddat från skyltar till alla kanaler; "
        "termen skrivs ut i sin helhet.",
        "miriam-hook",
        datetime(2012, 6, 5),
    )
    v5 = revise(
        v4,
        "realtidsinformation",
        a5,
        "proposed",
        tags_v4,
        "Tillägg: även störningsinformation ingår.",
        "jakob-renhagen",
        datetime(2013, 4, 14),
    )
    v6 = revise(
        v5,
        "realtidsinformation",
        a6,
        "proposed",
        tags_v6,
        "Öppna data-perspektivet tillagt efter IRF:s genomgång; kategorin Operations tillagd.",
        "signe-akerlind",
        datetime(2013, 11, 2),
    )
    v7 = revise(
        v6,
        "realtidsinformation",
        a7,
        "endorsed",
        tags_v6,
        "Nytt stycke om branschgemensamt utbyte; definitionen fastställd som branschstandard.",
        "agnes-lovdal",
        datetime(2017, 9, 18),
    )
    add_endorsement(
        db,
        v7,
        body="Nordisk Resesamordning",
        note="Fastställd som branschgemensam definition",
        stamped_by=u["resesamordningen-redaktionen"],
    )
    revise(  # v8 — the controversial edit; v9 promotes v7 back over it
        v7,
        "realtidsinformation",
        a8,
        "proposed",
        tags_v6,
        "Omstridd strykning: detaljerna om prognosberäkning ansågs "
        "implementationsspecifika. Status återförd till föreslagen i väntan på ny "
        "förankring.",
        "elis-storback",
        datetime(2021, 3, 30),
    )
    v9 = graph.promote(
        db,
        concept=concept,
        version_id=v7.id,
        note=(
            "Återställning: den fastställda lydelsen från 2017 gäller tills en ny "
            "formulering förankrats."
        ),
        created_by=u["miriam-hook"].id,
        created_at=datetime(2022, 8, 22),
    )
    v10 = revise(
        v9,
        "realtidsinformation",
        a10,
        "proposed",
        tags_v6,
        "Språklig justering: 'digitala reseplanerare' täcker även webbtjänster.",
        "jakob-renhagen",
        datetime(2023, 1, 17),
    )
    v11 = revise(
        v10,
        "realtidsinformation",
        a11,
        "proposed",
        tags_v11,
        "Omskrivning av stycket om branschsamarbete; kategorier justerade.",
        "signe-akerlind",
        datetime(2023, 2, 9),
    )
    v12 = revise(
        v11,
        "realtidsinformation",
        a12,
        "proposed",
        tags_v11,
        "Anpassning till EU:s förordning 2017/1926 om multimodala reseinformationstjänster.",
        "miriam-hook",
        datetime(2024, 10, 5),
    )

    # Branch: regional reading, by yet another author.
    b1_text = (
        "Trafikinformation som beskriver det faktiska trafikläget utifrån fordonens "
        "positioneringsdata. I regional trafik med långa avstånd mellan hållplatser "
        "avser realtidsinformationen främst avvikelser från tidtabellen — försening "
        "i minuter och inställda turer — snarare än rullande minutprognoser. "
        "Informationen förmedlas via skyltar på större bytespunkter, utrop ombord "
        "och digitala kanaler."
    )
    b1 = graph.add_version(
        db,
        concept=concept,
        mode="branch",
        branch_name="regional-tolkning",
        base_version_id=v10.id,
        canonical_form="realtidsinformation",
        definition_md=b1_text,
        status="proposed",
        tags=["Passenger Services", "Technology & Data", "Transport Modes"],
        note="Regional tolkning: fokus på avvikelser snarare än minutprognoser.",
        provenance={"kind": "human"},
        created_by=u["linnea-fjallmark"].id,
        created_at=datetime(2024, 3, 12),
    )
    b2 = graph.add_version(
        db,
        concept=concept,
        mode="revise",
        base_version_id=b1.id,
        canonical_form="realtidsinformation",
        definition_md=b1_text
        + (
            " Vid ersättningstrafik ska realtidsinformationen även omfatta "
            "ersättningsfordonens läge."
        ),
        status="proposed",
        tags=["Passenger Services", "Technology & Data", "Transport Modes"],
        note="Tillägg om ersättningstrafik efter vintersäsongens erfarenheter.",
        provenance={"kind": "human"},
        created_by=u["linnea-fjallmark"].id,
        created_at=datetime(2024, 6, 20),
    )

    v13 = graph.add_version(
        db,
        concept=concept,
        mode="synthesize",
        base_version_id=v12.id,
        extra_parent_ids=[b2.id],
        canonical_form="realtidsinformation",
        definition_md=(
            "Trafikinformation som beskriver det faktiska trafikläget och uppdateras "
            "kontinuerligt utifrån fordonens positioneringsdata. "
            "Realtidsinformationen visas på hållplatsskyltar, ombord i fordonen och "
            "i digitala reseplanerare och omfattar beräknade ankomst- och "
            "avgångstider, störningar samt inställda turer. I regional trafik med "
            "långa avstånd ligger tonvikten på avvikelser från tidtabellen, och vid "
            "ersättningstrafik omfattas även ersättningsfordonens läge. Genom "
            "branschgemensamma standarder och kraven i EU:s förordning 2017/1926 "
            "möter resenären samma trafikläge oavsett kanal."
        ),
        status="draft",
        tags=sorted(set(tags_v11) | {"Transport Modes"}),
        note=(
            "AI-utkast: syntes av huvudlinjen och grenen 'regional-tolkning'. "
            "Kräver mänsklig granskning."
        ),
        provenance=dict(LLM_PROVENANCE),
        created_by=u["harmoniserings-boten"].id,
        created_at=datetime(2026, 6, 1),
    )
    assert v13 is not None
    db.flush()
    return concept, 15, 1  # 13 on main + 2 on the branch


# --------------------------------------------------------------------------
# Acceptance concept B: anropsstyrd trafik (7 versions).
# --------------------------------------------------------------------------


def build_acceptance_b(db: Session, showcase: Collection) -> tuple[Concept, int, int]:
    u = {h: get_or_create_user(db, h) for h in DEMO_USERS}

    b1 = (
        "Kollektivtrafik som endast utförs efter beställning från resenären. "
        "Turerna körs med mindre fordon och utan fast tidtabell inom ett avgränsat "
        "område."
    )
    b2 = b1 + " Beställning sker vanligen per telefon senast en timme före önskad avresa."
    b3 = edited(b2, "mindre fordon", "mindre fordon, exempelvis minibussar,")
    b4 = (
        "Kollektivtrafik som utförs först efter beställning från resenären och där "
        "rutt och tidtabell anpassas efter efterfrågan. Trafiken körs ofta med "
        "mindre fordon, exempelvis minibussar, inom ett avgränsat område eller som "
        "ersättning för linjelagd trafik i glesbygd. Beställning sker per telefon "
        "eller i app, i regel senast en timme före önskad avresa."
    )
    b5 = b4 + (
        " I storstadsområden prövas anropsstyrd trafik som komplement till "
        "stomnätet under lågtrafik."
    )
    b6 = edited(
        b5,
        "Kollektivtrafik som utförs först efter beställning",
        "Kollektivtrafik, ofta kallad DRT (demand responsive transport), som utförs "
        "först efter beställning",
    )
    b7 = edited(
        b6,
        "Beställning sker per telefon eller i app, i regel senast en timme före önskad avresa.",
        "Beställning sker i regel i app eller via reseplanerare, med telefonbokning "
        "som komplement, ofta fram till kort före avresa.",
    )

    tags1 = ["Demand-Responsive Transport"]
    tags4 = ["Demand-Responsive Transport", "Passenger Services"]
    tags5 = ["Demand-Responsive Transport", "Passenger Services", "Urban Mobility"]

    concept, version, _branch = graph.create_concept(
        db,
        collection_id=showcase.id,
        canonical_form="anropsstyrd trafik",
        language="sv",
        definition_md=b1,
        status="draft",
        tags=tags1,
        note="Första utkast.",
        provenance={"kind": "human"},
        created_by=u["signe-akerlind"].id,
        created_at=datetime(2011, 5, 10),
    )
    plan = [
        (
            b2,
            "proposed",
            tags1,
            "Bokningsförfarandet beskrivet.",
            "agnes-lovdal",
            datetime(2013, 8, 19),
        ),
        (
            b3,
            "proposed",
            tags1,
            "Exemplifiering av fordonstyp.",
            "jakob-renhagen",
            datetime(2016, 2, 27),
        ),
        (
            b4,
            "proposed",
            tags4,
            "Omarbetning: dynamisk ruttplanering och glesbygdsperspektivet tillagt.",
            "miriam-hook",
            datetime(2019, 11, 8),
        ),
        (
            b5,
            "proposed",
            tags5,
            "Storstadsperspektivet tillagt: DRT som komplement under lågtrafik.",
            "elis-storback",
            datetime(2022, 4, 3),
        ),
        (
            b6,
            "endorsed",
            tags5,
            "Engelsk synonym tillagd; definitionen rekommenderad av branschorganisationen.",
            "linnea-fjallmark",
            datetime(2023, 9, 21),
        ),
        (
            b7,
            "proposed",
            tags5,
            "Modernisering: telefonbeställning är inte längre huvudregeln.",
            "signe-akerlind",
            datetime(2025, 6, 30),
        ),
    ]
    for text, status, tags, note, author, when in plan:
        version = graph.add_version(
            db,
            concept=concept,
            mode="revise",
            base_version_id=version.id,
            canonical_form="anropsstyrd trafik",
            definition_md=text,
            status=status,
            tags=tags,
            note=note,
            provenance={"kind": "human"},
            created_by=u[author].id,
            created_at=when,
        )
        if status == "endorsed":
            add_endorsement(
                db,
                version,
                body="Kollektivtrafikbranschens samorganisation",
                note="Rekommenderad branschdefinition",
                stamped_by=u["branschordboksredaktionen"],
            )
    db.flush()
    return concept, 7, 0


def main() -> None:
    db = SessionLocal()
    remove_existing_showcase(db)

    showcase = Collection(
        slug="tidsmaskinen",
        name="Tidsmaskinen — harmoniseringsdemo",
        year=2026,
        authoritative=False,
        description=(
            "Demobegrepp med djup versionshistorik: samma begrepp genom fyra "
            "decenniers källor, med grenar och AI-assisterad syntes. Konstruerad "
            "för att demonstrera versionsgrafen."
        ),
        licence={"label": "Demo — härledd ur källsamlingarnas material"},
    )
    db.add(showcase)
    for handle in DEMO_USERS:
        get_or_create_user(db, handle)
    db.flush()

    by_slug = load_source_heads(db)
    picks = select_showcase_forms(db, by_slug)
    print(f"Showcase selection: {picks}")

    summary: list[tuple[str, int, int, str]] = []
    for form in picks:
        entries = eligible_entries(by_slug, form)
        concept, n_versions, n_branches = build_stitched_concept(
            db, showcase, form, entries, by_slug
        )
        summary.append((form, n_versions, n_branches, concept.id))

    concept_a, a_versions, a_branches = build_acceptance_a(db, showcase)
    concept_b, b_versions, b_branches = build_acceptance_b(db, showcase)
    db.commit()

    print("\n=== Tidsmaskinen showcase ===")
    for form, n_versions, n_branches, concept_id in summary:
        print(f"  {form}: {n_versions} versions, {n_branches} branch(es), id={concept_id}")
    print(
        f"  realtidsinformation (acceptance A): {a_versions} versions, "
        f"{a_branches} branch(es), id={concept_a.id}"
    )
    print(
        f"  anropsstyrd trafik (acceptance B): {b_versions} versions, "
        f"{b_branches} branch(es), id={concept_b.id}"
    )
    print(f"\nACCEPTANCE_CONCEPT_A = {concept_a.id}")
    print(f"ACCEPTANCE_CONCEPT_B = {concept_b.id}")
    db.close()


if __name__ == "__main__":
    main()
