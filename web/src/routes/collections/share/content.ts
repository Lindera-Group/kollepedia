/* i18n-content */
/** /collections/share — sidan som förklarar organisationsvägen: egna
 * samlingar är alltid privata; delning sker genom en organisation (skapa
 * eller bli inbjuden). Content-by-language module (pricing-mönstret): formen
 * är typad som Record<Lang, ShareContent>, så ett saknat språk eller fält är
 * ett kompileringsfel. */
import type { Lang } from '$lib/i18n.svelte';

export interface ShareStep {
  title: string;
  text: string;
  cta: { label: string; href: string } | null;
}

export interface ShareContent {
  metaDescription: string;
  title: string;
  intro: string;
  whyTitle: string;
  whyText: string;
  pathsTitle: string;
  steps: ShareStep[];
  moveTitle: string;
  moveText: string;
}

export const shareContent: Record<Lang, ShareContent> = {
  sv: {
    metaDescription:
      'Egna samlingar är privata arbetsytor. För att dela en samling med andra går vägen genom en organisation – skapa en eller bli inbjuden.',
    title: 'Dela samlingar',
    intro:
      'Dina egna samlingar är privata arbetsytor – bara du ser dem. För att dela en samling med kollegor eller med alla går vägen genom en organisation.',
    whyTitle: 'Varför en organisation?',
    whyText:
      'En samling som ägs av en organisation kan vara intern (synlig för organisationens medlemmar) eller publik (synlig för alla). Organisationen ger delningen en tydlig ägare: vem som ansvarar för innehållet, vem som får skriva och vilken licens som gäller.',
    pathsTitle: 'Två vägar in',
    steps: [
      {
        title: 'Skapa en organisation',
        text: 'Du blir ägare och administratör och kan bjuda in medlemmar. Organisationer använder organisationslicensen – se prissidan för vad som ingår.',
        cta: { label: 'Till organisationer', href: '/orgs' }
      },
      {
        title: 'Bli inbjuden',
        text: 'En administratör i en befintlig organisation kan bjuda in dig som medlem. Som medlem ser du organisationens interna samlingar och kan bidra enligt din roll.',
        cta: { label: 'Se licenser', href: '/pricing' }
      }
    ],
    moveTitle: 'Flytta en befintlig samling',
    moveText:
      'När du är administratör i en organisation kan du flytta en privat samling dit: öppna samlingen, välj Redigera samlingen och ange organisation och synlighet (Intern eller Publik).'
  },
  en: {
    metaDescription:
      'Personal collections are private workspaces. Sharing a collection with others goes through an organisation — create one or get invited.',
    title: 'Sharing collections',
    intro:
      'Your own collections are private workspaces — only you can see them. To share a collection with colleagues or with everyone, the path goes through an organisation.',
    whyTitle: 'Why an organisation?',
    whyText:
      'A collection owned by an organisation can be internal (visible to the organisation’s members) or public (visible to everyone). The organisation gives sharing a clear owner: who is responsible for the content, who may write, and which licence applies.',
    pathsTitle: 'Two ways in',
    steps: [
      {
        title: 'Create an organisation',
        text: 'You become its owner and administrator and can invite members. Organisations use the organisation licence — see the pricing page for what is included.',
        cta: { label: 'Go to organisations', href: '/orgs' }
      },
      {
        title: 'Get invited',
        text: 'An administrator of an existing organisation can invite you as a member. As a member you see the organisation’s internal collections and can contribute according to your role.',
        cta: { label: 'See licences', href: '/pricing' }
      }
    ],
    moveTitle: 'Move an existing collection',
    moveText:
      'Once you are an administrator of an organisation, you can move a private collection into it: open the collection, choose Edit collection, and set the organisation and visibility (Internal or Public).'
  }
};
