/** Path selection through the version DAG: follow a branch head's ancestry. */

import type { ConceptGraphOut, EdgeOut, VersionOut } from '$lib/api';

export interface Fork {
  /** Index in the current path where an alternative continuation exists. */
  pathIndex: number;
  /** Alternative branches whose lineage passes through this version. */
  options: { branchName: string; headId: string }[];
}

export interface PathModel {
  versions: VersionOut[];
  forks: Fork[];
  branchName: string;
}

function primaryParent(edges: EdgeOut[], childId: string, known: Set<string>): string | null {
  const parents = edges
    .filter((e) => e.child_id === childId && known.has(e.parent_id))
    .sort((a, b) => a.ordinal - b.ordinal);
  return parents.length ? parents[0].parent_id : null;
}

/** Walk primary parents from a head back to the root; returns oldest-first. */
export function ancestryOf(graph: ConceptGraphOut, headId: string): VersionOut[] {
  const byId = new Map(graph.versions.map((v) => [v.id, v]));
  const known = new Set(byId.keys());
  const path: VersionOut[] = [];
  let cursor: string | null = headId;
  const guard = new Set<string>();
  while (cursor && byId.has(cursor) && !guard.has(cursor)) {
    guard.add(cursor);
    path.push(byId.get(cursor)!);
    cursor = primaryParent(graph.edges, cursor, known);
  }
  path.reverse();
  return path;
}

/** Build the path for a branch plus the fork points where other branches diverge. */
export function buildPath(graph: ConceptGraphOut, branchName: string): PathModel {
  const branch =
    graph.branches.find((b) => b.name === branchName) ??
    graph.branches.find((b) => b.name === 'main') ??
    graph.branches[0];
  const headId = branch?.head_version_id ?? graph.versions[graph.versions.length - 1]?.id;
  const versions = headId ? ancestryOf(graph, headId) : [...graph.versions];
  const inPath = new Set(versions.map((v) => v.id));

  const forks: Fork[] = [];
  for (const other of graph.branches) {
    if (other.name === branch?.name || !other.head_version_id) continue;
    if (inPath.has(other.head_version_id)) continue;
    const otherPath = ancestryOf(graph, other.head_version_id);
    // Divergence = last version the two paths share.
    let shared = -1;
    for (let i = 0; i < otherPath.length; i++) {
      if (inPath.has(otherPath[i].id)) {
        shared = versions.findIndex((v) => v.id === otherPath[i].id);
      }
    }
    if (shared >= 0) {
      const existing = forks.find((f) => f.pathIndex === shared);
      const option = { branchName: other.name, headId: other.head_version_id };
      if (existing) existing.options.push(option);
      else forks.push({ pathIndex: shared, options: [option] });
    }
  }
  forks.sort((a, b) => a.pathIndex - b.pathIndex);
  return { versions, forks, branchName: branch?.name ?? 'main' };
}

/** One branch rendered as a lane above its parent (git-graph style). */
export interface Lane {
  /** Branch name. */
  name: string;
  /** What the lane forks from: 'main' (the trunk) or another lane's name. */
  parent: string;
  /** Index of the fork version within the PARENT's sequence: for a 'main'
   * parent an index into `mainPath`, otherwise into the parent lane's
   * `versions`. */
  forkIndex: number;
  /** Lane-only versions AFTER the fork, oldest first. */
  versions: VersionOut[];
  headId: string;
  /** Vertical row above the trunk (1 = nearest the rail). Rows are unique
   * and a child's row is always greater than its parent's, so nested lanes
   * stack ABOVE the lane they fork from. */
  row: number;
}

/** Layout model for the lane timeline: the mainline plus stacked branch lanes. */
export interface LaneModel {
  mainPath: VersionOut[];
  /** Ordered by row, ascending. */
  lanes: Lane[];
}

/** Git-graph layout: main as the trunk, one lane per branch — including
 * branches of branches. Lanes are resolved iteratively: first the ones
 * forking from the trunk, then the ones forking from already-placed lanes,
 * repeated until stable; unresolvable branches are skipped gracefully.
 *
 * The fork point is read from the structural `branched_from` edge (the last
 * one on the branch's ancestry — mode=branch always writes it). Branches
 * without such an edge (legacy/synthetic data) fall back to "everything
 * after the last version shared with already-placed material".
 *
 * The layout is selection-independent — `selectedBranch` only serves as the
 * trunk fallback when no 'main' branch exists. */
export function buildLanes(graph: ConceptGraphOut, selectedBranch: string): LaneModel {
  const trunk =
    graph.branches.find((b) => b.name === 'main') ??
    graph.branches.find((b) => b.name === selectedBranch) ??
    graph.branches[0];
  const headId = trunk?.head_version_id ?? graph.versions[graph.versions.length - 1]?.id;
  const mainPath = headId ? ancestryOf(graph, headId) : [...graph.versions];
  const indexOnMain = new Map(mainPath.map((v, i) => [v.id, i]));

  /** Where each already-laid-out version lives (the trunk or a placed lane). */
  const placement = new Map<string, { parent: string; index: number; row: number }>();
  mainPath.forEach((v, i) => placement.set(v.id, { parent: 'main', index: i, row: 0 }));

  interface Candidate {
    name: string;
    headId: string;
    path: VersionOut[];
    /** Fork version id (parent of the last branched_from step), if present. */
    forkId: string | null;
    /** Versions after the fork — the lane's own material. */
    own: VersionOut[];
  }

  let pending: Candidate[] = [];
  for (const branch of graph.branches) {
    if (branch.name === trunk?.name || !branch.head_version_id) continue;
    if (indexOnMain.has(branch.head_version_id)) continue;
    const path = ancestryOf(graph, branch.head_version_id);
    let forkIdx = -1;
    for (let i = 1; i < path.length; i++) {
      const step = graph.edges.find(
        (e) => e.child_id === path[i].id && e.parent_id === path[i - 1].id
      );
      if (step?.edge_type === 'branched_from') forkIdx = i - 1;
    }
    pending.push({
      name: branch.name,
      headId: branch.head_version_id,
      path,
      forkId: forkIdx >= 0 ? path[forkIdx].id : null,
      own: forkIdx >= 0 ? path.slice(forkIdx + 1) : []
    });
  }

  const lanes: Lane[] = [];
  let maxRow = 0;
  while (pending.length > 0) {
    // Structural forks whose fork version already has a home resolve first.
    let batch = pending.filter((c) => c.forkId !== null && placement.has(c.forkId));
    const dropped = new Set<Candidate>();
    if (batch.length === 0) {
      // Fallback round: diverge at the last version shared with anything placed.
      for (const cand of pending) {
        let lastShared = -1;
        for (let i = 0; i < cand.path.length; i++) {
          if (placement.has(cand.path[i].id)) lastShared = i;
        }
        if (lastShared < 0) continue; // maybe resolvable in a later round
        const own = cand.path.slice(lastShared + 1);
        if (own.length === 0) {
          dropped.add(cand); // fully covered by placed material — nothing to draw
          continue;
        }
        cand.forkId = cand.path[lastShared].id;
        cand.own = own;
        batch.push(cand);
      }
      if (batch.length === 0 && dropped.size === 0) break; // stable — skip the rest
    }
    const chosen = new Set(batch);
    batch.sort((a, b) => {
      const pa = placement.get(a.forkId!)!;
      const pb = placement.get(b.forkId!)!;
      return pa.row - pb.row || pa.index - pb.index || a.name.localeCompare(b.name);
    });
    for (const cand of batch) {
      const at = placement.get(cand.forkId!)!;
      maxRow += 1; // collision-free: each lane gets its own row above everything placed
      lanes.push({
        name: cand.name,
        parent: at.parent,
        forkIndex: at.index,
        versions: cand.own,
        headId: cand.headId,
        row: maxRow
      });
      cand.own.forEach((v, i) => placement.set(v.id, { parent: cand.name, index: i, row: maxRow }));
    }
    pending = pending.filter((c) => !chosen.has(c) && !dropped.has(c));
  }
  return { mainPath, lanes };
}

/** Full root-to-head version sequence for a lane ('main' → the trunk itself).
 * Walks the parent chain, so a branch-of-branch yields trunk prefix + each
 * ancestor lane's segment + its own versions — the same sequence ancestryOf
 * produces for the lane's head. */
export function fullLanePath(model: LaneModel, name: string): VersionOut[] {
  if (name === 'main') return model.mainPath;
  const lane = model.lanes.find((l) => l.name === name);
  if (!lane) return model.mainPath;
  const parentPath = fullLanePath(model, lane.parent);
  const parentLane = model.lanes.find((l) => l.name === lane.parent);
  // Fork position within the parent's FULL path: a lane's own versions are
  // the tail of its full path, so offset the parent-relative forkIndex.
  const forkPos = parentLane
    ? parentPath.length - parentLane.versions.length + lane.forkIndex
    : lane.forkIndex;
  return [...parentPath.slice(0, forkPos + 1), ...lane.versions];
}

/** Incoming edge type for each version in a path (what kind of step it was). */
export function stepTypes(graph: ConceptGraphOut, versions: VersionOut[]): (string | null)[] {
  return versions.map((v, i) => {
    if (i === 0) return null;
    const edge = graph.edges
      .filter((e) => e.child_id === v.id)
      .sort((a, b) => a.ordinal - b.ordinal)[0];
    return edge?.edge_type ?? null;
  });
}
