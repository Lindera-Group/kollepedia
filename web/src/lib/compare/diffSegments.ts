/** Semantic-diff segments for the comparison workbench.
 *
 * Reuses the Time Machine's word-level Myers diff. Direction: `a` is the BASE
 * column, `b` is the compared column — so `del` means "only in the base"
 * (rendered as red strikethrough wash) and `ins` means "only in this column"
 * (green wash), matching the static-diff visual language.
 */

import { diffTokens, tokenize, type OpType } from '../timemachine/diff';

export interface DiffSegment {
  type: OpType;
  text: string;
}

export function buildDiffSegments(baseText: string, otherText: string): DiffSegment[] {
  return diffTokens(tokenize(baseText), tokenize(otherText)).map((op) => ({
    type: op.type,
    text: op.tokens.map((t) => t.text).join('')
  }));
}
