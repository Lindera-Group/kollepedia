/** Typed client for the Kollepedia NG API (contract: server/app/schemas.py). */

import { clearSession } from './user.svelte';

const BASE = '/api/v1';

/** Terminal auth endpoints where a 401 is the real answer (bad credentials /
 * dead refresh cookie), never an expired access token — so they must NOT
 * trigger a refresh-retry (or, for /auth/refresh, recurse) or wipe the session. */
const AUTH_TERMINAL = new Set(['/auth/login', '/auth/register', '/auth/refresh']);

export interface CollectionOut {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  year: number | null;
  authoritative: boolean;
  licence: Record<string, unknown> | null;
  concept_count: number;
  // Iteration 2 (optional until the auth/orgs backend fills them):
  visibility?: 'public' | 'org_private' | 'private';
  edit_policy?: 'org' | 'anyone' | 'open';
  organisation?: { id: string; slug: string; name: string } | null;
  created_by?: string | null;
  editable?: boolean;
  // can_write = the caller may write versions here (UI-gating 2026-07-15);
  // editable = the caller may manage the collection (admin).
  can_write?: boolean;
  // Iteration 3 (lock & archive — optional until the backend ships them):
  is_locked?: boolean;
  /** False when the licence forbids redistribution: no bulk export, read on site. */
  export_allowed?: boolean;
  is_archived?: boolean;
  // Migration 007 — rich metadata recovered from the old prototype. `locales`
  // carries the long bilingual descriptions (markdown); the rest are provenance.
  credits?: string | null;
  source_url?: string | null;
  archive_url?: string | null;
  sources?: unknown | null;
  locales?: Partial<Record<'sv' | 'en', CollectionLocale>> | null;
  /** Paket B: the living author list — only on the detail endpoint. */
  contributors?: ContributorOut[] | null;
}

/** One row in a collection's author list (version + section authorship). */
export interface ContributorOut {
  handle: string;
  display_name: string;
  affiliation: string | null;
  activated: boolean;
  version_count: number;
  section_count: number;
}

export interface CollectionLocale {
  name?: string | null;
  short_description?: string | null;
  description?: string | null;
}

export interface UserOut {
  id: string;
  handle: string;
  display_name: string;
  affiliation: string | null;
}

export interface AnnotationOut {
  id: string;
  attr_type: string;
  start: number;
  end: number;
  quote: string | null;
  value: Record<string, unknown>;
}

export interface EndorsementOut {
  id: string;
  /** Display name of the endorser — denormalised org name on new stamps,
   * free text on historical rows without an organisation link. */
  body: string;
  organisation: { id: string; slug: string; name: string } | null;
  note: string | null;
  created_at: string;
  withdrawn_at: string | null;
  withdrawal_note: string | null;
}

export interface VersionOut {
  id: string;
  concept_id: string;
  branch_id: string | null;
  language: string;
  canonical_form: string;
  definition_md: string;
  status: string;
  tags: string[];
  note: string | null;
  provenance: Record<string, unknown>;
  created_at: string;
  created_by: UserOut | null;
  annotations: AnnotationOut[];
  endorsements: EndorsementOut[];
}

export interface EdgeOut {
  child_id: string;
  parent_id: string;
  edge_type: string;
  ordinal: number;
  note: string | null;
}

export interface BranchOut {
  id: string;
  name: string;
  head_version_id: string | null;
}

export interface ConceptGraphOut {
  concept_id: string;
  collection: CollectionOut;
  versions: VersionOut[];
  edges: EdgeOut[];
  branches: BranchOut[];
}

export interface RelationOut {
  id: string;
  relation_type: string;
  direction: 'out' | 'in';
  other_concept_id: string;
  other_canonical_form: string;
  other_collection_slug: string;
  note: string | null;
}

export interface TranslationOut {
  concept_id: string;
  version_id: string;
  language: string;
  canonical_form: string;
}

export interface TaxonomyValueOut {
  id: string;
  /** Swedish primary name — the taxonomy level is bilingual, unlike tags. */
  name: string;
  name_en: string | null;
  position: number;
}

export interface TaxonomyOut {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  scope: 'global' | 'collection';
  collection_id: string | null;
  /** SOFT minimum (UI/import guidance). */
  min_per_concept: number;
  /** HARD maximum when set — parts use 1. */
  max_per_concept: number | null;
  values: TaxonomyValueOut[];
}

/** One taxonomy's assigned values on a concept (assignment lives on the
 * CONCEPT, not the version). */
export interface ConceptTaxonomyOut {
  taxonomy_id: string;
  taxonomy_slug: string;
  taxonomy_name: string;
  scope: 'global' | 'collection';
  max_per_concept: number | null;
  values: TaxonomyValueOut[];
}

export interface TagCountOut {
  name: string;
  count: number;
}

export interface ConceptOut {
  id: string;
  collection: CollectionOut;
  created_at: string;
  head: VersionOut | null;
  branches: BranchOut[];
  relations: RelationOut[];
  translations: TranslationOut[];
  version_count: number;
  /** Rich-button counts (begreppssidans verktygsyta). Optional until the
   * backend ships them — render with `?? 0`. */
  watcher_count?: number;
  list_count?: number;
  comment_count?: number;
  proposal_count?: number;
  open_proposal_count?: number;
  activity_count?: number;
  taxonomies: ConceptTaxonomyOut[];
}

export interface MostWatchedItem {
  id: string;
  canonical_form: string;
  language: string;
  watcher_count: number;
  collection: { slug: string; name: string; year: number | null; visibility: string; has_org: boolean };
}

export interface ConceptListItem {
  id: string;
  canonical_form: string;
  language: string;
  definition_snippet: string;
  definition_snippet_md: string;
  tags: string[];
  categories: string[];
  status: string;
  collection_slug: string;
  collection_name: string;
  collection_year: number | null;
  collection_visibility: string;
  collection_has_org: boolean;
  version_count: number;
  updated_at: string;
}

export interface ConceptListOut {
  items: ConceptListItem[];
  total: number;
}

export interface StatsOut {
  collections: number;
  concepts: number;
  versions: number;
  relations: number;
  users: number;
}

export interface VersionCreatePayload {
  mode: 'revise' | 'branch' | 'synthesize' | 'translate';
  base_version_id: string;
  canonical_form: string;
  definition_md: string;
  language?: string;
  status?: string;
  tags?: string[];
  note?: string;
  branch_name?: string;
  extra_parent_ids?: string[];
  source_version_id?: string;
}

export interface ConceptCreatePayload {
  collection_id: string;
  canonical_form: string;
  language?: string;
  definition_md?: string;
  status?: string;
  tags?: string[];
  note?: string;
  translated_from_version_id?: string;
}

export interface ListItemOut {
  id: string;
  concept_id: string;
  version_id: string | null;
  follow_head: boolean;
  ordinal: number;
  note: string | null;
  canonical_form: string | null;
}

export interface ListOut {
  id: string;
  name: string;
  purpose: string | null;
  created_at: string;
  items: ListItemOut[];
}

export interface AiDraftPayload {
  intent: 'translate' | 'synthesize';
  version_ids: string[];
  target_language?: 'sv' | 'en';
  guidance?: string;
  model?: string;
}

export interface AiDraftOut {
  canonical_form: string;
  definition_md: string;
  note_suggestion: string;
  model: string;
  provider: string;
}

export class ApiError extends Error {
  status: number;
  /** English log/debug text — NEVER render this to the user; use
   * errorMessage() from $lib/errors, which maps `code` to a localized
   * message and falls back to localized generic copy. */
  detail: string;
  /** Machine-readable error code from the structured detail envelope
   * {code, message, params} — the localization contract with the server. */
  code?: string;
  /** Interpolation values for the localized message (apierr.* keys). */
  params?: Record<string, string | number>;
  /** The raw `detail` payload when the server answers with a structured
   * object (e.g. registration collisions: {code, message, params}). */
  detailData?: unknown;
  constructor(status: number, detail: unknown, path: string) {
    const text =
      typeof detail === 'string'
        ? detail
        : ((detail as { message?: string } | null)?.message ?? JSON.stringify(detail));
    super(`API ${status}: ${text} (${path})`);
    this.status = status;
    this.detail = text;
    if (typeof detail !== 'string') this.detailData = detail;
    if (detail && typeof detail === 'object') {
      const d = detail as { code?: unknown; params?: unknown };
      if (typeof d.code === 'string') this.code = d.code;
      if (d.params && typeof d.params === 'object') {
        this.params = d.params as Record<string, string | number>;
      }
    }
  }
}

function userHeader(): Record<string, string> {
  // SSR: no session storage on the server — render logged-out, no header.
  // Account-only (SPAM hardening): a session without a token is not an
  // identity — the old X-User signature path is gone.
  if (typeof localStorage === 'undefined') return {};
  try {
    const raw = localStorage.getItem('kollepedia-session');
    if (raw) {
      const session = JSON.parse(raw) as { token?: string | null };
      if (session.token) return { Authorization: `Bearer ${session.token}` };
    }
    return {};
  } catch {
    return {};
  }
}

type FetchLike = typeof fetch;

/** Small client factory so the same request logic can run bound either to the
 * global browser fetch (default `api` export) or to SvelteKit's `event.fetch`
 * inside load functions (see `serverApi`). Server-side, relative `/api/v1`
 * URLs resolve through hooks.server.ts, which proxies them to API_URL. */
function createClient(fetchFn?: FetchLike) {
  // Wrap instead of aliasing: calling a bare reference to window.fetch
  // throws an "Illegal invocation" in browsers.
  const f: FetchLike = fetchFn ?? ((input, init) => fetch(input, init));

  function doFetch(
    method: string,
    path: string,
    body?: unknown,
    extraHeaders?: Record<string, string>
  ): Promise<Response> {
    return f(BASE + path, {
      method,
      headers: {
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...userHeader(),
        ...extraHeaders
      },
      body: body !== undefined ? JSON.stringify(body) : undefined
    });
  }

  async function request<T>(
    method: string,
    path: string,
    body?: unknown,
    extraHeaders?: Record<string, string>
  ): Promise<T> {
    // Whether this request carried a session we could refresh. Captured up
    // front so a mid-flight token rotation doesn't change the decision.
    const authed = hasStoredToken() && !AUTH_TERMINAL.has(path.split('?')[0]);
    let res = await doFetch(method, path, body, extraHeaders);
    // An expired or rotated access token gets ONE transparent refresh-and-retry
    // (httpOnly cookie `kollepedia_refresh`) before the error surfaces. Applies
    // to reads too — GET /auth/me on the profile page is the common case, not
    // just writes. (hasStoredToken() is always false server-side, so SSR never
    // refreshes.)
    if (res.status === 401 && authed && (await tryRefresh())) {
      res = await doFetch(method, path, body, extraHeaders);
    }
    // A 401 that survives the refresh on an authenticated request means the
    // session is definitively dead (expired past the 30-day refresh window, or
    // the account/DB was reset). Clear it so the UI drops the phantom logged-in
    // state instead of silently 401-ing every authenticated read.
    if (res.status === 401 && authed) clearSession();
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail ?? detail;
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, detail, path);
    }
    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
  }

  async function get<T>(path: string): Promise<T> {
    return request<T>('GET', path);
  }

  return { request, get };
}

const { request, get } = createClient();

/** The public read surface, shared verbatim between the browser `api` object
 * and `serverApi` (SSR load functions). Reads only — writes need the
 * localStorage-backed session and stay browser-side. */
function createReadApi(get: <T>(path: string) => Promise<T>) {
  return {
    collections: () => get<CollectionOut[]>('/collections'),
    collection: (slug: string) => get<CollectionOut>(`/collections/${slug}`),
    concepts: (params: {
      q?: string;
      /** Comma-separated slugs — OR within the filter type. */
      collection?: string;
      language?: string;
      status?: string;
      /** Comma-separated tags — OR within the filter type. */
      tag?: string;
      /** Comma-separated global-category value ids — OR within the type. */
      category?: string;
      limit?: number;
      offset?: number;
    }) => {
      const search = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== '') search.set(key, String(value));
      }
      return get<ConceptListOut>(`/concepts?${search}`);
    },
    concept: (id: string) => get<ConceptOut>(`/concepts/${id}`),
    graph: (id: string) => get<ConceptGraphOut>(`/concepts/${id}/graph`),
    stats: () => get<StatsOut>('/stats'),
    users: (q = '') => get<UserOut[]>(`/users?q=${encodeURIComponent(q)}`),
    authors: (q = '', limit = 50) =>
      get<AuthorOut[]>(`/authors?q=${encodeURIComponent(q)}&limit=${limit}`),
    author: (handle: string) => get<AuthorDetailOut>(`/authors/${encodeURIComponent(handle)}`),
    version: (id: string) => get<VersionPermalinkOut>(`/versions/${id}`)
  };
}

/** API client for universal load functions. Pass the load event's `fetch`:
 * during SSR it routes through hooks.server.ts (API_URL proxy) with no
 * session header; on client-side navigations it behaves like `api`. */
export function serverApi(fetchFn: FetchLike) {
  const { get } = createClient(fetchFn);
  return createReadApi(get);
}

export const api = {
  // Public reads (shared surface with serverApi — see createReadApi)
  ...createReadApi(get),

  // Writes (dev-mode identity via X-User; see lib/user.svelte.ts)
  createConcept: (payload: ConceptCreatePayload) =>
    request<ConceptOut>('POST', '/concepts', payload),
  createVersion: (conceptId: string, payload: VersionCreatePayload) =>
    request<VersionOut>('POST', `/concepts/${conceptId}/versions`, payload),
  promote: (
    conceptId: string,
    payload: {
      version_id: string;
      note?: string;
      branch_name?: string;
      // Content overrides — the "edit a historical version" flow; absent = plain restore.
      canonical_form?: string;
      definition_md?: string;
      tags?: string[];
      status?: string;
    }
  ) => request<VersionOut>('POST', `/concepts/${conceptId}/promote`, payload),
  createRelation: (payload: {
    relation_type: string;
    from_concept_id: string;
    to_concept_id: string;
    note?: string;
  }) => request<{ id: string }>('POST', '/relations', payload),
  deleteRelation: (id: string) => request<void>('DELETE', `/relations/${id}`),

  // Lists
  lists: () => get<ListOut[]>('/lists'),
  list: (id: string) => get<ListOut>(`/lists/${id}`),
  createList: (payload: { name: string; purpose?: string }) =>
    request<ListOut>('POST', '/lists', payload),
  addListItem: (
    listId: string,
    payload: { concept_id: string; version_id?: string; follow_head?: boolean; note?: string }
  ) => request<ListOut>('POST', `/lists/${listId}/items`, payload),
  deleteListItem: (listId: string, itemId: string) =>
    request<void>('DELETE', `/lists/${listId}/items/${itemId}`),

  /** Direct-download URL for exports (open in new tab / href). */
  exportUrl: (kind: 'collections' | 'lists', idOrSlug: string, format: string) =>
    `${BASE}/${kind}/${idOrSlug}/export?format=${format}`,

  // AI drafts (BYOK — key passes through, never persisted server-side)
  aiDraft: (payload: AiDraftPayload, key: string) =>
    request<AiDraftOut>('POST', '/ai/draft', payload, {
      'X-LLM-Key': key,
      'X-LLM-Provider': 'anthropic'
    }),
  aiExtract: (payload: { text: string; language?: string }, key: string) =>
    request<{ rows: ImportRow[] }>('POST', '/ai/extract', payload, {
      'X-LLM-Key': key,
      'X-LLM-Provider': 'anthropic'
    }),

  // Auth
  challenge: () => get<PowChallenge>('/auth/challenge'),
  register: (payload: {
    email: string;
    display_name: string;
    password: string;
    handle?: string;
    claim?: boolean;
    /** Personal activation-link token — a verified claim skips manual review. */
    claim_token?: string;
    pow: PowSolution;
    website?: string;
  }) => request<AuthOut>('POST', '/auth/register', payload),
  login: (payload: { identifier?: string; handle?: string; password: string }) =>
    request<AuthOut>('POST', '/auth/login', payload),
  me: () => get<AuthUser>('/auth/me'),
  patchMe: (payload: {
    display_name?: string;
    affiliation?: string;
    bio?: string;
    web_url?: string;
  }) => request<AuthUser>('PATCH', '/auth/me', payload),

  // Organisations
  orgs: () => get<OrgOut[]>('/orgs'),
  org: (slug: string) => get<OrgOut>(`/orgs/${slug}`),
  createOrg: (payload: { name: string; slug: string; org_type?: OrgType }) =>
    request<OrgOut>('POST', '/orgs', payload),
  addOrgMember: (slug: string, payload: { handle: string; role: string; kind?: string }) =>
    request<OrgOut>('POST', `/orgs/${slug}/members`, payload),
  patchOrgMember: (slug: string, userId: string, payload: { role?: string; kind?: string }) =>
    request<OrgOut>('PATCH', `/orgs/${slug}/members/${userId}`, payload),
  removeOrgMember: (slug: string, userId: string) =>
    request<void>('DELETE', `/orgs/${slug}/members/${userId}`),
  approveOrg: (slug: string, payload?: { org_type?: OrgType }) =>
    request<OrgOut>('POST', `/orgs/${slug}/approve`, payload),
  transferOrgOwner: (slug: string, userId: string) =>
    request<OrgOut>('POST', `/orgs/${slug}/owner`, { user_id: userId }),
  /** The member's own author-page visibility switch for one membership. */
  patchMyMembership: (slug: string, isPublic: boolean) =>
    request<OrgOut>('PATCH', `/orgs/${slug}/my-membership`, { is_public: isPublic }),

  // Collections management
  createCollection: (payload: CollectionEditPayload & { slug: string }) =>
    request<CollectionOut>('POST', '/collections', payload),
  patchCollection: (slug: string, payload: CollectionEditPayload) =>
    request<CollectionOut>('PATCH', `/collections/${slug}`, payload),

  // Taxonomies (curated vocabularies: global categories + collection parts)
  taxonomies: (collection?: string) =>
    get<TaxonomyOut[]>(`/taxonomies${collection ? `?collection=${encodeURIComponent(collection)}` : ''}`),
  createTaxonomy: (payload: {
    slug: string;
    name: string;
    description?: string;
    scope: 'global' | 'collection';
    collection_id?: string;
    min_per_concept?: number;
    max_per_concept?: number;
  }) => request<TaxonomyOut>('POST', '/taxonomies', payload),
  createTaxonomyValue: (taxonomyId: string, name: string) =>
    request<TaxonomyValueOut>('POST', `/taxonomies/${taxonomyId}/values`, { name }),
  renameTaxonomyValue: (valueId: string, name: string) =>
    request<TaxonomyValueOut>('PATCH', `/taxonomy-values/${valueId}`, { name }),
  deleteTaxonomyValue: (valueId: string) =>
    request<void>('DELETE', `/taxonomy-values/${valueId}`),
  assignTaxonomyValues: (conceptId: string, taxonomyId: string, valueIds: string[]) =>
    request<TaxonomyValueOut[]>('PUT', `/concepts/${conceptId}/taxonomies/${taxonomyId}`, {
      value_ids: valueIds
    }),
  tagSuggestions: (q: string, collection?: string) =>
    get<TagCountOut[]>(
      `/tags?q=${encodeURIComponent(q)}${collection ? `&collection=${encodeURIComponent(collection)}` : ''}`
    ),

  // Import
  importTemplateUrl: (slug: string) => `${BASE}/collections/${slug}/import/template?format=csv`,
  importFile: async (slug: string, file: File, dryRun: boolean) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE}/collections/${slug}/import?dry_run=${dryRun}`, {
      method: 'POST',
      headers: userHeader(),
      body: form
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail ?? detail;
      } catch {
        /* non-JSON */
      }
      throw new ApiError(res.status, detail, `/collections/${slug}/import`);
    }
    return res.json() as Promise<ImportResult>;
  },
  importRows: (slug: string, rows: ImportRow[], dryRun: boolean) =>
    request<ImportResult>('POST', `/collections/${slug}/import-rows`, {
      rows,
      dry_run: dryRun
    })
};

export interface AuthUser {
  id: string;
  handle: string;
  display_name: string;
  affiliation: string | null;
  bio?: string | null;
  web_url?: string | null;
  email?: string | null;
  email_verified?: boolean;
  is_super_admin: boolean;
  /** Manual account review (SPAM defence): 'pending' reads but cannot write. */
  review_status?: 'approved' | 'pending' | 'rejected';
  /** ALL active memberships (multi-org 2026-07) — replaces `organisation`. */
  memberships: SessionMembership[];
}

export interface SessionMembership {
  id: string;
  slug: string;
  name: string;
  role: string;
  kind: 'member' | 'guest';
  is_public: boolean;
  is_owner: boolean;
}

/** Proof-of-work challenge from GET /auth/challenge (self-hosted bot gate). */
export interface PowChallenge {
  salt: string;
  issued: number;
  expires: number;
  bits: number;
  signature: string;
}

export type PowSolution = PowChallenge & { number: number };

export interface AuthOut {
  token: string;
  user: AuthUser;
}

export interface OrgMemberOut {
  user_id: string;
  handle: string;
  display_name: string;
  role: string;
  kind: 'member' | 'guest';
  is_public: boolean;
}

export type OrgType = 'commercial' | 'academy' | 'industry_association';

export interface OrgOut {
  id: string;
  slug: string;
  name: string;
  is_approved: boolean;
  created_at: string;
  members: OrgMemberOut[];
  /** Iteration 3 — optional until the backend ships suspension. */
  is_suspended?: boolean;
  /** commercial → betalkonto (badge-only placeholder); academy/industry_association → fee-exempt. */
  org_type?: OrgType | null;
  /** The ONE user carrying economic responsibility (unique per user). */
  owner_user_id?: string | null;
}

export interface CollectionEditPayload {
  name?: string;
  description?: string | null;
  year?: number | null;
  licence?: { label?: string; url?: string } | null;
  organisation_id?: string | null;
  visibility?: 'public' | 'org_private' | 'private';
  edit_policy?: 'org' | 'anyone';
  authoritative?: boolean;
  // Iteration 3 — lock & archive toggles (manage rights; server enforces):
  is_locked?: boolean;
  is_archived?: boolean;
  // Migration 007/008 — editable provenance (manage rights):
  credits?: string | null;
  source_url?: string | null;
  archive_url?: string | null;
}

export interface ImportRow {
  canonical_form: string;
  language?: string;
  definition: string;
  status?: string;
  tags?: string;
  note?: string;
  author?: string;
  author_affiliation?: string;
  variants?: string;
  related_to?: string;
  broader?: string;
  narrower?: string;
  exact_match?: string;
  translation_of?: string;
  source?: string;
}

export interface ImportResult {
  rows_total: number;
  created: number;
  errors: { row: number; message: string }[];
  warnings: string[];
  dry_run: boolean;
}

// --- Authors & outreach (unified author/user surface) -----------------------

export interface AuthorCollectionRef {
  slug: string;
  name: string;
}

export interface AuthorMembership {
  org_slug: string;
  org_name: string;
  role: string;
  kind: 'member' | 'guest';
  /** Only serialised as false for super-admin viewers (opt-out rows). */
  is_public: boolean;
  /** Only ever non-null for super-admin viewers (ended memberships). */
  ended_at: string | null;
}

export interface AuthorOut {
  id: string;
  handle: string;
  display_name: string;
  affiliation: string | null;
  web_url: string | null;
  bio?: string | null;
  /** true = has a password (claimed account); false = historical imported author. */
  activated: boolean;
  /** false = suspended account (super admins may restore). */
  is_active: boolean;
  memberships: AuthorMembership[];
  version_count: number;
  section_count: number;
  concept_count: number;
  collections: AuthorCollectionRef[];
}

export interface AuthorConceptRef {
  id: string;
  canonical_form: string;
  collection_slug: string;
  collection_name: string;
}

export interface AuthorDetailOut extends AuthorOut {
  concepts: AuthorConceptRef[];
}

export type OutreachStatus = 'contacted' | 'opted_out' | null;

export interface OutreachRow extends AuthorOut {
  outreach_status: OutreachStatus;
  outreach_note: string | null;
  outreach_updated_at: string | null;
}

export interface OutreachPatchPayload {
  status: OutreachStatus;
  note?: string | null;
  confirm_clear_opt_out?: boolean;
}

export function listAuthors(q = '', limit = 50): Promise<AuthorOut[]> {
  return get<AuthorOut[]>(`/authors?q=${encodeURIComponent(q)}&limit=${limit}`);
}

export function getAuthor(handle: string): Promise<AuthorDetailOut> {
  return get<AuthorDetailOut>(`/authors/${encodeURIComponent(handle)}`);
}

export function listOutreach(): Promise<OutreachRow[]> {
  return get<OutreachRow[]>('/admin/outreach');
}

export function patchOutreach(userId: string, payload: OutreachPatchPayload): Promise<OutreachRow> {
  return request<OutreachRow>('PATCH', `/admin/outreach/${userId}`, payload);
}

export interface ActivationLinkOut {
  /** Relative URL (/activate?handle=…&token=…) — prepend origin when sharing. */
  url: string;
  expires_at: string;
}

/** Mint a personal one-time activation link for an unclaimed author (super
 * admin). A claim carrying the token is approved without manual review. */
export function mintActivationLink(userId: string): Promise<ActivationLinkOut> {
  return request<ActivationLinkOut>('POST', `/admin/outreach/${userId}/activation-link`);
}

// --- Iteration 3: auth hardening, endorsements, admin users, org suspension -----

const SESSION_KEY = 'kollepedia-session';

export interface RefreshOut {
  token: string;
  user?: AuthUser;
}

function hasStoredToken(): boolean {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return false;
    return Boolean((JSON.parse(raw) as { token?: string | null }).token);
  } catch {
    return false;
  }
}

/** Persist a rotated access token so subsequent `userHeader()` calls pick it up. */
function storeToken(token: string): void {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return;
    const session = JSON.parse(raw) as Record<string, unknown>;
    session.token = token;
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    /* private mode */
  }
}

let refreshInFlight: Promise<boolean> | null = null;

/** Silent refresh used by the 401-retry wrapper. Bare fetch — must not recurse.
 *
 * Single-flight: the refresh cookie ROTATES on every /auth/refresh (server
 * revokes the presented token), so concurrent 401s must share ONE refresh.
 * If each fired its own, the first would revoke the cookie and the rest would
 * replay a now-dead token, 401, and wrongly clear a perfectly valid session. */
function tryRefresh(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${BASE}/auth/refresh`, { method: 'POST' });
      if (!res.ok) return false;
      const data = (await res.json()) as RefreshOut;
      if (!data?.token) return false;
      storeToken(data.token);
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

/** Like request(), but tolerates empty success bodies (200 without JSON / 204). */
async function requestVoid(method: string, path: string, body?: unknown): Promise<void> {
  try {
    await request<unknown>(method, path, body);
  } catch (e) {
    if (e instanceof SyntaxError) return; // 2xx with empty body
    throw e;
  }
}

/** Rotate the access token via the httpOnly refresh cookie. Stores the new token. */
export async function refresh(): Promise<RefreshOut> {
  const out = await request<RefreshOut>('POST', '/auth/refresh');
  if (out?.token) storeToken(out.token);
  return out;
}

/** Revoke the refresh cookie server-side. Caller clears the local session. */
export function logout(): Promise<void> {
  return requestVoid('POST', '/auth/logout');
}

export function changePassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  return requestVoid('POST', '/auth/password', payload);
}

/** Consume a one-time reset token (from an admin-created link, /reset?token=). */
export function resetPassword(token: string, newPassword: string): Promise<void> {
  return requestVoid('POST', '/auth/reset', { token, new_password: newPassword });
}

// Admin: users

export type AdminUserFilter = 'all' | 'active' | 'inactive' | 'admins' | 'pending';

export interface AdminUserOut {
  id: string;
  handle: string;
  display_name: string;
  email: string | null;
  affiliation?: string | null;
  is_active: boolean;
  is_super_admin: boolean;
  review_status?: 'approved' | 'pending' | 'rejected';
  review_reason?: string | null;
  created_at: string;
  memberships: {
    id: string;
    slug: string;
    name: string;
    role: string;
    kind: 'member' | 'guest';
    is_public: boolean;
  }[];
  version_count?: number;
  concept_count?: number;
}

export function adminUsers(q = '', filter: AdminUserFilter = 'all'): Promise<AdminUserOut[]> {
  return get<AdminUserOut[]>(`/admin/users?q=${encodeURIComponent(q)}&filter=${filter}`);
}

export function patchAdminUser(
  id: string,
  payload: { is_active?: boolean; is_super_admin?: boolean; review_status?: string }
): Promise<AdminUserOut> {
  return request<AdminUserOut>('PATCH', `/admin/users/${id}`, payload);
}

export interface ResetLinkOut {
  url: string;
  expires_at: string;
}

export function adminResetLink(id: string): Promise<ResetLinkOut> {
  return request<ResetLinkOut>('POST', `/admin/users/${id}/reset-link`);
}

/** Guardrail G5: the append-only super-admin audit log. */
export interface AdminEventOut {
  id: string;
  actor_id: string;
  actor_handle: string | null;
  action: string;
  target_type: string;
  target_id: string;
  note: string | null;
  created_at: string;
}

export function adminEvents(limit = 100): Promise<AdminEventOut[]> {
  return get<AdminEventOut[]>(`/admin/events?limit=${limit}`);
}

// Org suspension (super admin)

export function suspendOrg(slug: string): Promise<OrgOut> {
  return request<OrgOut>('POST', `/orgs/${slug}/suspend`);
}

export function unsuspendOrg(slug: string): Promise<OrgOut> {
  return request<OrgOut>('POST', `/orgs/${slug}/unsuspend`);
}

// Endorsements (VISION §4.3 — write path; rights enforced server-side)

export function endorse(
  versionId: string,
  payload: { note: string; organisation_id?: string }
): Promise<EndorsementOut> {
  return request<EndorsementOut>('POST', `/versions/${versionId}/endorsements`, payload);
}

export function withdrawEndorsement(
  id: string,
  payload: { note: string }
): Promise<EndorsementOut> {
  return request<EndorsementOut>('POST', `/endorsements/${id}/withdraw`, payload);
}

// ── Iteration 4: email, proposals, discussions, watching, prompts, permalinks ──

export interface ProposalOut {
  id: string;
  concept_id: string;
  canonical_form: string;
  collection_slug: string;
  source_branch_name: string;
  target_branch: string;
  title: string;
  description: string | null;
  status: 'open' | 'merged' | 'rejected' | 'withdrawn';
  created_by: UserOut | null;
  created_at: string;
  resolved_by: UserOut | null;
  resolved_at: string | null;
  resolution_note: string | null;
  source_head: VersionOut | null;
  target_head: VersionOut | null;
  base_version_id: string | null;
}

export interface CommentOut {
  id: string;
  concept_id: string;
  proposal_id: string | null;
  body: string;
  created_by: UserOut | null;
  created_at: string;
}

export interface ActivityItem {
  kind:
    | 'version'
    | 'endorsement'
    | 'comment'
    | 'proposal'
    | 'proposal_merged'
    | 'proposal_rejected'
    | 'proposal_withdrawn'
    | 'branch'
    | 'merge';
  at: string;
  actor: UserOut | null;
  concept_id: string;
  canonical_form: string;
  /** Language-neutral payload (note/title/body) — prefix with a localized
   * label per kind (activityKindLabel) when rendering. */
  summary: string;
  /** The version the event anchors to on the timeline (null for e.g.
   * comments). Optional until the backend ships it. */
  version_id?: string | null;
}

export interface SavedPromptOut {
  id: string;
  name: string;
  intent: 'synthesize' | 'translate' | 'extract';
  text: string;
  shared: boolean;
  owner_handle: string | null;
}

export interface VersionPermalinkOut extends VersionOut {
  collection: { slug: string; name: string; year: number | null; visibility: string; has_org: boolean };
  is_head: boolean;
}

export interface OutboxMessage {
  id: string;
  to_addr: string;
  subject: string;
  body_text: string;
  template: string;
  status: 'queued' | 'sent' | 'blocked' | 'outbox';
  created_at: string;
  sent_at: string | null;
}

export const night4 = {
  // Email
  setEmail: (email: string) => request<void>('POST', '/auth/email', { email }),
  verifyEmail: (token: string) => request<void>('POST', '/auth/verify-email', { token }),
  forgot: (handleOrEmail: string) =>
    request<void>('POST', '/auth/forgot', { handle_or_email: handleOrEmail }),
  outbox: (limit = 50) => get<OutboxMessage[]>(`/admin/outbox?limit=${limit}`),

  // Proposals
  createProposal: (
    conceptId: string,
    payload: { branch_name: string; title: string; description?: string }
  ) => request<ProposalOut>('POST', `/concepts/${conceptId}/proposals`, payload),
  proposals: (params: { status?: string; collection?: string; concept_id?: string } = {}) => {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) if (value) search.set(key, value);
    return get<ProposalOut[]>(`/proposals?${search}`);
  },
  proposal: (id: string) => get<ProposalOut>(`/proposals/${id}`),
  mergeProposal: (id: string, note: string) =>
    request<ProposalOut>('POST', `/proposals/${id}/merge`, { note }),
  rejectProposal: (id: string, note: string) =>
    request<ProposalOut>('POST', `/proposals/${id}/reject`, { note }),
  withdrawProposal: (id: string) => request<ProposalOut>('POST', `/proposals/${id}/withdraw`),

  // Discussions
  conceptComments: (conceptId: string) => get<CommentOut[]>(`/concepts/${conceptId}/comments`),
  proposalComments: (proposalId: string) => get<CommentOut[]>(`/proposals/${proposalId}/comments`),
  addConceptComment: (conceptId: string, body: string) =>
    request<CommentOut>('POST', `/concepts/${conceptId}/comments`, { body }),
  addProposalComment: (proposalId: string, body: string) =>
    request<CommentOut>('POST', `/proposals/${proposalId}/comments`, { body }),
  deleteComment: (id: string) => request<void>('DELETE', `/comments/${id}`),

  // Watching & activity
  watch: (conceptId: string) => request<void>('PUT', `/concepts/${conceptId}/watch`),
  unwatch: (conceptId: string) => request<void>('DELETE', `/concepts/${conceptId}/watch`),
  conceptActivity: (conceptId: string, limit = 30) =>
    get<ActivityItem[]>(`/concepts/${conceptId}/activity?limit=${limit}`),
  myActivity: (limit = 50) => get<ActivityItem[]>(`/activity?limit=${limit}`),
  mostWatched: (limit = 5) => get<MostWatchedItem[]>(`/concepts/most-watched?limit=${limit}`),
  unseenActivityCount: () => get<{ count: number }>(`/activity/unseen-count`),
  markActivitySeen: () => request<void>('POST', '/activity/seen'),

  // Saved prompts
  prompts: (intent?: string) => get<SavedPromptOut[]>(`/prompts${intent ? `?intent=${intent}` : ''}`),
  createPrompt: (payload: { name: string; intent: string; text: string; shared?: boolean }) =>
    request<SavedPromptOut>('POST', '/prompts', payload),
  deletePrompt: (id: string) => request<void>('DELETE', `/prompts/${id}`),

  // Permalinks
  version: (id: string) => get<VersionPermalinkOut>(`/versions/${id}`)
};

/** AI provider selection (BYOK): OpenAI-compatible providers like Berget.ai. */
export function aiHeaders(key: string, provider: string, baseUrl?: string): Record<string, string> {
  const headers: Record<string, string> = { 'X-LLM-Key': key, 'X-LLM-Provider': provider };
  if (baseUrl) headers['X-LLM-Base-URL'] = baseUrl;
  return headers;
}

export const aiDraftWith = (
  payload: AiDraftPayload,
  key: string,
  provider = 'anthropic',
  baseUrl?: string
) => request<AiDraftOut>('POST', '/ai/draft', payload, aiHeaders(key, provider, baseUrl));

export const aiExtractWith = (
  payload: { text: string; language?: string },
  key: string,
  provider = 'anthropic',
  baseUrl?: string
) =>
  request<{ rows: ImportRow[] }>('POST', '/ai/extract', payload, aiHeaders(key, provider, baseUrl));
