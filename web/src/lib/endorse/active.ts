/** Endorsement rework 2026-07-11: "fastställd" is an organisation's
 * withdrawable flag on ONE version (endorsement records), not a version
 * status. The gold star everywhere keys off ACTIVE stamps. */
import type { EndorsementOut, VersionOut } from '$lib/api';

export function activeEndorsements(
  version: Pick<VersionOut, 'endorsements'>
): EndorsementOut[] {
  return version.endorsements.filter((e) => e.withdrawn_at === null);
}

export function hasActiveEndorsement(version: Pick<VersionOut, 'endorsements'>): boolean {
  return version.endorsements.some((e) => e.withdrawn_at === null);
}
