/** Per-token provenance: which version introduced each word ("git blame as ink").
 *
 * Chains diffs along the current path: version 0's tokens are introduced by
 * version 0; at each step, 'eq' tokens inherit their introducer and 'ins'
 * tokens are stamped with the new version's id.
 */

import { diffTokens, tokenize, type Token } from './diff';

/** blame[i][j] = version id that introduced token j of text i in the chain. */
export function blameChain(texts: string[], versionIds: string[]): string[][] {
  const blame: string[][] = [];
  let prevTokens: Token[] = [];
  let prevBlame: string[] = [];

  for (let i = 0; i < texts.length; i++) {
    const tokens = tokenize(texts[i]);
    if (i === 0) {
      const meta = tokens.map(() => versionIds[0]);
      blame.push(meta);
      prevTokens = tokens;
      prevBlame = meta;
      continue;
    }
    const ops = diffTokens(prevTokens, tokens);
    const meta: string[] = [];
    let aIdx = 0;
    for (const op of ops) {
      if (op.type === 'eq') {
        for (let k = 0; k < op.tokens.length; k++) meta.push(prevBlame[aIdx + k]);
        aIdx += op.tokens.length;
      } else if (op.type === 'del') {
        aIdx += op.tokens.length;
      } else {
        for (let k = 0; k < op.tokens.length; k++) meta.push(versionIds[i]);
      }
    }
    blame.push(meta);
    prevTokens = tokens;
    prevBlame = meta;
  }
  return blame;
}

/** Age per token, 0 = written in the current version, 1 = as old as the path. */
export function tokenAges(blame: string[], versionIds: string[], currentIndex: number): number[] {
  const indexOf = new Map(versionIds.map((id, i) => [id, i]));
  return blame.map((vid) => {
    const introduced = indexOf.get(vid) ?? 0;
    return currentIndex === 0 ? 0 : (currentIndex - introduced) / Math.max(1, versionIds.length - 1);
  });
}
