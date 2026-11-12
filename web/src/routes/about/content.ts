/* i18n-content */
/** /about page content, per UI language. Content-by-language module typed as
 * Record<Lang, AboutContent> — a missing language or field is a compile-time
 * error. `*Html` fields are trusted authored HTML (may contain <a>, <em>,
 * <span class="ui small">) rendered with {@html} in +page.svelte. */
import type { Lang } from '$lib/i18n.svelte';

export interface AboutContent {
  kicker: string;
  title: string;
  ledeHtml: string;
  why: { title: string; html: string };
  history: { title: string; html: string };
  openSource: { title: string; html: string };
  licences: {
    title: string;
    html: string;
    loadFailed: string;
    loading: string;
    notSpecified: string;
  };
  start: { title: string; html: string };
}

export const aboutContent: Record<Lang, AboutContent> = {
  sv: {
    kicker: 'Om Kollepedia',
    title: 'En begreppsbank där definitioner har historia',
    ledeHtml:
      'Kollepedia NG samlar kollektivtrafikens terminologi – från Transmodel till svenska ordböcker – i en gemensam, versionerad begreppsbank. Varje definition är inte en textrad utan en <em>versionsgraf</em>: den kan revideras, grenas, syntetiseras och översättas, och varje steg bevaras med upphovsperson, tidpunkt och motivering.',
    why: {
      title: 'Varför versioner?',
      html: 'Fackspråk förhandlas fram. När en myndighet, en forskargrupp och en operatör menar olika saker med samma ord behövs inte en vinnare – det behövs spårbarhet. I Kollepedia kan flera definitioner leva sida vid sida, jämföras, och till slut fastställas av ett organ med mandat. Historiken låter dig spela upp hur ett begrepp vuxit fram, ord för ord.'
    },
    history: {
      title: 'Från KOMIMP till i dag',
      html: 'Den första Kollepedia var en wiki på kollepedia.se, öppnad omkring 2007 inom <strong>KOMIMP</strong> – ett projekt för att sprida forsknings- och utvecklingsresultat i kollektivtrafikbranschen, finansierat av Upplands Lokaltrafik, Länstrafiken, Skånetrafiken, SLTF (i dag Svensk Kollektivtrafik) och Vinnova. <strong>Transportidé AB</strong>, med <strong>Mats Börjesson</strong> som drivande kraft, byggde upp wikin och höll den samman: en plats där branschfolk, konsulter och forskare kunde bidra med definitioner, förklaringar och praktiska exempel. Omkring 2012 försvann sajten från nätet, men en stor del av innehållet bevarades i Internet Archives Wayback Machine. 225 artiklar har kunnat räddas därifrån och lever vidare i samlingen <a href="/collections/kollepedia-2012">Kollepedia</a>, under samma GNU FDL-licens som originalet och med källhänvisningar till arkivet. Dagens Kollepedia är Linderå Groups vidareutveckling av idén – tack till Transportidé och Mats Börjesson för att ni la grunden.'
    },
    openSource: {
      title: 'Öppen källkod',
      html: 'Plattformen är fri programvara under <a href="https://www.gnu.org/licenses/agpl-3.0.html" target="_blank" rel="noopener noreferrer">GNU AGPL-3.0-or-later</a>: fri att köra, läsa, ändra och hosta, med villkoret att den som erbjuder en ändrad version till andra också erbjuder dem källkoden. Källkoden finns på <a href="https://github.com/Lindera-Group/kollepedia" target="_blank" rel="noopener noreferrer">GitHub</a> – felrapporter och bidrag är välkomna.'
    },
    licences: {
      title: 'Innehållslicenser per samling',
      html: 'Koden är en sak, innehållet en annan: varje samling behåller sin egen licens och sina egna upphovspersoner. Det som gäller för respektive samling:',
      loadFailed: 'Samlingslistan kunde inte hämtas just nu.',
      loading: 'Hämtar samlingarna …',
      notSpecified: 'licens ej angiven'
    },
    start: {
      title: 'Kom igång',
      html: 'Läs <a href="/manual">hjälpen</a> för att lära dig söka, jämföra och bidra – eller börja direkt i <a href="/">söket</a>. Vill din organisation förvalta en egen samling? Skapa den under <a href="/orgs">Min organisation</a>.'
    }
  },
  en: {
    kicker: 'About Kollepedia',
    title: 'A concept bank where definitions have history',
    ledeHtml:
      'Kollepedia NG gathers public transport terminology — from Transmodel to Swedish glossaries — into a shared, versioned concept bank. Each definition is not a line of text but a <em>version graph</em>: it can be revised, branched, synthesised and translated, and every step is preserved with its author, timestamp and justification.',
    why: {
      title: 'Why versions?',
      html: 'Technical language is negotiated. When an authority, a research group and an operator mean different things by the same word, what is needed is not a winner — it is traceability. In Kollepedia, several definitions can live side by side, be compared, and finally be endorsed by a body with a mandate. The history view lets you play back how a concept has grown, word by word.'
    },
    history: {
      title: 'From KOMIMP to today',
      html: 'The first Kollepedia was a wiki at kollepedia.se, opened around 2007 within <strong>KOMIMP</strong> — a project for spreading research and development results across the Swedish public transport industry, funded by Upplands Lokaltrafik, Länstrafiken, Skånetrafiken, SLTF (today Svensk Kollektivtrafik) and Vinnova. <strong>Transportidé AB</strong>, with <strong>Mats Börjesson</strong> as its driving force, built the wiki and held it together: a place where practitioners, consultants and researchers contributed definitions, explanations and practical examples. Around 2012 the site disappeared from the web, but much of its content survived in the Internet Archive’s Wayback Machine. 225 articles have been recovered from there and live on in the collection <a href="/collections/kollepedia-2012">Kollepedia</a>, under the same GNU FDL licence as the original and with source references to the archive. Today’s Kollepedia is Linderå Group’s continuation of the idea — thank you, Transportidé and Mats Börjesson, for laying the foundation.'
    },
    openSource: {
      title: 'Open source',
      html: 'The platform is free software under the <a href="https://www.gnu.org/licenses/agpl-3.0.html" target="_blank" rel="noopener noreferrer">GNU AGPL-3.0-or-later</a>: free to run, study, change and host, on the condition that whoever offers a modified version to others also offers them its source. The source code is on <a href="https://github.com/Lindera-Group/kollepedia" target="_blank" rel="noopener noreferrer">GitHub</a> — bug reports and contributions are welcome.'
    },
    licences: {
      title: 'Content licences per collection',
      html: 'The code is one thing, the content another: each collection keeps its own licence and its own authors. This is what applies to each collection:',
      loadFailed: 'The collection list could not be loaded right now.',
      loading: 'Loading the collections …',
      notSpecified: 'licence not specified'
    },
    start: {
      title: 'Getting started',
      html: 'Read <a href="/manual">the help pages</a> to learn how to search, compare and contribute — or start straight away in <a href="/">the search</a>. Does your organisation want to curate a collection of its own? Create it under <a href="/orgs">My organisation</a>.'
    }
  }
};
