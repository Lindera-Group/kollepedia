/** Session identity — account-only (anonymous signatures were removed in the
 * SPAM-hardening pass: every write becomes immutable history and must be
 * attributable to an account). The JWT from /auth/login|register is sent as
 * Bearer; `currentUser.handle` non-empty ⇔ logged in. */

export interface OrgRef {
  id: string;
  slug: string;
  name: string;
  role: 'admin' | 'editor' | 'viewer';
  /** medlem/gäst — display semantics, orthogonal to role (multi-org 2026-07). */
  kind: 'member' | 'guest';
  /** Per-membership opt-out from the public author page. */
  is_public: boolean;
  /** True on the ONE org this user owns (economic responsibility). */
  is_owner: boolean;
}

export interface Session {
  handle: string;
  display_name: string;
  token: string | null;
  is_super_admin: boolean;
  /** 'pending' = account awaiting manual review (reads OK, writes blocked). */
  review_status?: 'approved' | 'pending' | 'rejected';
  /** ALL active memberships (multi-org 2026-07) — replaces `organisation`. */
  memberships: OrgRef[];
}

const KEY = 'kollepedia-session';

function initial(): Session {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const stored = { ...empty(), ...JSON.parse(raw) } as Session;
      // Legacy signature sessions (handle without token) are no longer valid.
      if (!stored.token) return empty();
      // Pre-multi-org sessions carry `organisation` instead of `memberships`
      // — normalise to an empty list; the next refresh fills it in.
      if (!Array.isArray(stored.memberships)) stored.memberships = [];
      return stored;
    }
  } catch {
    /* private mode */
  }
  return empty();
}

function empty(): Session {
  return {
    handle: '',
    display_name: '',
    token: null,
    is_super_admin: false,
    review_status: 'approved',
    memberships: []
  };
}

export const currentUser = $state<Session>(initial());

/** Orgs where the current user is admin — the set they can act for
 * (create collections, stamp endorsements, manage members). */
export function adminOrgs(): OrgRef[] {
  return currentUser.memberships.filter((m) => m.role === 'admin');
}

export function isOrgAdmin(orgId: string): boolean {
  return currentUser.memberships.some((m) => m.id === orgId && m.role === 'admin');
}

/** Cross-component "please open the login form" signal — e.g. the activity
 * bell when logged out. UserChip watches `requested` and opens its popover. */
export const authUi = $state({ requested: false });

export function requestLogin(): void {
  authUi.requested = true;
}

function persist(): void {
  try {
    if (currentUser.handle) localStorage.setItem(KEY, JSON.stringify(currentUser));
    else localStorage.removeItem(KEY);
  } catch {
    /* private mode */
  }
}

/** Login/registration result. */
export function setSession(session: Session): void {
  Object.assign(currentUser, { ...empty(), ...session });
  persist();
}

export function clearSession(): void {
  Object.assign(currentUser, empty());
  persist();
}
