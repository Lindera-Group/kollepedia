/** The ONE source for export formats + labels (Bengt deep-review #4) —
 * consumed by the collection page and the list page alike. */
export const EXPORT_FORMATS: { format: string; label: string }[] = [
  { format: 'csv', label: 'CSV' },
  { format: 'markdown', label: 'Markdown' },
  { format: 'jsonld', label: 'JSON-LD' },
  { format: 'skos', label: 'SKOS' },
  { format: 'tbx', label: 'TBX' }
];
