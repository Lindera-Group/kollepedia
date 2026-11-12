/** Kollepedia NG icon library — THE single source for every icon in the app.
 *
 * Rules (ui-guardrails §15): check this library FIRST; a new icon may only
 * be added here, never inlined ad hoc in a component. Grid 20×20, stroke 1.5,
 * round caps/joins, always currentColor (themes come free). Inactive =
 * outline (`o`), active = filled (`f`) + semantic color set by the caller
 * (watching = --ins-strong, endorsed = --endorsed, unread = --ins-strong).
 * Flat — no gradients, no shadows. One glyph per concept everywhere:
 * the rectangular speech bubble IS discussion, the dial clock IS history,
 * the bell IS watching/activity, at any size.
 */

const S = 'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"';

export const ICONS = {
  /** kryss — stäng/ta bort (borttagbara filterpiller, panelstängning) */
  close: {
    o: `<path d="M5 5l10 10M15 5L5 15" ${S}/>`
  },
  /** bock — bekräftat/sparat (status role="status") */
  check: {
    o: `<path d="M4 10.5l4 4 8-9" ${S}/>`
  },
  /** arkivlåda — arkiverad samling */
  archive: {
    o: `<path d="M3 5.5h14v3H3z" ${S}/><path d="M4.5 8.5v7a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-7" ${S}/><path d="M8 11.5h4" ${S}/>`
  },
  /** snöflinga — fryst version (frozen banner) */
  frozen: {
    o: `<path d="M10 3v14M4 6.5l12 7M16 6.5l-12 7M8 4l2 2 2-2M8 16l2-2 2 2" ${S}/>`
  },
  /** nål — fäst i lista (AddToList) */
  pin: {
    o: `<path d="M7.5 3h5l-.8 5 2.3 2.3H6l2.3-2.3z" ${S}/><path d="M10 12.6V17" ${S}/>`
  },
  /** gnista — AI-åtgärd (harmonisera) */
  sparkle: {
    o: `<path d="M10 2.5c.6 3.4 1.6 4.4 5 5-3.4.6-4.4 1.6-5 5-.6-3.4-1.6-4.4-5-5 3.4-.6 4.4-1.6 5-5z" ${S}/>`
  },
  /** vinkel — nedfällbar (dropdown-triggers) */
  chevron: {
    o: `<path d="M5 7.5l5 5 5-5" ${S}/>`
  },
  /** penna — redigera */
  edit: {
    o: `<path d="M3 17l1-4L14.5 2.5a1.4 1.4 0 0 1 2 0l1 1a1.4 1.4 0 0 1 0 2L7 16l-4 1Z" ${S}/>`
  },
  /** ringklocka — bevaka (knapp) + aktivitet (header). Ifylld = bevakar/olästa. */
  bell: {
    o: `<path d="M10 2.2a4.6 4.6 0 0 1 4.6 4.6c0 3.4 1 4.6 1.9 5.5.35.36.1 1-.4 1H3.9c-.5 0-.75-.64-.4-1 .9-.9 1.9-2.1 1.9-5.5A4.6 4.6 0 0 1 10 2.2Z" ${S}/><path d="M8.3 15.4a1.8 1.8 0 0 0 3.4 0" ${S}/>`,
    f: `<path d="M10 2.2a4.6 4.6 0 0 1 4.6 4.6c0 3.4 1 4.6 1.9 5.5.35.36.1 1-.4 1H3.9c-.5 0-.75-.64-.4-1 .9-.9 1.9-2.1 1.9-5.5A4.6 4.6 0 0 1 10 2.2Z" fill="currentColor" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M8.3 15.4a1.8 1.8 0 0 0 3.4 0" ${S}/>`
  },
  /** urtavla — historik */
  clock: {
    o: `<circle cx="10" cy="10" r="7.2" ${S}/><path d="M10 6v4.2l2.8 1.6" ${S}/>`
  },
  /** rader — listor */
  list: {
    o: `<path d="M4 5h12M4 10h12M4 15h8" ${S}/>`
  },
  /** förstoringsglas — sök (tomtillstånd, sökfält) */
  search: {
    o: `<circle cx="8.8" cy="8.8" r="5.6" ${S}/><path d="M13 13l4.2 4.2" ${S}/>`
  },
  /** kategori — kurerad klassificering */
  category: {
    o: `<path d="M3 4.5h8l6 5.5-6 5.5H3z" ${S}/><circle cx="6.4" cy="10" r="1.1" fill="currentColor" stroke="none"/>`
  },
  /** relation — typad koppling mellan begrepp */
  relation: {
    o: `<circle cx="5" cy="5.5" r="2.4" ${S}/><circle cx="15" cy="14.5" r="2.4" ${S}/><path d="M6.8 7.2l6.4 5.6" ${S}/>`
  },
  /** kugghjul — hantera begreppet. Symmetriskt: ring r5.6, 8 tänder till r7.8, nav r2.2. */
  gear: {
    o: `<circle cx="10" cy="10" r="5.6" ${S}/><circle cx="10" cy="10" r="2.2" ${S}/><path d="M10 4.4V2.2M10 17.8v-2.2M15.6 10h2.2M2.2 10h2.2M13.96 6.04l1.56-1.56M6.04 13.96l-1.56 1.56M13.96 13.96l1.56 1.56M6.04 6.04L4.48 4.48" ${S}/>`
  },
  /** nedladdningsbricka — exportera */
  download: {
    o: `<path d="M10 3.2v8.6M6.6 8.6l3.4 3.4 3.4-3.4" ${S}/><path d="M3.6 13.6v1.8a1.6 1.6 0 0 0 1.6 1.6h9.6a1.6 1.6 0 0 0 1.6-1.6v-1.8" ${S}/>`
  },
  /** uppladdningsbricka — importera */
  upload: {
    o: `<path d="M10 11.8V3.2M6.6 6.6L10 3.2l3.4 3.4" ${S}/><path d="M3.6 13.6v1.8a1.6 1.6 0 0 0 1.6 1.6h9.6a1.6 1.6 0 0 0 1.6-1.6v-1.8" ${S}/>`
  },
  /** dela — dokument med delningspil uppåt */
  share: {
    o: `<path d="M6.8 6.8H5.4A1.4 1.4 0 004 8.2v7.4A1.4 1.4 0 005.4 17h9.2a1.4 1.4 0 001.4-1.4V8.2a1.4 1.4 0 00-1.4-1.4h-1.4M10 12.8V3M7.2 5.6L10 2.8l2.8 2.8" ${S}/>`
  },
  /** e-post — kuvert */
  mail: {
    o: `<rect x="2.8" y="4.5" width="14.4" height="11" rx="1.5" ${S}/><path d="M3.6 5.6L10 10.9l6.4-5.3" ${S}/>`
  },
  /** LinkedIn — förenklad logotyp */
  linkedin: {
    o: `<rect x="2.8" y="2.8" width="14.4" height="14.4" rx="2" ${S}/><circle cx="6.5" cy="6.8" r="1.1" fill="currentColor" stroke="none"/><path d="M6.5 9.4v4.8M9.7 14.2V9.4m0 2c.4-1.3 1.3-2 2.3-2 1.2 0 2 .8 2 2.2v2.6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`
  },
  /** X — logotyp */
  xlogo: {
    o: `<path d="M11.7 8.6L17 2.5h-1.7l-4.4 5L7.3 2.5H2.9l5.7 8L2.9 17.5h1.7l4.9-5.6 4 5.6h4.4l-6.2-8.9z" fill="currentColor" stroke="none"/>`
  },
  /** länk — dela/permalänk */
  link: {
    o: `<path d="M8.5 11.5l3-3M7 13l-1.5 1.5a2.8 2.8 0 01-4-4L5 7M13 7l1.5-1.5a2.8 2.8 0 014 4L15 13" transform="translate(0.25 0)" ${S}/>`
  },
  /** glob — språk */
  globe: {
    o: `<circle cx="10" cy="10" r="7.2" ${S}/><path d="M2.8 10h14.4M10 2.8c-2.6 2.4-2.6 12 0 14.4M10 2.8c2.6 2.4 2.6 12 0 14.4" fill="none" stroke="currentColor" stroke-width="1.2"/>`
  },
  /** puls — aktivitet (begreppsnivå) */
  pulse: {
    o: `<path d="M2.5 11h3l2-6 3.5 10 2.5-7 1.5 3h2.5" ${S}/>`
  },
  /** rektangulär pratbubbla — diskussion, överallt */
  talk: {
    o: `<path d="M3 4.5h14v8.5H8l-3.5 3v-3H3z" ${S}/>`
  },
  /** stjärna — fastställd. Ifylld + --endorsed när aktiv. */
  star: {
    o: `<path d="M10 2.8l2.1 4.4 4.8.6-3.5 3.3.9 4.8L10 13.6l-4.3 2.3.9-4.8L3.1 7.8l4.8-.6z" ${S}/>`,
    f: `<path d="M10 2.8l2.1 4.4 4.8.6-3.5 3.3.9 4.8L10 13.6l-4.3 2.3.9-4.8L3.1 7.8l4.8-.6z" fill="currentColor" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>`
  },
  /** gren */
  branch: {
    o: `<circle cx="6" cy="4.5" r="1.8" ${S}/><circle cx="6" cy="15.5" r="1.8" ${S}/><circle cx="14.5" cy="8" r="1.8" ${S}/><path d="M6 6.3v7.4M14.5 9.8c0 3-3 4-6 4.4" ${S}/>`
  },
  /** merge */
  merge: {
    o: `<path d="M4 6.5h8.5l-2.3-2.3M12.5 6.5l-2.3 2.3" ${S}/><path d="M16 13.5H7.5l2.3-2.3M7.5 13.5l2.3 2.3" ${S}/>`
  },
  /** överlappande ark — ändringsförslag */
  proposal: {
    o: `<rect x="3.2" y="6.5" width="9.5" height="9.5" rx="1.2" ${S}/><path d="M7.5 4h8.3a1.2 1.2 0 0 1 1.2 1.2v8.3" ${S}/>`
  },
  /** uppslagen bok — publik samling (scope) */
  book: {
    o: `<path d="M10 5C8.4 3.8 6 3.4 3.4 3.4v12.2c2.6 0 5 .4 6.6 1.6 1.6-1.2 4-1.6 6.6-1.6V3.4C14 3.4 11.6 3.8 10 5Z" ${S}/><path d="M10 5v12.2" ${S}/>`
  },
  /** hänglås — låst/privat. Ifylld när samlingen är låst. */
  lock: {
    o: `<rect x="4.8" y="8.8" width="10.4" height="7.4" rx="1.4" ${S}/><path d="M7 8.8V6.4a3 3 0 0 1 6 0v2.4" ${S}/>`,
    f: `<rect x="4.8" y="8.8" width="10.4" height="7.4" rx="1.4" fill="currentColor" stroke="currentColor" stroke-width="1.5"/><path d="M7 8.8V6.4a3 3 0 0 1 6 0v2.4" ${S}/>`
  },
  /** två personer — organisation (scope) */
  group: {
    o: `<circle cx="7" cy="7.2" r="2.4" ${S}/><path d="M2.8 16c.5-3 2.2-4.4 4.2-4.4s3.7 1.4 4.2 4.4" ${S}/><circle cx="13.8" cy="7.8" r="2" ${S}/><path d="M12.6 11.9c2.4-.4 4.2 1 4.6 4.1" ${S}/>`
  },
  /** en person — individ (scope) */
  person: {
    o: `<circle cx="10" cy="6.8" r="2.8" ${S}/><path d="M4.6 16.6c.7-3.6 2.9-5.2 5.4-5.2s4.7 1.6 5.4 5.2" ${S}/>`
  }
} as const;

export type IconName = keyof typeof ICONS;

/** Raw inner-SVG markup for an icon; filled falls back to outline when the
 * icon has no filled variant. For non-Svelte contexts (e.g. string templates). */
export function iconMarkup(name: IconName, filled = false): string {
  const ic = ICONS[name];
  return filled && 'f' in ic ? (ic as { f: string }).f : ic.o;
}
