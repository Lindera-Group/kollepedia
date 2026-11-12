/** Import column spec — mirrors server/app/routers/imports.py (COLUMNS)
 * and the server's app/routers/imports.py COLUMNS exactly.
 * Descriptions are i18n keys resolved with t() at render time (ColumnHelp). */

import type { TranslationKey } from '$lib/i18n.svelte';

export interface ColumnSpec {
  name: string;
  required: boolean;
  descriptionKey: TranslationKey;
  example: string;
}

export const IMPORT_COLUMNS: ColumnSpec[] = [
  {
    name: 'canonical_form',
    required: true,
    descriptionKey: 'import.coldesc_canonical_form',
    example: 'hållplats' // i18n-exempt: illustrative sample value
  },
  {
    name: 'language',
    required: false,
    descriptionKey: 'import.coldesc_language',
    example: 'sv'
  },
  {
    name: 'definition',
    required: true,
    descriptionKey: 'import.coldesc_definition',
    example: 'Plats där resenärer kan stiga på eller av …' // i18n-exempt: illustrative sample value
  },
  {
    name: 'status',
    required: false,
    descriptionKey: 'import.coldesc_status',
    example: 'fastställd' // i18n-exempt: illustrative sample value
  },
  {
    name: 'tags',
    required: false,
    descriptionKey: 'import.coldesc_tags',
    example: 'Infrastruktur;Hållplatser' // i18n-exempt: illustrative sample value
  },
  {
    name: 'note',
    required: false,
    descriptionKey: 'import.coldesc_note',
    example: 'Importerad från ordlista 2024.' // i18n-exempt: illustrative sample value
  },
  {
    name: 'author',
    required: false,
    descriptionKey: 'import.coldesc_author',
    example: 'Anna Andersson'
  },
  {
    name: 'author_affiliation',
    required: false,
    descriptionKey: 'import.coldesc_author_affiliation',
    example: 'K2'
  },
  {
    name: 'variants',
    required: false,
    descriptionKey: 'import.coldesc_variants',
    example: 'hållplatsen;hpl' // i18n-exempt: illustrative sample value
  },
  {
    name: 'related_to',
    required: false,
    descriptionKey: 'import.coldesc_related_to',
    example: 'bytespunkt'
  },
  {
    name: 'broader',
    required: false,
    descriptionKey: 'import.coldesc_broader',
    example: 'plats'
  },
  {
    name: 'narrower',
    required: false,
    descriptionKey: 'import.coldesc_narrower',
    example: 'busshållplats' // i18n-exempt: illustrative sample value
  },
  {
    name: 'exact_match',
    required: false,
    descriptionKey: 'import.coldesc_exact_match',
    example: ''
  },
  {
    name: 'translation_of',
    required: false,
    descriptionKey: 'import.coldesc_translation_of',
    example: 'stop'
  },
  {
    name: 'source',
    required: false,
    descriptionKey: 'import.coldesc_source',
    example: 'Transmodel v6.0 (EN 12896)'
  }
];
