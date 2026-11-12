"""Make Samtrafiken's glossary public (permission granted by Samtrafiken, 2026-09-15).

- visibility org_private → public
- edit_policy anyone → org (public readers must not be able to edit a third
  party's published-by-permission list)
- is_locked → 1 (2026-11-08): read-only like the other reference
  collections — direct writes only for Samtrafiken's org admins and super
  admins, everyone else contributes through branch proposals
- licence: label/url shown in the UI + machine-readable rights fields
- locales: the "Licens"/"License" section of the bilingual description states
  the permission and that redistribution is not permitted

Idempotent. Plain sqlite3 so it runs unchanged in the staging container.
Usage: python scripts/publish_samtrafiken_collection.py [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "kollepedia.db"
SLUG = "samtrafiken-begreppslista-2024"

LICENCE = {
    "label": "© Samtrafiken i Sverige AB – published by permission, no redistribution",
    "url": "https://samtrafiken.se/begreppslista/",
    "rights_holder": "Samtrafiken i Sverige AB",
    "basis": "published_with_permission",
    "redistribution": "not_permitted",
    "permission_granted": "2026-09-15",
}

LICENSE_SV = (
    "## Licens\n\n"
    "Copyright 2024 [Samtrafiken i Sverige AB](https://samtrafiken.se/). "
    "Begreppslistan publiceras i Kollepedia med särskilt tillstånd från Samtrafiken. "
    "Tillståndet gäller publiceringen här och innebär inte att materialet får "
    "vidarepubliceras, kopieras eller spridas i andra sammanhang utan Samtrafikens medgivande. "
    "Citering och hänvisning till enskilda termer är tillåten med korrekt källangivelse."
)
LICENSE_EN = (
    "## License\n\n"
    "Copyright 2024 [Samtrafiken i Sverige AB](https://samtrafiken.se/). "
    "The glossary is published in Kollepedia by special permission of Samtrafiken. "
    "The permission covers publication here only and does not allow the material to be "
    "republished, copied or distributed elsewhere without Samtrafiken's consent. "
    "Citation of and reference to individual terms is permitted with proper attribution."
)


def replace_section(md: str, heading: str, new_section: str) -> str:
    pat = re.compile(rf"## {heading}\n.*?(?=\n## |\Z)", re.S)
    if pat.search(md):
        return pat.sub(lambda _m: new_section, md)
    return md.rstrip() + "\n\n" + new_section


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    con = sqlite3.connect(a.db)
    row = con.execute(
        "SELECT id, visibility, edit_policy, licence, locales FROM collections WHERE slug=?",
        (SLUG,),
    ).fetchone()
    if row is None:
        raise SystemExit(f"{SLUG} not found in {a.db}")
    cid, vis, policy, licence, locales = row
    loc = json.loads(locales) if locales else {}
    if "sv" in loc:
        loc["sv"]["description"] = replace_section(
            loc["sv"].get("description", ""), "Licens", LICENSE_SV
        )
    if "en" in loc:
        loc["en"]["description"] = replace_section(
            loc["en"].get("description", ""), "License", LICENSE_EN
        )
    print(
        f"{SLUG}: visibility {vis} -> public, edit_policy {policy} -> org, is_locked -> 1, "
        f"licence -> {LICENCE['label']}"
    )
    if a.dry_run:
        print("(dry-run, no changes)")
        return
    con.execute(
        "UPDATE collections SET visibility='public', edit_policy='org', is_locked=1, "
        "licence=?, locales=? "
        "WHERE id=?",
        (json.dumps(LICENCE, ensure_ascii=False), json.dumps(loc, ensure_ascii=False), cid),
    )
    con.commit()
    v = con.execute(
        "SELECT visibility, edit_policy, is_locked, json_extract(licence,'$.label') "
        "FROM collections WHERE "
        "id=?",
        (cid,),
    ).fetchone()
    print("now:", v)


if __name__ == "__main__":
    main()
