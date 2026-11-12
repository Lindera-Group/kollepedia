/** Citation formatting for version permalinks (VISION §10 — citable pillar). */

/** The 8-character short form used when citing a version id. */
export function shortId(id: string): string {
  return id.slice(0, 8);
}

export interface CitationParts {
  author: string;
  canonicalForm: string;
  collection: string;
  versionId: string;
  /** Already locale-formatted date string. */
  date: string;
  /** The sentence dash of the UI language (t('typo.dash')): en dash in
   * Swedish, em dash in English. */
  dash: string;
  url: string;
}

/** A ready-to-paste citation line for a frozen version:
 * `<author>, '<canonical_form>', <collection> <dash> version <8-char id>, <date>. <url>` */
export function formatCitation(parts: CitationParts): string {
  return (
    `${parts.author}, '${parts.canonicalForm}', ${parts.collection}` +
    ` ${parts.dash} version ${shortId(parts.versionId)}, ${parts.date}. ${parts.url}`
  );
}
