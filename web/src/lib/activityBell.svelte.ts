/** Header-bell unread state (runes module pattern, like theme/user).
 * The bell turns green + filled when the logged-in user has unseen events in
 * watched concepts; /activity marks everything seen on visit. */
import { night4 } from '$lib/api';
import { currentUser } from '$lib/user.svelte';

export const activityBell = $state({ unseen: 0 });

/** Refresh the unseen counter; silently a no-op when logged out or when the
 * backend has not shipped the endpoint yet. */
export async function refreshUnseen(): Promise<void> {
  if (!currentUser.token) {
    activityBell.unseen = 0;
    return;
  }
  try {
    const res = await night4.unseenActivityCount();
    activityBell.unseen = res.count;
  } catch {
    activityBell.unseen = 0;
  }
}

/** Mark the feed as seen (called by /activity) and clear the badge. */
export async function markSeen(): Promise<void> {
  if (!currentUser.token) return;
  try {
    await night4.markActivitySeen();
  } catch {
    /* endpoint not shipped yet — badge already cleared optimistically */
  }
  activityBell.unseen = 0;
}
