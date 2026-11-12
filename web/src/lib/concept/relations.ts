/** Relation grouping + labels, shared by the concept page's "Se även" line
 * and the Relationer tool subview (ToolRelations.svelte). */
import type { RelationOut } from '$lib/api';
import { t, type TranslationKey } from '$lib/i18n.svelte';

const RELATION_KEYS: Record<string, TranslationKey> = {
  related_to: 'concept.rel_related_to',
  broader: 'concept.rel_broader',
  narrower: 'concept.rel_narrower',
  exact_match: 'concept.rel_exact_match',
  close_match: 'concept.rel_close_match',
  supersedes: 'concept.rel_supersedes'
};

export function relationLabel(type: string): string {
  const key = RELATION_KEYS[type];
  return key ? t(key) : type;
}

export function groupRelations(relations: RelationOut[]): Map<string, RelationOut[]> {
  const groups = new Map<string, RelationOut[]>();
  for (const relation of relations) {
    const list = groups.get(relation.relation_type) ?? [];
    list.push(relation);
    groups.set(relation.relation_type, list);
  }
  return groups;
}
