/**
 * Stand-off section/author segmentation of a version's definition_md.
 *
 * `section` annotations carry {number, title} in value and character offsets
 * into definition_md; `author` annotations share their section's span and
 * carry {name, affiliation, web_url}. The migration guarantees identical
 * spans, but this module is defensive: offsets are clamped, overlapping
 * sections abort segmentation (caller falls back to whole-text rendering),
 * and the produced slices are verified to reconstruct the original text.
 */

import type { AnnotationOut } from '$lib/api';

export interface SectionAuthor {
  name: string;
  affiliation: string | null;
  web_url: string | null;
}

export interface Segment {
  kind: 'intro' | 'section';
  text: string;
  /** Display number — null for intro text and for section "0" (the lead-in). */
  number: string | null;
  title: string | null;
  authors: SectionAuthor[];
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(Math.max(n, lo), hi);
}

function asText(v: unknown): string | null {
  if (typeof v === 'number') return String(v);
  return typeof v === 'string' && v.trim() !== '' ? v.trim() : null;
}

interface Span {
  start: number;
  end: number;
}

/** An author belongs to a section when their spans coincide or overlap. */
function belongsTo(author: Span, section: Span): boolean {
  if (author.start === section.start && author.end === section.end) return true;
  if (author.start === author.end) {
    return author.start >= section.start && author.start <= section.end;
  }
  return author.start < section.end && author.end > section.start;
}

/** Extract the authors carried by `author` annotations, deduplicated. */
function sectionAuthors(annotations: AnnotationOut[], section: Span): SectionAuthor[] {
  const seen = new Set<string>();
  const authors: SectionAuthor[] = [];
  for (const a of annotations) {
    if (a.attr_type !== 'author') continue;
    if (!belongsTo({ start: a.start, end: a.end }, section)) continue;
    const value = a.value as { name?: unknown; affiliation?: unknown; web_url?: unknown };
    const name = asText(value.name);
    if (!name) continue;
    const key = `${name}|${asText(value.web_url) ?? ''}`;
    if (seen.has(key)) continue;
    seen.add(key);
    authors.push({
      name,
      affiliation: asText(value.affiliation),
      web_url: asText(value.web_url)
    });
  }
  return authors;
}

/**
 * Slice `text` into ordered segments from the version's `section` annotations.
 *
 * Returns null when there are no sections, or when the offsets are
 * inconsistent (overlapping sections / slices that do not reconstruct the
 * text) — the caller should then render the whole text unsectioned.
 */
export function buildSegments(text: string, annotations: AnnotationOut[]): Segment[] | null {
  const sections = annotations
    .filter((a) => a.attr_type === 'section')
    .map((a) => {
      const start = clamp(Math.min(a.start, a.end), 0, text.length);
      const value = a.value as { number?: unknown; title?: unknown };
      return {
        start,
        end: clamp(Math.max(a.start, a.end), start, text.length),
        number: asText(value.number),
        title: asText(value.title)
      };
    })
    .sort((x, y) => x.start - y.start || x.end - y.end);
  if (sections.length === 0) return null;

  const segments: Segment[] = [];
  const slices: string[] = [];
  let cursor = 0;

  const pushIntro = (slice: string): void => {
    slices.push(slice);
    if (slice.trim() !== '') {
      segments.push({ kind: 'intro', text: slice, number: null, title: null, authors: [] });
    }
  };

  for (const section of sections) {
    if (section.start < cursor) return null; // overlapping sections — cannot slice
    if (section.start > cursor) pushIntro(text.slice(cursor, section.start));
    const body = text.slice(section.start, section.end);
    slices.push(body);
    if (body.trim() !== '') {
      segments.push({
        kind: 'section',
        text: body,
        // Section "0" is the unnumbered lead-in (prototype convention).
        number: section.number === '0' ? null : section.number,
        title: section.title,
        authors: sectionAuthors(annotations, section)
      });
    }
    cursor = section.end;
  }
  if (cursor < text.length) pushIntro(text.slice(cursor));

  if (slices.join('') !== text) return null; // paranoia: must reconstruct exactly
  return segments;
}

/** "Källa: …" lines from `source_citation` annotations, deduplicated. */
export function sourceCitations(annotations: AnnotationOut[]): string[] {
  const out: string[] = [];
  for (const a of annotations) {
    if (a.attr_type !== 'source_citation') continue;
    const value = a.value as { text?: unknown; citation?: unknown; source?: unknown };
    const citation =
      asText(value.text) ?? asText(value.citation) ?? asText(value.source) ?? asText(a.quote);
    if (citation && !out.includes(citation)) out.push(citation);
  }
  return out;
}
