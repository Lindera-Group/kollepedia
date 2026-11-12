import { describe, expect, it } from 'vitest';
import type { BranchOut, ConceptGraphOut, EdgeOut, VersionOut } from '$lib/api';
import { ancestryOf, buildLanes, fullLanePath } from './graph';

function version(id: string, created: string): VersionOut {
  return {
    id,
    concept_id: 'c1',
    branch_id: null,
    language: 'sv',
    canonical_form: id,
    definition_md: '',
    status: 'draft',
    tags: [],
    note: null,
    provenance: {},
    created_at: created,
    created_by: null,
    annotations: [],
    endorsements: []
  };
}

function edge(parent: string, child: string, type = 'revised_from', ordinal = 0): EdgeOut {
  return { parent_id: parent, child_id: child, edge_type: type, ordinal, note: null };
}

function branch(name: string, head: string | null): BranchOut {
  return { id: `branch-${name}`, name, head_version_id: head };
}

function graphOf(
  versions: VersionOut[],
  edges: EdgeOut[],
  branches: BranchOut[]
): ConceptGraphOut {
  return {
    concept_id: 'c1',
    collection: {} as ConceptGraphOut['collection'],
    versions,
    edges,
    branches
  };
}

/** main: m1 → m2 → m3 → m4; branch 'b': m2 → b1 → b2. */
const base = graphOf(
  [
    version('m1', '2020-01-01T00:00:00Z'),
    version('m2', '2021-01-01T00:00:00Z'),
    version('m3', '2022-01-01T00:00:00Z'),
    version('m4', '2023-01-01T00:00:00Z'),
    version('b1', '2022-06-01T00:00:00Z'),
    version('b2', '2024-01-01T00:00:00Z')
  ],
  [
    edge('m1', 'm2'),
    edge('m2', 'm3'),
    edge('m3', 'm4'),
    edge('m2', 'b1'),
    edge('b1', 'b2')
  ],
  [branch('main', 'm4'), branch('b', 'b2')]
);

describe('buildLanes', () => {
  it('lays out main as the trunk and the branch as a lane after its fork', () => {
    const model = buildLanes(base, 'main');
    expect(model.mainPath.map((v) => v.id)).toEqual(['m1', 'm2', 'm3', 'm4']);
    expect(model.lanes).toHaveLength(1);
    const lane = model.lanes[0];
    expect(lane.name).toBe('b');
    expect(lane.parent).toBe('main');
    expect(lane.forkIndex).toBe(1); // diverges at m2
    expect(lane.versions.map((v) => v.id)).toEqual(['b1', 'b2']); // only AFTER the fork, ascending
    expect(lane.headId).toBe('b2');
    expect(lane.row).toBe(1);
  });

  it('keeps the layout selection-independent: selecting the branch changes nothing', () => {
    expect(buildLanes(base, 'b')).toEqual(buildLanes(base, 'main'));
  });

  it('skips branches whose head is on main, has no head, or never touches the trunk', () => {
    const orphan = version('o1', '2022-03-01T00:00:00Z');
    const graph = graphOf(
      [...base.versions, orphan],
      base.edges,
      [
        ...base.branches,
        branch('on-main', 'm3'),
        branch('headless', null),
        branch('disconnected', 'o1')
      ]
    );
    const model = buildLanes(graph, 'main');
    expect(model.lanes.map((l) => l.name)).toEqual(['b']);
  });

  it('sorts multiple lanes by fork index, then name', () => {
    const graph = graphOf(
      [
        ...base.versions,
        version('c1v', '2023-06-01T00:00:00Z'),
        version('a1v', '2023-07-01T00:00:00Z')
      ],
      [...base.edges, edge('m3', 'c1v'), edge('m3', 'a1v')],
      [...base.branches, branch('c', 'c1v'), branch('a', 'a1v')]
    );
    const model = buildLanes(graph, 'main');
    expect(model.lanes.map((l) => [l.name, l.forkIndex])).toEqual([
      ['b', 1],
      ['a', 2],
      ['c', 2]
    ]);
    expect(model.lanes.map((l) => l.row)).toEqual([1, 2, 3]); // unique rows, row order
  });

  it('falls back to the selected branch as trunk when no main branch exists', () => {
    const graph = graphOf(base.versions, base.edges, [
      branch('trunkish', 'm4'),
      branch('b', 'b2')
    ]);
    const model = buildLanes(graph, 'trunkish');
    expect(model.mainPath.map((v) => v.id)).toEqual(['m1', 'm2', 'm3', 'm4']);
    expect(model.lanes.map((l) => l.name)).toEqual(['b']);
  });
});

/** Nested fixture with real branched_from fork edges:
 * main: m1 → m2 → m3 → m4
 * b:    m2 ⤴ b1 → b2          (fork on main)
 * nb:   b1 ⤴ n1 → n2          (fork on lane b — branch of branch)
 * c:    m3 ⤴ c1               (second trunk-level lane) */
const nested = graphOf(
  [
    version('m1', '2020-01-01T00:00:00Z'),
    version('m2', '2021-01-01T00:00:00Z'),
    version('m3', '2022-01-01T00:00:00Z'),
    version('m4', '2023-01-01T00:00:00Z'),
    version('b1', '2022-06-01T00:00:00Z'),
    version('b2', '2024-01-01T00:00:00Z'),
    version('n1', '2024-06-01T00:00:00Z'),
    version('n2', '2025-01-01T00:00:00Z'),
    version('c1', '2023-06-01T00:00:00Z')
  ],
  [
    edge('m1', 'm2'),
    edge('m2', 'm3'),
    edge('m3', 'm4'),
    edge('m2', 'b1', 'branched_from'),
    edge('b1', 'b2'),
    edge('b1', 'n1', 'branched_from'),
    edge('n1', 'n2'),
    edge('m3', 'c1', 'branched_from')
  ],
  [branch('main', 'm4'), branch('b', 'b2'), branch('nb', 'n2'), branch('c', 'c1')]
);

describe('buildLanes — nested branches', () => {
  it('resolves a branch-of-branch onto its parent lane with a parent-relative forkIndex', () => {
    const model = buildLanes(nested, 'main');
    const nb = model.lanes.find((l) => l.name === 'nb')!;
    expect(nb.parent).toBe('b');
    expect(nb.forkIndex).toBe(0); // b1 is index 0 within lane b's versions
    expect(nb.versions.map((v) => v.id)).toEqual(['n1', 'n2']);
    // The parent keeps its full material — b1 is NOT stolen by the child.
    const b = model.lanes.find((l) => l.name === 'b')!;
    expect(b.parent).toBe('main');
    expect(b.versions.map((v) => v.id)).toEqual(['b1', 'b2']);
  });

  it('stacks children above their parents with unique, collision-free rows', () => {
    const model = buildLanes(nested, 'main');
    const rows = new Map(model.lanes.map((l) => [l.name, l.row]));
    expect(rows.get('nb')!).toBeGreaterThan(rows.get('b')!);
    expect(new Set(rows.values()).size).toBe(model.lanes.length); // no collisions
    expect(model.lanes.map((l) => l.row)).toEqual([1, 2, 3]); // model is row-ordered
  });

  it('resolves three layers of nesting iteratively', () => {
    const graph = graphOf(
      [...nested.versions, version('d1', '2025-06-01T00:00:00Z')],
      [...nested.edges, edge('n1', 'd1', 'branched_from')],
      [...nested.branches, branch('dd', 'd1')]
    );
    const model = buildLanes(graph, 'main');
    const dd = model.lanes.find((l) => l.name === 'dd')!;
    expect(dd.parent).toBe('nb');
    expect(dd.forkIndex).toBe(0); // n1 is index 0 within lane nb's versions
    expect(dd.row).toBeGreaterThan(model.lanes.find((l) => l.name === 'nb')!.row);
  });

  it('skips a nested branch whose parent chain never resolves', () => {
    const orphan = version('o1', '2022-03-01T00:00:00Z');
    const stray = version('x1', '2022-09-01T00:00:00Z');
    const graph = graphOf(
      [...nested.versions, orphan, stray],
      [...nested.edges, edge('o1', 'x1', 'branched_from')],
      [...nested.branches, branch('stray', 'x1')]
    );
    const model = buildLanes(graph, 'main');
    expect(model.lanes.map((l) => l.name).sort()).toEqual(['b', 'c', 'nb']);
  });

  it('ancestryOf walks the whole nested chain back to the root (buildPath sanity)', () => {
    expect(ancestryOf(nested, 'n2').map((v) => v.id)).toEqual(['m1', 'm2', 'b1', 'n1', 'n2']);
  });

  it('fullLanePath reproduces the ancestry of each lane head', () => {
    const model = buildLanes(nested, 'main');
    for (const name of ['b', 'nb', 'c']) {
      const head = model.lanes.find((l) => l.name === name)!.headId;
      expect(fullLanePath(model, name).map((v) => v.id)).toEqual(
        ancestryOf(nested, head).map((v) => v.id)
      );
    }
    expect(fullLanePath(model, 'main')).toEqual(model.mainPath);
  });
});
