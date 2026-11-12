"""Stand-off annotation remapping (plan NG_ATTRIBUTION_OCH_FELHANTERING, paket A).

Section structure and per-span attribution live as character-offset
annotations on immutable versions (migrated from the v1 prototype's
term_sections). Versions are never edited — but without remapping, the
FIRST new version silently drops every section/author annotation and the
imported attribution rots. This module carries them forward through the DAG.

Mapping rules (beslut 2026-07-12, plan §A):
- unchanged text keeps its annotations (offsets translated),
- a partially surviving span shrinks to the surviving part (quote updated),
- a fully removed span is dropped — DAG blame owns attribution from there,
- inserted text gets no annotation (its author IS the version's created_by).

The diff is word-level (mirroring the frontend's diff.ts tokenizer) and the
equal blocks are then mapped back to character offsets. Offsets are Python
str indices (Unicode code points), consistent with the frontend's slicing
in lib/sections/sections.ts — å/ä/ö count as one.

Remapped annotations carry provenance {"kind": "remap", "from_version": …}
so origin stays traceable and a bad remap can be backed out.
"""

import re
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from .models import Annotation, Version

REMAPPED_TYPES = ("section", "author")

# Words and whitespace runs are SEPARATE tokens (unlike diff.ts, which
# attaches trailing whitespace to the word) — otherwise a word would lose
# its identity whenever only the whitespace after it changes, and the last
# word of a span would be dropped on every append.
_TOKEN = re.compile(r"\S+|\s+")


def _tokens(text: str) -> tuple[list[str], list[int]]:
    """Token strings + each token's character start offset."""
    tokens: list[str] = []
    starts: list[int] = []
    for match in _TOKEN.finditer(text):
        tokens.append(match.group(0))
        starts.append(match.start())
    return tokens, starts


class SpanMap:
    """Character-offset mapping old→new built from word-level equal blocks.

    Equal tokens are identical strings, so each equal block is a pair of
    same-length character ranges — offsets translate linearly inside it.
    """

    def __init__(self, old_text: str, new_text: str) -> None:
        a_tokens, a_starts = _tokens(old_text)
        b_tokens, b_starts = _tokens(new_text)
        matcher = SequenceMatcher(a=a_tokens, b=b_tokens, autojunk=False)
        # (old_lo, old_hi, new_lo) per equal block, in old-text order.
        self._blocks: list[tuple[int, int, int]] = []
        for tag, i1, i2, j1, _j2 in matcher.get_opcodes():
            if tag != "equal" or i1 == i2:
                continue
            # A block of nothing but whitespace is no anchor — a lone " "
            # matches anywhere and would map spans between unrelated texts.
            if all(token.isspace() for token in a_tokens[i1:i2]):
                continue
            old_lo = a_starts[i1]
            old_hi = a_starts[i2 - 1] + len(a_tokens[i2 - 1])
            new_lo = b_starts[j1]
            self._blocks.append((old_lo, old_hi, new_lo))

    def remap(self, start: int, end: int) -> tuple[int, int] | None:
        """Translate an old-text span to the new text.

        Returns the span covering every surviving part (shrunk to the
        overlap with equal blocks), or None when nothing survives.
        """
        new_start: int | None = None
        new_end: int | None = None
        for old_lo, old_hi, new_lo in self._blocks:
            lo = max(start, old_lo)
            hi = min(end, old_hi)
            if hi <= lo:
                continue
            mapped_lo = new_lo + (lo - old_lo)
            mapped_hi = new_lo + (hi - old_lo)
            if new_start is None or mapped_lo < new_start:
                new_start = mapped_lo
            if new_end is None or mapped_hi > new_end:
                new_end = mapped_hi
        if new_start is None or new_end is None or new_end <= new_start:
            return None
        return new_start, new_end


def remap_annotations(db: Session, *, parent: Version, child: Version) -> int:
    """Carry the parent's section/author annotations onto the new child.

    Called from every version-creation path in graph.py (revise, branch,
    synthesize, translate, promote). The translate mode's cross-language
    `translated_from` SOURCE is deliberately never remapped — the translator
    authors the translation's wording; origin shows through the DAG.

    Returns the number of annotations carried forward.
    """
    annotations = [a for a in parent.annotations if a.attr_type in REMAPPED_TYPES]
    if not annotations:
        return 0
    span_map = SpanMap(parent.definition_md or "", child.definition_md or "")
    carried = 0
    for annotation in annotations:
        span = span_map.remap(annotation.start, annotation.end)
        if span is None:
            continue
        new_start, new_end = span
        db.add(
            Annotation(
                version_id=child.id,
                attr_type=annotation.attr_type,
                start=new_start,
                end=new_end,
                quote=(child.definition_md or "")[new_start:new_end],
                value=dict(annotation.value or {}),
                provenance={"kind": "remap", "from_version": parent.id},
            )
        )
        carried += 1
    return carried
