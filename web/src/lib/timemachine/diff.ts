/** Word-level Myers diff for the Time Machine.
 *
 * Tokens are words *with their trailing whitespace* so that when a word's span
 * collapses, its space collapses with it. Newline runs are separate 'break'
 * tokens: word spans are rendered inline-block and must never contain a line
 * break.
 */

export interface Token {
  text: string;
  kind: 'word' | 'break';
}

export type OpType = 'eq' | 'del' | 'ins';

export interface DiffOp {
  type: OpType;
  tokens: Token[];
}

export function tokenize(text: string): Token[] {
  const parts = text.match(/\n+[^\S\n]*|[^\S\n]+|[^\s]+/g) ?? [];
  const tokens: Token[] = [];
  for (const part of parts) {
    if (part.includes('\n')) {
      tokens.push({ text: part, kind: 'break' });
    } else if (/^[^\S\n]+$/.test(part)) {
      const last = tokens[tokens.length - 1];
      if (last && last.kind === 'word') last.text += part;
      else tokens.push({ text: part, kind: 'word' });
    } else {
      tokens.push({ text: part, kind: 'word' });
    }
  }
  return tokens;
}

/** Equality ignores trailing-whitespace differences (visually negligible). */
function tokenKey(token: Token): string {
  return token.kind === 'break' ? '\n' : token.text.trimEnd();
}

/** Myers O(ND) diff over token sequences. */
export function diffTokens(a: Token[], b: Token[]): DiffOp[] {
  const n = a.length;
  const m = b.length;
  const aKeys = a.map(tokenKey);
  const bKeys = b.map(tokenKey);
  const max = n + m;
  if (max === 0) return [];

  // Trace of V arrays for backtracking.
  const trace: Int32Array[] = [];
  const offset = max;
  let v = new Int32Array(2 * max + 1);
  let foundD = -1;

  outer: for (let d = 0; d <= max; d++) {
    const next = new Int32Array(v);
    for (let k = -d; k <= d; k += 2) {
      let x: number;
      if (k === -d || (k !== d && v[offset + k - 1] < v[offset + k + 1])) {
        x = v[offset + k + 1];
      } else {
        x = v[offset + k - 1] + 1;
      }
      let y = x - k;
      while (x < n && y < m && aKeys[x] === bKeys[y]) {
        x++;
        y++;
      }
      next[offset + k] = x;
      if (x >= n && y >= m) {
        trace.push(next);
        foundD = d;
        break outer;
      }
    }
    trace.push(next);
    v = next;
  }

  // Backtrack into a raw op list (one token per op), then coalesce.
  const raw: { type: OpType; aIdx?: number; bIdx?: number }[] = [];
  let x = n;
  let y = m;
  for (let d = foundD; d > 0; d--) {
    const prev = trace[d - 1];
    const k = x - y;
    let prevK: number;
    if (k === -d || (k !== d && prev[offset + k - 1] < prev[offset + k + 1])) {
      prevK = k + 1;
    } else {
      prevK = k - 1;
    }
    const prevX = prev[offset + prevK];
    const prevY = prevX - prevK;
    while (x > prevX && y > prevY) {
      raw.push({ type: 'eq', aIdx: x - 1, bIdx: y - 1 });
      x--;
      y--;
    }
    if (x === prevX) {
      raw.push({ type: 'ins', bIdx: y - 1 });
      y--;
    } else {
      raw.push({ type: 'del', aIdx: x - 1 });
      x--;
    }
  }
  while (x > 0 && y > 0) {
    raw.push({ type: 'eq', aIdx: x - 1, bIdx: y - 1 });
    x--;
    y--;
  }
  while (y > 0) {
    raw.push({ type: 'ins', bIdx: y - 1 });
    y--;
  }
  while (x > 0) {
    raw.push({ type: 'del', aIdx: x - 1 });
    x--;
  }
  raw.reverse();

  // Coalesce, ordering del before ins inside a replace block, eq tokens use
  // the B-side text (correct at-rest rendering of the newer version).
  const ops: DiffOp[] = [];
  let i = 0;
  while (i < raw.length) {
    const type = raw[i].type;
    if (type === 'eq') {
      const tokens: Token[] = [];
      while (i < raw.length && raw[i].type === 'eq') {
        tokens.push(b[raw[i].bIdx as number]);
        i++;
      }
      ops.push({ type: 'eq', tokens });
    } else {
      const dels: Token[] = [];
      const inss: Token[] = [];
      while (i < raw.length && raw[i].type !== 'eq') {
        if (raw[i].type === 'del') dels.push(a[raw[i].aIdx as number]);
        else inss.push(b[raw[i].bIdx as number]);
        i++;
      }
      if (dels.length) ops.push({ type: 'del', tokens: dels });
      if (inss.length) ops.push({ type: 'ins', tokens: inss });
    }
  }
  return ops;
}

export function diffText(a: string, b: string): DiffOp[] {
  return diffTokens(tokenize(a), tokenize(b));
}

export function charCount(ops: DiffOp[], type: OpType): number {
  let count = 0;
  for (const op of ops) {
    if (op.type !== type) continue;
    for (const token of op.tokens) count += token.text.length;
  }
  return count;
}
