/** The ONE source for status-filter options (Bengt deep-review #3):
 * the text lifecycle statuses plus 'endorsed', which since the endorsement
 * rework means "some version carries an ACTIVE organisation flag" (the
 * server special-cases it in the concepts list). */
export const STATUS_FILTER_VALUES = [
  'draft',
  'proposed',
  'endorsed',
  'deprecated',
  'superseded'
] as const;

/** The text lifecycle only — what an editor can SET on a version. */
export const VERSION_STATUSES = ['draft', 'proposed', 'deprecated', 'superseded'] as const;
