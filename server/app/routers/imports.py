"""Per-collection import (Iteration 2): CSV/XLSX file upload, JSON rows, template.

Contract (docs/ARKITEKTUR.md, "Samlingar och listor"):
- GET  /collections/{slug}/import/template?format=csv
- POST /collections/{slug}/import?dry_run=true|false   (multipart `file`)
- POST /collections/{slug}/import-rows                 ({rows, dry_run})

One shared pipeline: validate per row, create concepts through the graph
service (provenance {kind:'import', source, row}), then a second pass
resolves relations/translations first against rows in the same import,
then against existing concepts in the collection. Unresolved targets are
warnings, bad rows are per-row errors — the rest still imports.
dry_run runs everything and rolls back.

Hardening (2026-11-10):
- File parsing stops at MAX_ROWS + 1 rows (413) instead of materialising a
  whole workbook first — a 5 MB xlsx can hold millions of empty rows.
- The file type is decided by content (xlsx is a ZIP: leading ``PK``), not
  by the extension alone; a .xlsx without that signature is rejected.
- The `author` column may attribute a row only to the importer themself or
  to an account WITHOUT a password (an imported, unclaimed profile, created
  on the fly if needed). A name that matches a real, claimed account is kept
  as free text in provenance (`author_name`, `author_affiliation`) — history
  is immutable, so a version must never be signed by someone who did not
  write it — and an import never changes a claimed account's affiliation.
"""

import csv
import io
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, BinaryIO

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import graph
from ..db import get_db
from ..deps import can_view_collection, current_user, ensure_write_allowed
from ..errors import api_error
from ..models import (
    Annotation,
    Branch,
    Collection,
    Concept,
    ConceptRelation,
    ConceptTaxonomyValue,
    Taxonomy,
    User,
    Version,
    VersionEdge,
)

router = APIRouter(tags=["imports"])

MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024  # 5 MB

COLUMNS = [
    "canonical_form",
    "language",
    "definition",
    "status",
    "tags",
    "categories",
    "part",
    "note",
    "author",
    "author_affiliation",
    "variants",
    "related_to",
    "broader",
    "narrower",
    "exact_match",
    "translation_of",
    "source",
]
REQUIRED_COLUMNS = ("canonical_form", "definition")

TEMPLATE_EXAMPLE = [
    "hållplats",
    "sv",
    "Plats där resenärer kan stiga på eller av kollektivtrafikens fordon.",
    "fastställd",
    "Infrastruktur;Hållplatser",
    "Exempelrad – ersätt med egna termer.",
    "Anna Andersson",
    "K2",
    "hållplatsen;hpl",
    "bytespunkt",
    "plats",
    "busshållplats",
    "",
    "stop",
    "Transmodel v6.0 (EN 12896)",
]

# Swedish status labels ↔ API values; both are accepted on import.
# 'Fastställd' is no longer a status (endorsement rework 2026-07-11) — it is
# an organisation's flag on a version. Legacy labels are still accepted on
# import but land as 'proposed'; the flagging itself is a manual org act.
STATUS_BY_LABEL = {
    "utkast": "draft",
    "föreslagen": "proposed",
    "fastställd": "proposed",
    "endorsed": "proposed",
    "utfasad": "deprecated",
    "ersatt": "superseded",
}
API_STATUSES = set(STATUS_BY_LABEL.values())

RELATION_COLUMNS = ("related_to", "broader", "narrower", "exact_match")


# ── Schemas (import-local; web/src/lib/api.ts: ImportRow / ImportResult) ──


class ImportRowIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    canonical_form: str | None = None
    language: str | None = None
    definition: str | None = None
    status: str | None = None
    tags: str | None = None
    note: str | None = None
    author: str | None = None
    author_affiliation: str | None = None
    variants: str | None = None
    related_to: str | None = None
    broader: str | None = None
    narrower: str | None = None
    exact_match: str | None = None
    translation_of: str | None = None
    source: str | None = None


class ImportRowsIn(BaseModel):
    rows: list[ImportRowIn]
    dry_run: bool = False


class ImportErrorOut(BaseModel):
    row: int
    message: str


class ImportResultOut(BaseModel):
    rows_total: int
    created: int
    errors: list[ImportErrorOut]
    warnings: list[str]
    dry_run: bool


# ── Pipeline ──


@dataclass
class _CreatedRow:
    index: int  # 1-based data-row number
    data: dict[str, str]
    concept: Concept
    version: Version
    language: str
    form_lower: str


@dataclass
class _Report:
    rows_total: int = 0
    created: int = 0
    errors: list[ImportErrorOut] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _split_multi(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def _handle_for(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def _resolve_author(
    db: Session,
    cache: dict[str, User | None],
    name: str,
    affiliation: str,
    importer: User | None,
) -> User | None:
    """The account a row's `author` may be attributed to, or None when the
    name belongs to a claimed account that is not the importer (the caller
    then keeps the name as provenance text). Unclaimed profiles (no password)
    are reused or created; their affiliation is filled in only while empty."""
    handle = _handle_for(name)
    if handle in cache:
        return cache[handle]
    user = db.query(User).filter(User.handle == handle).first()
    if user is None:
        user = User(
            handle=handle,
            display_name=name.strip(),
            affiliation=affiliation.strip() or None,
        )
        db.add(user)
        db.flush()
    elif importer is not None and user.id == importer.id:
        pass  # signing your own rows by name is fine; the profile is yours to edit
    elif user.password_hash is not None:
        user = None  # a real person's account — never attribute or alter it
    elif affiliation.strip() and not user.affiliation:
        user.affiliation = affiliation.strip()
    cache[handle] = user
    return user


def _parse_status(raw: str) -> str | None:
    """Swedish label or API value → API value; None when unknown."""
    value = raw.strip().lower()
    if not value:
        return "draft"
    if value in STATUS_BY_LABEL:
        return STATUS_BY_LABEL[value]
    if value in API_STATUSES:
        return value
    return None


def _validate_row(index: int, data: dict[str, str], report: _Report) -> dict[str, Any] | None:
    """Return normalised fields, or None after recording a Swedish error."""
    problems: list[str] = []
    form = data.get("canonical_form", "").strip()
    definition = data.get("definition", "").strip()
    if not form:
        problems.append("canonical_form saknas")
    elif len(form) > 500:
        problems.append("canonical_form är för lång (max 500 tecken)")
    if not definition:
        problems.append("definition saknas")

    language = data.get("language", "").strip().lower() or "sv"
    if language not in ("sv", "en"):
        problems.append(f"okänt språk '{language}' (tillåtna: sv, en)")

    status = _parse_status(data.get("status", ""))
    if status is None:
        problems.append(
            f"okänd status '{data.get('status', '').strip()}' "
            "(tillåtna: utkast, föreslagen, fastställd, utfasad, ersatt)"
        )

    if problems:
        message = f"Rad {index}: {'; '.join(problems)}"
        report.errors.append(ImportErrorOut(row=index, message=message))
        return None
    return {"form": form, "definition": definition, "language": language, "status": status}


def _resolve_target(
    db: Session,
    collection: Collection,
    created: list[_CreatedRow],
    form: str,
    *,
    exclude_concept_id: str,
    row_language: str,
    other_language: bool = False,
) -> tuple[Concept, Version] | None:
    """Resolve a canonical form: rows in this import first, then the collection."""
    key = form.strip().lower()
    candidates = [r for r in created if r.form_lower == key and r.concept.id != exclude_concept_id]
    if other_language:
        candidates = [r for r in candidates if r.language != row_language]
    else:
        same = [r for r in candidates if r.language == row_language]
        if same:
            candidates = same
    if candidates:
        return candidates[0].concept, candidates[0].version

    query = (
        db.query(Concept, Version)
        .join(Branch, (Branch.concept_id == Concept.id) & (Branch.name == "main"))
        .join(Version, Version.id == Branch.head_version_id)
        .filter(
            Concept.collection_id == collection.id,
            Concept.id != exclude_concept_id,
            func.lower(Version.canonical_form) == key,
        )
    )
    if other_language:
        query = query.filter(Version.language != row_language)
    existing = query.first()
    if existing is not None:
        return existing[0], existing[1]
    return None


def run_import(
    db: Session,
    *,
    collection: Collection,
    rows: list[dict[str, str]],
    source_label: str,
    dry_run: bool,
    user: User | None,
) -> ImportResultOut:
    """The shared pipeline: two passes (create, then link), rollback on dry_run."""
    if len(rows) > MAX_ROWS:
        raise api_error(
            413,
            "import_too_many_rows",
            f"Too many rows: {len(rows)} (max {MAX_ROWS}).",
            rows=len(rows),
            max_rows=MAX_ROWS,
        )

    report = _Report(rows_total=len(rows))
    created: list[_CreatedRow] = []
    author_cache: dict[str, User | None] = {}

    # Taxonomy lookups (plan NG_TAXONOMIES follow-up): `categories` validates
    # against the GLOBAL vocabulary, `part` against the collection's exact-one
    # taxonomy. Names match Swedish or English, case-insensitively. Unknown
    # names are HARD row errors — imports are curated material.
    global_tax = (
        db.query(Taxonomy)
        .filter(Taxonomy.scope == "global", Taxonomy.slug == "kategorier")
        .first()
    )
    category_by_name = {
        name.lower(): v.id
        for v in (global_tax.values if global_tax else [])
        for name in (v.name, v.name_en)
        if name
    }
    parts_tax = (
        db.query(Taxonomy)
        .filter(Taxonomy.collection_id == collection.id, Taxonomy.max_per_concept == 1)
        .first()
    )
    part_by_name = {
        name.lower(): v.id
        for v in (parts_tax.values if parts_tax else [])
        for name in (v.name, v.name_en)
        if name
    }

    # Pass 1 — validate and create concepts.
    for index, data in enumerate(rows, start=1):
        fields = _validate_row(index, data, report)
        if fields is None:
            continue
        category_ids: list[str] = []
        row_error = False
        for name in _split_multi(data.get("categories", "")):
            value_id = category_by_name.get(name.lower())
            if value_id is None:
                report.errors.append(
                    ImportErrorOut(
                        row=index, message=f"okänd kategori '{name}' (globala vokabulären styr)"
                    )
                )
                row_error = True
                break
            if value_id not in category_ids:
                category_ids.append(value_id)
        part_name = data.get("part", "").strip()
        part_id: str | None = None
        if part_name and not row_error:
            if parts_tax is None:
                report.errors.append(
                    ImportErrorOut(
                        row=index,
                        message=(
                            "samlingen har ingen part-taxonomi – kolumnen 'part' kan inte användas"
                        ),
                    )
                )
                row_error = True
            else:
                part_id = part_by_name.get(part_name.lower())
                if part_id is None:
                    report.errors.append(
                        ImportErrorOut(row=index, message=f"okänd part '{part_name}'")
                    )
                    row_error = True
        if row_error:
            continue

        provenance = {"kind": "import", "source": source_label, "row": index}
        if user is None:
            # Anonymous wiki-mode import (edit_policy 'open', iteration 4).
            provenance["anonymous"] = True
        author_name = data.get("author", "").strip()
        author_affiliation = data.get("author_affiliation", "").strip()
        creator = user
        if author_name:
            creator = _resolve_author(db, author_cache, author_name, author_affiliation, user)
            if creator is None:
                # The name is a claimed account's: record it as text and let
                # the importer sign the version (see module docstring).
                creator = user
                provenance["author_name"] = author_name
                if author_affiliation:
                    provenance["author_affiliation"] = author_affiliation
        concept, version, _branch = graph.create_concept(
            db,
            collection_id=collection.id,
            canonical_form=fields["form"],
            language=fields["language"],
            definition_md=fields["definition"],
            status=fields["status"],
            tags=_split_multi(data.get("tags", "")),
            note=data.get("note", "").strip() or None,
            provenance=provenance,
            created_by=creator.id if creator else None,
        )
        for variant in _split_multi(data.get("variants", "")):
            db.add(
                Annotation(
                    version_id=version.id,
                    attr_type="variant",
                    value={"form": variant, "kind": "synonym"},
                    provenance=provenance,
                )
            )
        citation = data.get("source", "").strip()
        if citation:
            db.add(
                Annotation(
                    version_id=version.id,
                    attr_type="source_citation",
                    value={"text": citation},
                    provenance=provenance,
                )
            )
        for value_id in category_ids + ([part_id] if part_id else []):
            db.add(
                ConceptTaxonomyValue(
                    concept_id=concept.id,
                    value_id=value_id,
                    added_by=user.id if user else None,
                )
            )
        created.append(
            _CreatedRow(
                index=index,
                data=data,
                concept=concept,
                version=version,
                language=fields["language"],
                form_lower=fields["form"].lower(),
            )
        )
    db.flush()
    report.created = len(created)

    # Pass 2 — resolve relations and translations now that all rows exist.
    linked_translations: set[frozenset[str]] = set()
    for row in created:
        provenance = {"kind": "import", "source": source_label, "row": row.index}
        if user is None:
            provenance["anonymous"] = True
        for column in RELATION_COLUMNS:
            for target_form in _split_multi(row.data.get(column, "")):
                target = _resolve_target(
                    db,
                    collection,
                    created,
                    target_form,
                    exclude_concept_id=row.concept.id,
                    row_language=row.language,
                )
                if target is None:
                    report.warnings.append(
                        f"Rad {row.index}: målet '{target_form}' för {column} "
                        "hittades inte – relationen hoppades över."
                    )
                    continue
                db.add(
                    ConceptRelation(
                        relation_type=column,
                        from_concept_id=row.concept.id,
                        to_concept_id=target[0].id,
                        provenance=provenance,
                        created_by=user.id if user else None,
                    )
                )

        translation_form = row.data.get("translation_of", "").strip()
        if translation_form:
            target = _resolve_target(
                db,
                collection,
                created,
                translation_form,
                exclude_concept_id=row.concept.id,
                row_language=row.language,
                other_language=True,
            )
            if target is None:
                report.warnings.append(
                    f"Rad {row.index}: översättningen '{translation_form}' "
                    "hittades inte på det andra språket – hoppades över."
                )
            else:
                pair = frozenset({row.version.id, target[1].id})
                if pair not in linked_translations:
                    linked_translations.add(pair)
                    db.add(
                        VersionEdge(
                            child_id=row.version.id,
                            parent_id=target[1].id,
                            edge_type="translated_from",
                        )
                    )
    db.flush()

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return ImportResultOut(
        rows_total=report.rows_total,
        created=report.created,
        errors=report.errors,
        warnings=report.warnings,
        dry_run=dry_run,
    )


# ── File parsing ──


def _too_many_rows() -> Exception:
    return api_error(
        413,
        "import_too_many_rows",
        f"Too many rows: more than {MAX_ROWS} (max {MAX_ROWS}).",
        max_rows=MAX_ROWS,
    )


def _collect_rows(row_iter: Iterator[dict[str, str]]) -> list[dict[str, str]]:
    """Keep the non-empty rows, stopping as soon as the cap is exceeded so an
    oversized file is never fully materialised in memory (413)."""
    rows: list[dict[str, str]] = []
    for row in row_iter:
        if any(row.get(column, "") for column in COLUMNS):
            rows.append(row)
            if len(rows) > MAX_ROWS:
                raise _too_many_rows()
    return rows


def _parse_csv(data: bytes) -> tuple[list[dict[str, str]], list[str]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise api_error(400, "file_not_utf8", "The file could not be read as UTF-8.") from None
    stripped = text.lstrip("\r\n")
    if not stripped.strip():
        raise api_error(400, "file_empty", "The file is empty.")
    header_line = stripped.splitlines()[0]
    delimiter = ";" if header_line.count(";") > header_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(stripped), delimiter=delimiter)
    fieldnames = [(name or "").strip() for name in reader.fieldnames or []]
    warnings = _check_header(fieldnames)
    rows = _collect_rows(
        {(key or "").strip(): (value or "").strip() for key, value in raw.items() if key}
        for raw in reader
    )
    return rows, warnings


def _parse_xlsx(stream: BinaryIO) -> tuple[list[dict[str, str]], list[str]]:
    import openpyxl

    try:
        workbook = openpyxl.load_workbook(stream, read_only=True, data_only=True)
    except Exception:
        raise api_error(
            400, "file_not_xlsx", "The file could not be read as Excel (.xlsx)."
        ) from None
    try:
        sheet = workbook.worksheets[0]
        rows_iter = sheet.iter_rows(values_only=True)
        header = next(rows_iter, None)
        if header is None:
            raise api_error(400, "file_empty", "The file is empty.")
        fieldnames = [str(cell).strip() if cell is not None else "" for cell in header]
        warnings = _check_header(fieldnames)
        rows = _collect_rows(
            {
                name: (str(value).strip() if value is not None else "")
                for name, value in zip(fieldnames, values, strict=False)
                if name
            }
            for values in rows_iter
        )
    finally:
        workbook.close()
    return rows, warnings


# ZIP local-file-header signature — every .xlsx (OOXML) starts with it.
XLSX_MAGIC = b"PK"


def _parse_upload(data: bytes, filename: str) -> tuple[list[dict[str, str]], list[str]]:
    """Dispatch on CONTENT: a ZIP signature means xlsx whatever the name says;
    a .xlsx name without it is rejected outright rather than fed to the CSV
    reader (whose UTF-8/column errors would only mislead)."""
    if data.startswith(XLSX_MAGIC):
        return _parse_xlsx(io.BytesIO(data))
    if filename.lower().endswith(".xlsx"):
        raise api_error(400, "file_not_xlsx", "The file could not be read as Excel (.xlsx).")
    return _parse_csv(data)


def _check_header(fieldnames: list[str]) -> list[str]:
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        raise api_error(
            400,
            "import_bad_columns",
            f"The file is missing required columns: {', '.join(missing)}. "
            f"Expected columns: {', '.join(COLUMNS)}.",
            missing=", ".join(missing),
            expected=", ".join(COLUMNS),
        )
    return [
        f"Okänd kolumn ignorerades: {name}" for name in fieldnames if name and name not in COLUMNS
    ]


# ── Endpoints ──


def _get_collection(db: Session, slug: str, user: User | None = None) -> Collection:
    """Resolve a collection with the same visibility rule as every other read:
    org_private collections 404 for strangers (never confirm the slug exists)."""
    collection = db.query(Collection).filter(Collection.slug == slug).first()
    if collection is None or not can_view_collection(user, collection):
        raise api_error(404, "collection_not_found", "Collection not found")
    return collection


def _require_import_permission(db: Session, slug: str, user: User | None) -> Collection:
    """Imports are bulk writes — the same central guard as any other concept
    write (iteration 3): 401 anonymous (unless edit_policy 'open', iteration 4),
    403 inactive/suspended/rights, 423 archived/locked. Visibility still
    404s before anything is disclosed."""
    collection = _get_collection(db, slug, user)
    ensure_write_allowed(user, collection)
    return collection


@router.get("/collections/{slug}/import/template")
def import_template(
    slug: str,
    format: str = Query(default="csv"),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> Response:
    _get_collection(db, slug, user)
    if format != "csv":
        raise api_error(
            422,
            "import_template_format_unknown",
            "Only format=csv is supported.",
            format=format,
        )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    writer.writerow(TEMPLATE_EXAMPLE)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}-import-mall.csv"'},
    )


@router.post("/collections/{slug}/import", response_model=ImportResultOut)
def import_file(
    slug: str,
    dry_run: bool = Query(default=False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> ImportResultOut:
    collection = _require_import_permission(db, slug, user)

    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise api_error(
            413,
            "file_too_large",
            "The file is too large (max 5 MB).",
            max_mb=MAX_BYTES // (1024 * 1024),
        )
    filename = file.filename or "import.csv"
    rows, warnings = _parse_upload(data, filename)

    result = run_import(
        db,
        collection=collection,
        rows=rows,
        source_label=filename,
        dry_run=dry_run,
        user=user,
    )
    result.warnings = warnings + result.warnings
    return result


@router.post("/collections/{slug}/import-rows", response_model=ImportResultOut)
def import_rows(
    slug: str,
    payload: ImportRowsIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
) -> ImportResultOut:
    collection = _require_import_permission(db, slug, user)
    rows = [
        {key: (value or "").strip() for key, value in row.model_dump().items()}
        for row in payload.rows
    ]
    return run_import(
        db,
        collection=collection,
        rows=rows,
        source_label="rows",
        dry_run=payload.dry_run,
        user=user,
    )
