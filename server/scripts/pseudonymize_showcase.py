"""Pseudonymise persons and organisations in the 'tidsmaskinen' showcase
(collection "Historik — harmoniseringsdemo").

The demo history was fabricated for the Time Machine, but it named real
organisations (Samtrafiken, Trafikverket, Svensk Kollektivtrafik, K2, SL,
Västtrafik, Skånetrafiken, Norrtåg, UITP, CEN, SUTI) and plausible/real
persons as authors and endorsers. This script replaces them with fictional
actors so the demo cannot be mistaken for real editorial history.

Scope (everything is limited to the showcase collection):
  users        — handle, display_name, affiliation of the demo editors
  endorsements — body text, note; organisation_id detached (NULL) so no real
                 organisation row is credited with a fabricated stamp
  versions     — note, provenance.source (pseudonymised source slugs)
  comments / change_proposals — text
  collection   — description gets an explicit "all actors are fictional" line

Definitions are NOT touched (verified: no person/org names in them).
Idempotent: a second run finds nothing to replace. Plain sqlite3 so it runs
unchanged inside the staging container (python scripts/pseudonymize_showcase.py).

Usage:
    python scripts/pseudonymize_showcase.py [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"
COLLECTION_SLUG = "tidsmaskinen"
DISCLAIMER = "Samtliga personer, redaktioner och organisationer i demon är fiktiva."

# handle -> (new_handle, new_display_name, new_affiliation)
USERS = {
    "anna-lindqvist": ("agnes-lovdal", "Agnes Lövdal", "Sydlänstrafiken"),
    "erik-sandstrom": ("elis-storback", "Elis Storbäck", "Mälardalstrafik"),
    "maria-holm": ("miriam-hook", "Miriam Höök", "Västlänstrafiken"),
    "jonas-berg": ("jakob-renhagen", "Jakob Renhagen", "Spårinfrastrukturverket"),
    "sara-nystrom": ("signe-akerlind", "Signe Åkerlind", "IRF"),
    "lena-vikstrom": ("linnea-fjallmark", "Linnea Fjällmark", "Nordbanan"),
    "petra-lundmark": ("paulina-granvik", "Paulina Granvik", "Övre Norrlands trafikmyndighet"),
    "thomas-weber": ("konrad-ahlberg", "Konrad Ahlberg", "ITF – Internationella transitforumet"),
    "kto-redaktionen": (
        "branschordboksredaktionen",
        "Branschordboksredaktionen",
        "KBS – Kollektivtrafikbranschens samorganisation",
    ),
    "transmodel-wg": (
        "referensmodellgruppen",
        "Referensmodellgruppen",
        "ESR – Europeiska standardgruppen för resedata",
    ),
    "k2-forskargruppen": (
        "irf-forskargruppen",
        "IRF forskargruppen",
        "IRF – Institutet för resandeforskning",
    ),
    "samtrafiken-redaktionen": (
        "resesamordningen-redaktionen",
        "Nordisk Resesamordning",
        "Nordisk Resesamordning AB",
    ),
    "trafikverket-redaktionen": (
        "sparinfrastrukturverket-redaktionen",
        "Spårinfrastrukturverket",
        "Spårinfrastrukturverket",
    ),
}

# Ordered longest-first; applied word-bounded to free text in the showcase.
TEXT = [
    (
        "UITP – International Association of Public Transport",
        "ITF – Internationella transitforumet",
    ),
    (
        "K2 – Nationellt kunskapscentrum för kollektivtrafik",
        "IRF – Institutet för resandeforskning",
    ),
    ("Norrbottens läns kollektivtrafik", "Övre Norrlands trafikmyndighet"),
    ("Samtrafikens begreppslista", "Nordisk Resesamordnings begreppslista"),
    ("Samtrafiken i Sverige AB", "Nordisk Resesamordning AB"),
    ("Trafikverkets järnvägstermer", "Spårinfrastrukturverkets järnvägstermer"),
    ("Svensk Kollektivtrafik", "Kollektivtrafikbranschens samorganisation"),
    ("CEN TC278 / Transmodel", "ESR / Transmodel"),
    ("CEN TC278", "ESR – Europeiska standardgruppen för resedata"),
    ("Samtrafiken", "Nordisk Resesamordning"),
    ("Trafikverket", "Spårinfrastrukturverket"),
    ("Skånetrafiken", "Sydlänstrafiken"),
    ("Västtrafik", "Västlänstrafiken"),
    ("Norrtåg", "Nordbanan"),
    ("UITP", "ITF"),
    ("SUTI", "SFAT"),
    ("K2", "IRF"),
    ("SL", "Mälardalstrafik"),
    # persons (full names, then first names for comment banter)
    ("Anna Lindqvist", "Agnes Lövdal"),
    ("Erik Sandström", "Elis Storbäck"),
    ("Maria Holm", "Miriam Höök"),
    ("Jonas Berg", "Jakob Renhagen"),
    ("Sara Nyström", "Signe Åkerlind"),
    ("Lena Vikström", "Linnea Fjällmark"),
    ("Petra Lundmark", "Paulina Granvik"),
    ("Thomas Weber", "Konrad Ahlberg"),
    ("Anna", "Agnes"),
    ("Erik", "Elis"),
    ("Maria", "Miriam"),
    ("Jonas", "Jakob"),
    ("Sara", "Signe"),
    ("Lena", "Linnea"),
    ("Petra", "Paulina"),
    ("Thomas", "Konrad"),
]
SOURCE_SLUGS = {
    "samtrafiken-begreppslista-2024": "resesamordningen-begreppslista-2024",
    "trafikverket-jarnvagstermer-2025": "sparinfrastrukturverket-jarnvagstermer-2025",
}

_PATTERNS = [
    (re.compile(r"(?<![\wåäöÅÄÖ])" + re.escape(old) + r"(?![\wåäöÅÄÖ])"), new) for old, new in TEXT
]


def pseudonymise(text: str | None) -> str | None:
    if not text:
        return text
    out = text
    for pat, new in _PATTERNS:
        out = pat.sub(new, out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    coll = cur.execute(
        "SELECT id, description FROM collections WHERE slug = ?", (COLLECTION_SLUG,)
    ).fetchone()
    if coll is None:
        raise SystemExit(f"collection '{COLLECTION_SLUG}' not found in {args.db}")
    cid = coll["id"]
    concept_ids = [
        r["id"] for r in cur.execute("SELECT id FROM concepts WHERE collection_id = ?", (cid,))
    ]
    cq = ",".join("?" * len(concept_ids))
    version_ids = [
        r["id"]
        for r in cur.execute(f"SELECT id FROM versions WHERE concept_id IN ({cq})", concept_ids)
    ]
    vq = ",".join("?" * len(version_ids))
    changes: dict[str, int] = {}

    def bump(key: str) -> None:
        changes[key] = changes.get(key, 0) + 1

    # ---- users (demo editors only) ----
    for old_handle, (new_handle, display, affiliation) in USERS.items():
        row = cur.execute(
            "SELECT id, display_name, affiliation FROM users WHERE handle = ?", (old_handle,)
        ).fetchone()
        if row is None:
            continue
        if cur.execute("SELECT 1 FROM users WHERE handle = ?", (new_handle,)).fetchone():
            raise SystemExit(f"target handle '{new_handle}' already exists — refusing to collide")
        print(
            f"  user {old_handle} ({row['display_name']}, {row['affiliation']}) -> {new_handle} "
            f"({display}, {affiliation})"
        )
        if not args.dry_run:
            cur.execute(
                "UPDATE users SET handle=?, display_name=?, affiliation=? WHERE id=?",
                (new_handle, display, affiliation, row["id"]),
            )
        bump("users")

    # ---- endorsements on showcase versions ----
    for e in cur.execute(
        "SELECT id, body, note, withdrawal_note, organisation_id FROM endorsements WHERE "
        f"version_id IN ({vq})",
        version_ids,
    ).fetchall():
        nb, nn, nw = (
            pseudonymise(e["body"]),
            pseudonymise(e["note"]),
            pseudonymise(e["withdrawal_note"]),
        )
        if (nb, nn, nw, None) != (
            e["body"],
            e["note"],
            e["withdrawal_note"],
            e["organisation_id"],
        ):
            print(
                f"  endorsement {e['id'][:8]}: '{e['body']}' -> '{nb}', org "
                f"{e['organisation_id']} -> NULL"
            )
            if not args.dry_run:
                cur.execute(
                    "UPDATE endorsements SET body=?, note=?, withdrawal_note=?, "
                    "organisation_id=NULL WHERE id=?",
                    (nb, nn, nw, e["id"]),
                )
            bump("endorsements")

    # ---- versions: note + provenance.source ----
    for v in cur.execute(
        f"SELECT id, note, provenance FROM versions WHERE id IN ({vq})", version_ids
    ).fetchall():
        new_note = pseudonymise(v["note"])
        prov_raw = v["provenance"]
        new_prov_raw = prov_raw
        if prov_raw:
            prov = json.loads(prov_raw)
            src = prov.get("source")
            if src in SOURCE_SLUGS:
                prov["source"] = SOURCE_SLUGS[src]
                new_prov_raw = json.dumps(prov, ensure_ascii=False)
        if new_note != v["note"] or new_prov_raw != prov_raw:
            if not args.dry_run:
                cur.execute(
                    "UPDATE versions SET note=?, provenance=? WHERE id=?",
                    (new_note, new_prov_raw, v["id"]),
                )
            bump("versions")

    # ---- comments / change proposals ----
    for c in cur.execute(
        f"SELECT id, body FROM comments WHERE concept_id IN ({cq})", concept_ids
    ).fetchall():
        nb = pseudonymise(c["body"])
        if nb != c["body"]:
            print(f"  comment {c['id'][:8]}: {c['body'][:60]!r} -> {nb[:60]!r}")
            if not args.dry_run:
                cur.execute("UPDATE comments SET body=? WHERE id=?", (nb, c["id"]))
            bump("comments")
    for p in cur.execute(
        "SELECT id, title, description, resolution_note FROM change_proposals WHERE concept_id "
        f"IN ({cq})",
        concept_ids,
    ).fetchall():
        nt, nd, nr = (
            pseudonymise(p["title"]),
            pseudonymise(p["description"]),
            pseudonymise(p["resolution_note"]),
        )
        if (nt, nd, nr) != (p["title"], p["description"], p["resolution_note"]):
            if not args.dry_run:
                cur.execute(
                    "UPDATE change_proposals SET title=?, description=?, resolution_note=? WHERE "
                    "id=?",
                    (nt, nd, nr, p["id"]),
                )
            bump("change_proposals")

    # ---- collection disclaimer ----
    desc = pseudonymise(coll["description"]) or ""
    if DISCLAIMER not in desc:
        desc = (desc.rstrip() + " " + DISCLAIMER).strip()
        if not args.dry_run:
            cur.execute("UPDATE collections SET description=? WHERE id=?", (desc, cid))
        bump("collection_description")

    if args.dry_run:
        con.rollback()
        print(f"DRY RUN — would change: {changes}")
    else:
        con.commit()
        print(f"DONE — changed: {changes}")

    # ---- verification: no old names left anywhere in the showcase ----
    leftovers = []
    checks = [
        (f"SELECT note AS t FROM versions WHERE id IN ({vq})", version_ids),
        (f"SELECT provenance AS t FROM versions WHERE id IN ({vq})", version_ids),
        (f"SELECT body AS t FROM endorsements WHERE version_id IN ({vq})", version_ids),
        (f"SELECT note AS t FROM endorsements WHERE version_id IN ({vq})", version_ids),
        (f"SELECT body AS t FROM comments WHERE concept_id IN ({cq})", concept_ids),
        (
            "SELECT display_name || ' ' || COALESCE(affiliation,'') || ' ' || handle AS t FROM "
            "users WHERE id IN "
            f"(SELECT DISTINCT created_by FROM versions WHERE id IN ({vq}))",
            version_ids,
        ),
    ]
    old_terms = [old for old, _ in TEXT if len(old) > 3] + list(USERS)
    for sql, params in checks:
        for r in cur.execute(sql, params):
            t = r["t"] or ""
            for old in old_terms:
                if re.search(r"(?<![\wåäöÅÄÖ])" + re.escape(old) + r"(?![\wåäöÅÄÖ])", t):
                    leftovers.append((old, t[:80]))
    if not args.dry_run:
        print(
            "Verification:",
            "clean — no real names left in the showcase"
            if not leftovers
            else f"LEFTOVERS: {leftovers[:10]}",
        )
    con.close()


if __name__ == "__main__":
    main()
