/** The admin console map — THE single source describing every admin and
 * superadmin surface in one pedagogical place. The hub (routes/admin) and the
 * nav gate both read from here, so a new admin tool is surfaced by adding one
 * entry (plus its i18n keys) — never by scattering another orphan route the
 * user can't find.
 *
 * Each item carries a `access` level; the hub filters sections/items against
 * the current session so a plain org-admin sees only what they may act on. */

import type { IconName } from '$lib/icons/icons';
import type { TranslationKey } from '$lib/i18n.svelte';
import { adminOrgs, currentUser } from '$lib/user.svelte';

/** Who may see a surface. `super` = platform superadmin only; `orgadmin` =
 * superadmin OR an admin of at least one organisation. */
export type AdminAccess = 'super' | 'orgadmin';

export interface AdminItem {
  href: string;
  icon: IconName;
  title: TranslationKey;
  desc: TranslationKey;
  access: AdminAccess;
}

export interface AdminSection {
  id: string;
  title: TranslationKey;
  desc: TranslationKey;
  access: AdminAccess;
  items: AdminItem[];
}

export const ADMIN_SECTIONS: AdminSection[] = [
  {
    id: 'platform',
    title: 'admin.sec_platform',
    desc: 'admin.sec_platform_desc',
    access: 'super',
    items: [
      {
        href: '/admin/users',
        icon: 'person',
        title: 'admin.users_title',
        desc: 'admin.users_desc',
        access: 'super'
      },
      {
        href: '/admin/taxonomies',
        icon: 'category',
        title: 'admin.taxonomies_title',
        desc: 'admin.taxonomies_desc',
        access: 'super'
      },
      {
        href: '/admin/events',
        icon: 'pulse',
        title: 'admin.events_title',
        desc: 'admin.events_desc',
        access: 'super'
      }
    ]
  },
  {
    id: 'outreach',
    title: 'admin.sec_outreach',
    desc: 'admin.sec_outreach_desc',
    access: 'super',
    items: [
      {
        href: '/admin/outreach',
        icon: 'share',
        title: 'admin.outreach_title',
        desc: 'admin.outreach_desc',
        access: 'super'
      },
      {
        href: '/admin/outbox',
        icon: 'mail',
        title: 'admin.outbox_title',
        desc: 'admin.outbox_desc',
        access: 'super'
      }
    ]
  },
  {
    id: 'orgs',
    title: 'admin.sec_orgs',
    desc: 'admin.sec_orgs_desc',
    access: 'orgadmin',
    items: [
      {
        href: '/orgs',
        icon: 'group',
        title: 'admin.orgs_title',
        desc: 'admin.orgs_desc',
        access: 'orgadmin'
      }
    ]
  }
];

/** Does the current session satisfy an access level? */
export function hasAdminAccess(access: AdminAccess): boolean {
  if (currentUser.is_super_admin) return true;
  if (access === 'orgadmin') return adminOrgs().length > 0;
  return false;
}

/** True when the user may reach the admin hub at all (drives the nav gate). */
export function canSeeAdminHub(): boolean {
  return currentUser.is_super_admin || adminOrgs().length > 0;
}

/** Sections the current session may see, each pruned to its allowed items. */
export function visibleAdminSections(): AdminSection[] {
  return ADMIN_SECTIONS.filter((s) => hasAdminAccess(s.access))
    .map((s) => ({ ...s, items: s.items.filter((i) => hasAdminAccess(i.access)) }))
    .filter((s) => s.items.length > 0);
}
