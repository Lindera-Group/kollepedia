/* i18n-content */
/** /pricing page content, per UI language. Content-by-language module: the
 * shape is typed as Record<Lang, PricingContent>, so a missing language or a
 * missing field is a compile-time error. Tier/feature order is meaningful and
 * must match between languages (first two tiers = individuals, rest = orgs). */
import type { Lang } from '$lib/i18n.svelte';

export interface Tier {
  name: string;
  price: string;
  audience: string;
  features: string[];
  note?: string;
  cta: { label: string; href: string } | null;
  highlight?: boolean;
}

export interface FeatureRow {
  label: string;
  values: [string, string, string, string];
}

export interface Principle {
  strong: string;
  text: string;
}

export interface PricingContent {
  metaDescription: string;
  heroTitle: string;
  heroTagline: string;
  groupIndividuals: string;
  groupOrgs: string;
  tiers: Tier[];
  compareTitle: string;
  featureColumn: string;
  /** Column headers for the comparison table (may carry soft hyphens). */
  tierColumns: [string, string, string, string];
  table: FeatureRow[];
  principlesTitle: string;
  principles: Principle[];
  /** Closing contact line; trusted authored HTML (contains <a>). */
  contactHtml: string;
}

const YES = '✓';
// Empty cell in the comparison table: en dash in Swedish, em dash in English.
const NO_SV = '–';
const NO_EN = '—';
export const NO_MARKS: ReadonlySet<string> = new Set([NO_SV, NO_EN]);
// AI is behind a feature flag during the beta — promised, not yet switched on.
const SOON_SV = 'kommer';
const SOON_EN = 'planned';

// Contact goes through the company's contact form: no address in the page.
const CONTACT_URL = 'https://linderagroup.com/#kontakt';

export const pricingContent: Record<Lang, PricingContent> = {
  sv: {
    metaDescription:
      'Kollepedia är gratis för alla som bygger sektorns gemensamma språk – individuellt, akademiskt och för branschens organisationer. Offert för organisationsbruk.',
    heroTitle: 'Gratis för alla som bygger det gemensamma språket.',
    heroTagline:
      'Kollepedias värde växer med varje aktör som delar sina begrepp. Därför är läsning, bidragande, akademiskt arbete och branschens kanonarbete kostnadsfritt – och organisationer som behöver privata ytor, drift och support bär kostnaderna.',
    groupIndividuals: 'För individer',
    groupOrgs: 'För organisationer',
    tiers: [
      {
        name: 'Individuell',
        price: 'Gratis',
        audience: 'Enskilda bidragsgivare',
        features: [
          'Läs och sök allt publikt innehåll – utan kostnad',
          'Riktig proveniens: varje bidrag i ditt namn',
          'Skapa begrepp, grenar och ändringsförslag',
          'Diskussioner, bevakning och aktivitetsflöde',
          'Personliga listor med fästa versioner + export',
          'Egna publika samlingar',
          'AI-funktioner med egen nyckel (BYOK) – under utveckling'
        ],
        cta: { label: 'Skapa konto', href: '/' }
      },
      {
        name: 'Akademi',
        price: 'Gratis',
        audience: 'Forskare och studenter',
        features: [
          'Full tillgång till alla organisationsfunktioner',
          'Registrering med akademisk e-postadress',
          'Första användaren skapar institutionen och blir dess administratör',
          'Org-funktioner aktiveras efter manuell granskning',
          'För icke-kommersiellt bruk'
        ],
        note: 'Institutioner granskas manuellt innan organisationsfunktionerna låses upp.',
        cta: { label: 'Registrera dig', href: '/' },
        highlight: true
      },
      {
        name: 'Branschorganisation',
        price: 'Gratis',
        audience: 'Branschens gemensamma aktörer – t.ex. Svensk Kollektivtrafik och Samtrafiken',
        features: [
          'Full tillgång till alla organisationsfunktioner',
          'Org-ägda samlingar: publika att läsa, redigerade av er',
          'Fastställanden i organisationens namn',
          'Lås, arkivering, roller och import i skala',
          'Ert kanonarbete är hela sektorns vinst – därför kostnadsfritt'
        ],
        note: 'Aktiveras efter kontakt – organisationen skapas fritt och granskas manuellt.',
        cta: { label: 'Kontakta oss', href: CONTACT_URL }
      },
      {
        name: 'Organisation',
        price: 'Offert',
        audience:
          'Offentliga och privata organisationer – RKM, operatörer, konsulter, systemleverantörer',
        features: [
          'Allt i Branschorganisation',
          'Org-privata samlingar för känsligt arbete',
          'Servermanagerade AI-nycklar och delade promptmallar – under utveckling',
          'Support och SLA',
          'Självhostad singel-tenant för höga suveränitetskrav',
          'EU-baserad drift'
        ],
        cta: { label: 'Begär offert', href: CONTACT_URL }
      }
    ],
    compareTitle: 'Jämförelse i detalj',
    featureColumn: 'Funktion',
    tierColumns: ['Individuell', 'Akademi', 'Bransch­organisation', 'Organisation'],
    table: [
      { label: 'Läsa & söka publikt innehåll', values: [YES, YES, YES, YES] },
      { label: 'Historiken & permalänkar', values: [YES, YES, YES, YES] },
      { label: 'Export av publikt innehåll (MD/CSV/TBX/SKOS/JSON-LD)', values: [YES, YES, YES, YES] },
      { label: 'Redigera med proveniens', values: [YES, YES, YES, YES] },
      { label: 'Grenar, ändringsförslag & diskussioner', values: [YES, YES, YES, YES] },
      { label: 'Personliga listor & frusen export', values: [YES, YES, YES, YES] },
      { label: 'AI med egen nyckel (BYOK)', values: [SOON_SV, SOON_SV, SOON_SV, SOON_SV] },
      { label: 'Organisation: roller & medlemmar', values: [NO_SV, YES, YES, YES] },
      { label: 'Org-ägda samlingar (publik läsning, er redigering)', values: [NO_SV, YES, YES, YES] },
      { label: 'Fastställanden i organisationens namn', values: [NO_SV, YES, YES, YES] },
      { label: 'Lås, arkivering & import i skala', values: [NO_SV, YES, YES, YES] },
      { label: 'Org-privata samlingar', values: [NO_SV, YES, YES, YES] },
      { label: 'Servermanagerade AI-nycklar & promptmallar', values: [NO_SV, NO_SV, NO_SV, SOON_SV] },
      { label: 'Support & SLA', values: [NO_SV, NO_SV, NO_SV, YES] },
      { label: 'Självhostad singel-tenant (EU)', values: [NO_SV, NO_SV, NO_SV, YES] }
    ],
    principlesTitle: 'Principerna bakom',
    principles: [
      {
        strong: 'Öppna data förblir öppna.',
        text: 'Allt publikt innehåll kan läsas och exporteras av vem som helst, i alla format – innehållslicensen bestäms per samling, aldrig av prisnivån.'
      },
      {
        strong: 'AI med egen nyckel kommer inte att kosta extra.',
        text: 'AI-funktionerna är under utveckling och slås på när de är klara. Du betalar då din egen AI-leverantör; vi tar inte betalt för att låta dig använda den.'
      },
      {
        strong: 'Ingenting aktiveras automatiskt.',
        text: 'Nya organisationer skapas fritt men granskas manuellt innan organisationsfunktionerna låses upp – akademiska som kommersiella.'
      },
      {
        strong: 'Branschens gemensamma aktörer åker gratis.',
        text: 'När Svensk Kollektivtrafik, Samtrafiken och deras motsvarigheter förvaltar sina begrepp här blir hela sektorns språk bättre – det är produkten, inte en kostnad.'
      }
    ],
    contactHtml:
      'Frågor om nivåerna? <a href="https://linderagroup.com/#kontakt" target="_blank" rel="noopener noreferrer">Hör av dig</a> – eller läs mer i <a href="/manual">manualen</a> och på <a href="/about">om-sidan</a>.'
  },
  en: {
    metaDescription:
      'Kollepedia is free for everyone building the sector’s common language — individual, academic and for the industry’s shared organisations. Quotes for organisational use.',
    heroTitle: 'Free for everyone who builds the common language.',
    heroTagline:
      'Kollepedia’s value grows with every actor who shares their concepts. That is why reading, contributing, academic work and the industry’s canon work are free of charge — and organisations that need private spaces, hosting and support carry the costs.',
    groupIndividuals: 'For individuals',
    groupOrgs: 'For organisations',
    tiers: [
      {
        name: 'Individual',
        price: 'Free',
        audience: 'Individual contributors',
        features: [
          'Read and search all public content — free of charge',
          'Real provenance: every contribution in your name',
          'Create concepts, branches and change proposals',
          'Discussions, watching and an activity feed',
          'Personal lists with pinned versions + export',
          'Your own public collections',
          'AI features with your own key (BYOK) — in development'
        ],
        cta: { label: 'Create account', href: '/' }
      },
      {
        name: 'Academic',
        price: 'Free',
        audience: 'Researchers and students',
        features: [
          'Full access to all organisation features',
          'Registration with an academic email address',
          'The first user creates the institution and becomes its administrator',
          'Org features are enabled after manual review',
          'For non-commercial use'
        ],
        note: 'Institutions are reviewed manually before the organisation features are unlocked.',
        cta: { label: 'Register', href: '/' },
        highlight: true
      },
      {
        name: 'Industry organisation',
        price: 'Free',
        audience:
          'The industry’s shared actors — e.g. Svensk Kollektivtrafik and Samtrafiken',
        features: [
          'Full access to all organisation features',
          'Org-owned collections: public to read, edited by you',
          'Endorsements in the organisation’s name',
          'Locking, archiving, roles and import at scale',
          'Your canon work benefits the whole sector — hence free of charge'
        ],
        note: 'Enabled after contact — the organisation is created freely and reviewed manually.',
        cta: { label: 'Contact us', href: CONTACT_URL }
      },
      {
        name: 'Organisation',
        price: 'Quote',
        audience:
          'Public and private organisations — PTAs, operators, consultancies, system vendors',
        features: [
          'Everything in Industry organisation',
          'Organisation-private collections for sensitive work',
          'Server-managed AI keys and shared prompt presets — in development',
          'Support and SLA',
          'Self-hosted single tenant for strict sovereignty requirements',
          'EU-based hosting'
        ],
        cta: { label: 'Request a quote', href: CONTACT_URL }
      }
    ],
    compareTitle: 'Detailed comparison',
    featureColumn: 'Feature',
    tierColumns: ['Individual', 'Academic', 'Industry organisation', 'Organisation'],
    table: [
      { label: 'Read & search public content', values: [YES, YES, YES, YES] },
      { label: 'The history view & permalinks', values: [YES, YES, YES, YES] },
      { label: 'Export of public content (MD/CSV/TBX/SKOS/JSON-LD)', values: [YES, YES, YES, YES] },
      { label: 'Edit with provenance', values: [YES, YES, YES, YES] },
      { label: 'Branches, change proposals & discussions', values: [YES, YES, YES, YES] },
      { label: 'Personal lists & frozen export', values: [YES, YES, YES, YES] },
      { label: 'AI with your own key (BYOK)', values: [SOON_EN, SOON_EN, SOON_EN, SOON_EN] },
      { label: 'Organisation: roles & members', values: [NO_EN, YES, YES, YES] },
      { label: 'Org-owned collections (public reading, your editing)', values: [NO_EN, YES, YES, YES] },
      { label: 'Endorsements in the organisation’s name', values: [NO_EN, YES, YES, YES] },
      { label: 'Locking, archiving & import at scale', values: [NO_EN, YES, YES, YES] },
      { label: 'Organisation-private collections', values: [NO_EN, YES, YES, YES] },
      { label: 'Server-managed AI keys & prompt presets', values: [NO_EN, NO_EN, NO_EN, SOON_EN] },
      { label: 'Support & SLA', values: [NO_EN, NO_EN, NO_EN, YES] },
      { label: 'Self-hosted single tenant (EU)', values: [NO_EN, NO_EN, NO_EN, YES] }
    ],
    principlesTitle: 'The principles behind it',
    principles: [
      {
        strong: 'Open data stays open.',
        text: 'All public content can be read and exported by anyone, in every format — the content licence is set per collection, never by the pricing tier.'
      },
      {
        strong: 'AI with your own key will cost nothing extra.',
        text: 'The AI features are in development and will be switched on when ready. You then pay your own AI provider; we do not charge you for letting you use it.'
      },
      {
        strong: 'Nothing is enabled automatically.',
        text: 'New organisations are created freely but reviewed manually before the organisation features are unlocked — academic and commercial alike.'
      },
      {
        strong: 'The industry’s shared actors ride for free.',
        text: 'When Svensk Kollektivtrafik, Samtrafiken and their counterparts curate their concepts here, the whole sector’s language improves — that is the product, not a cost.'
      }
    ],
    contactHtml:
      'Questions about the tiers? <a href="https://linderagroup.com/#kontakt" target="_blank" rel="noopener noreferrer">Get in touch</a> — or read more in <a href="/manual">the manual</a> and on <a href="/about">the about page</a>.'
  }
};
