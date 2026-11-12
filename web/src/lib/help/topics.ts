/* i18n-content */
/** Contextual help topics for <HelpTip topic="…" />, per UI language.
 *
 * Each topic is a 1–3 sentence micro-explanation plus an anchor into the
 * in-app manual at /help. Keep bodies short — the manual carries the depth.
 *
 * Content-by-language module: the Swedish map is the source of truth for the
 * topic-id union; the English map is typed against it, so a topic missing in
 * either language is a compile-time error. Anchors are shared (they are URLs
 * into /help and never translated).
 */
import type { Lang } from '$lib/i18n.svelte';

export interface HelpTopic {
  /** Anchor into /help, e.g. '#historiken'. Same in every language. */
  anchor: string;
  /** Short title, shown in the popover and in the button's aria-label. */
  title: string;
  /** 1–3 sentences of plain prose in the UI language. */
  body: string;
}

const svTopics = {
  signature: {
    anchor: '#komma-igang',
    title: 'Konto & attribution',
    body: 'Allt du sparar tillskrivs ditt konto – proveniens är produktens själ. Skapa ett konto via Logga in i sidhuvudet; varje version du skapar bär ditt författarnamn för alltid.'
  },
  'editing-note': {
    anchor: '#redigera',
    title: 'Motivering (not)',
    body: 'Varje ny version bär en obligatorisk motivering – versionens commit-meddelande. Den svarar på frågan varför och följer med versionen för alltid.'
  },
  branching: {
    anchor: '#redigera',
    title: 'Grenar',
    body: 'En gren är en namngiven sidolinje i begreppets historik. Ingenting skrivs över: grenar förenas senare genom en uttrycklig syntes eller genom att en version görs gällande.'
  },
  timeline: {
    anchor: '#historiken',
    title: 'Historik',
    body: 'Spela upp begreppets hela historik som en film, eller dra spelhuvudet till valfritt ögonblick. Piltangenterna stegar version för version, mellanslag spelar och pausar.'
  },
  'ink-mode': {
    anchor: '#historiken',
    title: 'Bläck-läge',
    body: 'Texten tonas efter ålder: nyskrivna ord i fullt bläck, äldre lager allt blekare mot sepia. Hovra över ett ord för att se vem som skrev det, när och varför.'
  },
  'order-toggle': {
    anchor: '#historiken',
    title: 'Ordning',
    body: '”Längs texten” spelar upp ändringarna i läsordning, som om någon redigerade från start till slut. ”Samtidigt” markerar allt rött först och skriver sedan allt grönt.'
  },
  'collection-vs-list': {
    anchor: '#samlingar-listor',
    title: 'Samling eller lista?',
    body: 'Samlingen är hyllan där begrepp lever och utvecklas i versioner. Listan är din urvalslåda: den fäster exakta versioner för ett syfte, till exempel en upphandling – utan att äga begreppen.'
  },
  'pin-vs-follow': {
    anchor: '#samlingar-listor',
    title: 'Fäst eller följ senaste',
    body: '”Fäst denna version” fryser exakt den version du ser – den ändras aldrig, ens när begreppet uppdateras. ”Följ senaste” är ett aktivt val för listor som ska leva med samlingen.'
  },
  'compare-base': {
    anchor: '#jamforelseverkstaden',
    title: 'Utgångspunkt',
    body: 'Kolumnen markerad som utgångspunkt är måttstocken: alla diffar i de andra kolumnerna räknas mot den. Byt utgångspunkt med radioknappen i valfri kolumn.'
  },
  'diff-mode': {
    anchor: '#jamforelseverkstaden',
    title: 'Diff-läge',
    body: 'Visar ordagrant vad som skiljer definitionerna åt: rött genomstruket finns bara i utgångspunkten, grönt bara i den aktuella kolumnen.'
  },
  harmonise: {
    anchor: '#ai',
    title: 'Harmonisera',
    body: 'Skapar ett AI-utkast som sammanför kolumnernas definitioner till en gemensam, med utgångspunkten som bas. Utkastet granskas och redigeras av dig innan något sparas – och sparas då som en syntes med full proveniens.'
  },
  'byok-key': {
    anchor: '#ai',
    title: 'Egen AI-nyckel (BYOK)',
    body: 'AI-funktionerna använder din egen nyckel hos vald leverantör. Den lagras endast i din webbläsare och skickas bara med själva anropet, som proxas utan att sparas på servern.'
  },
  'ai-provider': {
    anchor: '#ai',
    title: 'AI-leverantör',
    body: 'Välj mellan Anthropic, Berget.ai (OpenAI-kompatibel, svenskt datacenter) och valfri OpenAI-kompatibel tjänst med egen bas-URL. Modellfältet skickas med anropet; lämnas det tomt används leverantörens standardmodell.'
  },
  'prompt-presets': {
    anchor: '#ai',
    title: 'Promptmallar',
    body: 'Vägledningar du använder ofta kan sparas som mallar – privata eller delade. När ett AI-utkast skapas med en mall vald följer mallens id med i versionens proveniens.'
  },
  proposals: {
    anchor: '#andringsforslag',
    title: 'Ändringsförslag',
    body: 'En gren kan skickas som ändringsförslag till huvudlinjen – som en pull request för begrepp. Förslaget granskas med diff och avgörs uttryckligen: sammanfoga eller avvisa, alltid med motivering.'
  },
  discussion: {
    anchor: '#diskussioner',
    title: 'Diskussion',
    body: 'Varje begrepp och varje ändringsförslag har en diskussionstråd för frågor, källor och invändningar. Inlägg är attribuerade och kan bara tas bort av författaren själv.'
  },
  watch: {
    anchor: '#diskussioner',
    title: 'Bevaka',
    body: 'Bevaka ett begrepp så samlas dess händelser – nya versioner, fastställanden, inlägg och förslag – i ditt aktivitetsflöde under Aktivitet.'
  },
  'email-verify': {
    anchor: '#epost',
    title: 'E-postverifiering',
    body: 'E-postadressen kopplas till kontot först när du klickat på verifieringslänken. Brevet kommer från no-reply@kollepedia.se; har det inte kommit inom några minuter, titta i skräpposten.'
  },
  permalink: {
    anchor: '#permalankar',
    title: 'Permalänk & citering',
    body: 'Varje version har en permanent, citerbar adress som aldrig ändras. Citera-rutan ger både URL:en och en färdig källhänvisning.'
  },
  'import-format': {
    anchor: '#import',
    title: 'Importformat',
    body: 'Importen tar CSV eller Excel med bestämda kolumnrubriker – hämta mallen så får du rubrikraden och en exempelrad. Endast canonical_form och definition är obligatoriska.'
  },
  'dry-run': {
    anchor: '#import',
    title: 'Torrkörning',
    body: 'Torrkörningen validerar hela filen – rad för rad, med fel och varningar – utan att skriva någonting. Kör den alltid först; importera skarpt när rapporten är ren.'
  },
  visibility: {
    anchor: '#organisationer',
    title: 'Synlighet',
    body: 'En publik samling kan läsas av alla, även utan konto. En org-privat samling syns bara för organisationens medlemmar – i sök, jämförelser och export.'
  },
  'org-roles': {
    anchor: '#organisationer',
    title: 'Roller i organisationen',
    body: 'Läsare ser organisationens privata innehåll, redaktörer skapar och redigerar begrepp, och admin hanterar dessutom medlemmar och samlingarnas inställningar.'
  },
  promote: {
    anchor: '#historiken',
    title: 'Gör till gällande version',
    body: 'Återställer en äldre version genom att skapa en ny version med samma innehåll och en bakåtreferens. Historiken skrivs aldrig om – huvudet flyttas, inget raderas.'
  },
  endorsement: {
    anchor: '#begrepp',
    title: 'Fastställd (endorsement)',
    body: 'En fastställd version bär en uttrycklig, attribuerad stämpel från en auktoritativ aktör. Stämpeln kan återkallas – men även återkallandet blir en spårbar händelse, inget raderas.'
  },
  'export-formats': {
    anchor: '#export',
    title: 'Exportformat',
    body: 'CSV för kalkylblad, Markdown för läsbara dokument, JSON-LD och SKOS för länkade data, TBX för terminologi- och översättningsverktyg. Fästa versioner exporteras exakt som de är – ordlistan är fryst.'
  }
} as const satisfies Record<string, HelpTopic>;

export type HelpTopicId = keyof typeof svTopics;

const enTopics: Record<HelpTopicId, HelpTopic> = {
  signature: {
    anchor: '#komma-igang',
    title: 'Account & attribution',
    body: 'Everything you save is attributed to your account — provenance is the soul of the product. Create an account via Log in in the header; every version you create carries your author name forever.'
  },
  'editing-note': {
    anchor: '#redigera',
    title: 'Justification (note)',
    body: 'Every new version carries a required justification — the version’s commit message. It answers the question why and stays with the version forever.'
  },
  branching: {
    anchor: '#redigera',
    title: 'Branches',
    body: 'A branch is a named side line in the concept’s history. Nothing is overwritten: branches are later united through an explicit synthesis or by making one version current.'
  },
  timeline: {
    anchor: '#historiken',
    title: 'History',
    body: 'Play the concept’s entire history like a film, or drag the playhead to any moment. The arrow keys step version by version; the space bar plays and pauses.'
  },
  'ink-mode': {
    anchor: '#historiken',
    title: 'Ink mode',
    body: 'The text fades by age: freshly written words in full ink, older layers ever paler towards sepia. Hover over a word to see who wrote it, when and why.'
  },
  'order-toggle': {
    anchor: '#historiken',
    title: 'Order',
    body: '“Along the text” plays the changes in reading order, as if someone edited from start to finish. “Simultaneous” marks everything red first, then writes everything green.'
  },
  'collection-vs-list': {
    anchor: '#samlingar-listor',
    title: 'Collection or list?',
    body: 'The collection is the shelf where concepts live and evolve in versions. The list is your selection box: it pins exact versions for a purpose, such as a procurement — without owning the concepts.'
  },
  'pin-vs-follow': {
    anchor: '#samlingar-listor',
    title: 'Pin or follow latest',
    body: '“Pin this version” freezes exactly the version you see — it never changes, even when the concept is updated. “Follow latest” is an active choice for lists that should live with the collection.'
  },
  'compare-base': {
    anchor: '#jamforelseverkstaden',
    title: 'Base',
    body: 'The column marked as the base is the yardstick: all diffs in the other columns are calculated against it. Switch the base with the radio button in any column.'
  },
  'diff-mode': {
    anchor: '#jamforelseverkstaden',
    title: 'Diff mode',
    body: 'Shows word by word what separates the definitions: red strikethrough exists only in the base, green only in the current column.'
  },
  harmonise: {
    anchor: '#ai',
    title: 'Harmonise',
    body: 'Creates an AI draft that unifies the columns’ definitions into a shared one, with the base as its foundation. You review and edit the draft before anything is saved — and it is then saved as a synthesis with full provenance.'
  },
  'byok-key': {
    anchor: '#ai',
    title: 'Your own AI key (BYOK)',
    body: 'The AI features use your own key with the provider of your choice. It is stored only in your browser and sent only with the actual request, which is proxied without being stored on the server.'
  },
  'ai-provider': {
    anchor: '#ai',
    title: 'AI provider',
    body: 'Choose between Anthropic, Berget.ai (OpenAI-compatible, Swedish data centre) and any OpenAI-compatible service with a custom base URL. The model field is sent with the request; if left empty, the provider’s default model is used.'
  },
  'prompt-presets': {
    anchor: '#ai',
    title: 'Prompt presets',
    body: 'Guidance texts you use often can be saved as presets — private or shared. When an AI draft is created with a preset selected, the preset’s id travels with the version’s provenance.'
  },
  proposals: {
    anchor: '#andringsforslag',
    title: 'Change proposals',
    body: 'A branch can be submitted as a change proposal to the mainline — like a pull request for concepts. The proposal is reviewed with a diff and decided explicitly: merge or reject, always with a justification.'
  },
  discussion: {
    anchor: '#diskussioner',
    title: 'Discussion',
    body: 'Every concept and every change proposal has a discussion thread for questions, sources and objections. Posts are attributed and can only be deleted by their author.'
  },
  watch: {
    anchor: '#diskussioner',
    title: 'Watch',
    body: 'Watch a concept and its events — new versions, endorsements, posts and proposals — gather in your activity feed under Activity.'
  },
  'email-verify': {
    anchor: '#epost',
    title: 'Email verification',
    body: 'The email address is linked to the account only once you have clicked the verification link. The message comes from no-reply@kollepedia.se; if it has not arrived within a few minutes, check your spam folder.'
  },
  permalink: {
    anchor: '#permalankar',
    title: 'Permalink & citation',
    body: 'Every version has a permanent, citable address that never changes. The Cite box gives you both the URL and a ready-made citation.'
  },
  'import-format': {
    anchor: '#import',
    title: 'Import format',
    body: 'The import accepts CSV or Excel with fixed column headers — download the template to get the header row and an example row. Only canonical_form and definition are required.'
  },
  'dry-run': {
    anchor: '#import',
    title: 'Dry run',
    body: 'The dry run validates the whole file — row by row, with errors and warnings — without writing anything. Always run it first; import for real once the report is clean.'
  },
  visibility: {
    anchor: '#organisationer',
    title: 'Visibility',
    body: 'A public collection can be read by anyone, even without an account. An organisation-private collection is visible only to the organisation’s members — in search, comparisons and export.'
  },
  'org-roles': {
    anchor: '#organisationer',
    title: 'Roles in the organisation',
    body: 'Viewers see the organisation’s private content, editors create and edit concepts, and admins additionally manage members and the collections’ settings.'
  },
  promote: {
    anchor: '#historiken',
    title: 'Make current version',
    body: 'Restores an older version by creating a new version with the same content and a back-reference. History is never rewritten — the head moves, nothing is deleted.'
  },
  endorsement: {
    anchor: '#begrepp',
    title: 'Endorsed (endorsement)',
    body: 'An endorsed version carries an explicit, attributed stamp from an authoritative body. The stamp can be withdrawn — but even the withdrawal becomes a traceable event; nothing is deleted.'
  },
  'export-formats': {
    anchor: '#export',
    title: 'Export formats',
    body: 'CSV for spreadsheets, Markdown for readable documents, JSON-LD and SKOS for linked data, TBX for terminology and translation tools. Pinned versions are exported exactly as they are — the glossary is frozen.'
  }
};

export const helpTopics: Record<Lang, Record<HelpTopicId, HelpTopic>> = {
  sv: svTopics,
  en: enTopics
};
