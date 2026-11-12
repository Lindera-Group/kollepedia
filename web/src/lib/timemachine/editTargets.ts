/** Save targets for the "edit a historical version" flow (HistoryEditPanel).
 *
 * Editing never rewrites history — every target creates a NEW version:
 * - 'main':       the edit becomes the new main head. If the base IS the main
 *                 head this is a plain revise; otherwise a promote-with-edits
 *                 (lineage: promoted_from base + revised_from previous head).
 * - 'branch':     the base is the head of a non-main branch — the edit
 *                 continues that branch (revise on the branch head).
 * - 'new-branch': always available — fork a new branch from the base version.
 */
import type { BranchOut, ConceptGraphOut, VersionOut } from '$lib/api';

export type EditTarget = 'main' | 'branch' | 'new-branch';

export interface EditTargetInfo {
  target: EditTarget;
  /** For 'branch': the non-main branch the base version heads. */
  branchName?: string;
  /** For 'main': true when the base already is the main head (plain revise). */
  baseIsMainHead?: boolean;
}

export function editTargets(
  graph: Pick<ConceptGraphOut, 'branches'>,
  version: Pick<VersionOut, 'id'>
): EditTargetInfo[] {
  const heads = new Map<string, BranchOut>(
    graph.branches
      .filter((b) => b.head_version_id !== null)
      .map((b) => [b.head_version_id as string, b])
  );
  const headOf = heads.get(version.id);
  const targets: EditTargetInfo[] = [
    { target: 'main', baseIsMainHead: headOf?.name === 'main' }
  ];
  if (headOf && headOf.name !== 'main') {
    targets.push({ target: 'branch', branchName: headOf.name });
  }
  targets.push({ target: 'new-branch' });
  return targets;
}
