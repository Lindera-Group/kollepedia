import { describe, expect, it } from 'vitest';
import { editTargets } from './editTargets';

const graph = {
  branches: [
    { id: 'b1', name: 'main', head_version_id: 'v3' },
    { id: 'b2', name: 'forslag', head_version_id: 'v5' },
    { id: 'b3', name: 'tom', head_version_id: null }
  ]
};

describe('editTargets', () => {
  it('historical trunk version: main (promote-with-edits) + new branch', () => {
    const targets = editTargets(graph, { id: 'v1' });
    expect(targets).toEqual([
      { target: 'main', baseIsMainHead: false },
      { target: 'new-branch' }
    ]);
  });

  it('main head: main is a plain revise, no branch option', () => {
    const targets = editTargets(graph, { id: 'v3' });
    expect(targets).toEqual([
      { target: 'main', baseIsMainHead: true },
      { target: 'new-branch' }
    ]);
  });

  it('non-main branch head: offers continuing that branch too', () => {
    const targets = editTargets(graph, { id: 'v5' });
    expect(targets).toEqual([
      { target: 'main', baseIsMainHead: false },
      { target: 'branch', branchName: 'forslag' },
      { target: 'new-branch' }
    ]);
  });
});
