/** Iteration 4 — Swedish keys for AI providers (`aiprov.`), profile/email/auth
 * (`profile.`).
 * Spread into ./sv.ts as the LAST line of the dictionary object. */
export const svExtra = {
  // ── AI provider settings (AiSettings + harmonise/import call sites) ──
  'aiprov.button': 'AI-inställningar',
  'aiprov.dialog_aria': 'AI-inställningar',
  'aiprov.provider_label': 'Leverantör',
  'aiprov.provider_anthropic': 'Anthropic',
  'aiprov.provider_berget': 'Berget.ai (OpenAI-kompatibel)',
  'aiprov.provider_openai': 'OpenAI-kompatibel (egen bas-URL)',
  'aiprov.model_label': 'Modell',
  'aiprov.model_hint_berget': 'Kolla Bergets modellkatalog – fältet skickas som model.',
  'aiprov.base_url_label': 'Bas-URL',
  'aiprov.key_label': 'API-nyckel',
  'aiprov.saved': 'Inställningarna är sparade i din webbläsare.',
  'aiprov.custody_note':
    'Nyckel, leverantör och modell lagras endast i din webbläsare. Nyckeln skickas bara med själva anropet och proxas av servern utan att sparas eller loggas.',
  'aiprov.hint_key': 'Lägg först in din AI-nyckel under ”AI-inställningar”.',

  // ── Saved prompts (guidance presets in the harmonise panel) ──
  'aiprov.preset_label': 'Mall',
  'aiprov.preset_none': 'Ingen mall – egen vägledning',
  'aiprov.preset_shared_suffix': 'delad',
  'aiprov.save_as_preset': 'Spara som mall …',
  'aiprov.preset_name_label': 'Mallens namn',
  'aiprov.preset_name_placeholder': 't.ex. Transmodel först, max 50 ord',
  'aiprov.preset_shared_label': 'Delad – synlig för alla inloggade',
  'aiprov.preset_save': 'Spara mall',
  'aiprov.preset_saving': 'Sparar mall …',
  'aiprov.preset_saved': 'Mallen är sparad.',
  'aiprov.preset_error_no_name': 'Ange ett namn på mallen.',
  'aiprov.preset_error_no_text': 'Skriv en vägledning att spara som mall.',
  'aiprov.preset_save_failed': 'Mallen kunde inte sparas: {error}',

  // ── Profile page ──
  'profile.my_profile': 'Min profil',
  'profile.head_title': 'Min profil – Kollepedia NG',
  'profile.h1': 'Min profil',
  'profile.guard_body': 'Sidan kräver att du är inloggad med konto. Logga in via sidhuvudet.',
  'profile.loading': 'Hämtar profil …',
  'profile.load_error': 'Profilen kunde inte hämtas: {error}',
  'profile.handle_label': 'Användarnamn',
  'profile.affiliation_label': 'Affiliering',
  'profile.org_label': 'Organisation',
  'profile.no_org': 'Ingen organisation',
  'profile.author_page_link': 'Öppna min författarsida →',
  'profile.author_page_pending': 'Din författarsida blir publik när du har bidragit med innehåll.',

  // ── Mest bevakade (startsideruta + /most-watched) ──
  'mw.kicker': 'Mest bevakade',
  'mw.all_link': 'Alla bevakade i popularitetsordning →',
  'mw.head_title': 'Mest bevakade – Kollepedia NG',
  'mw.h1': 'Mest bevakade',
  'mw.intro':
    'Begreppen flest bevakar just nu. Listan visar bara det du har rätt att se utifrån din inloggning.',
  'mw.loading': 'Hämtar listan …',
  'mw.empty': 'Inga bevakade begrepp ännu.',
  'mw.load_error': 'Listan kunde inte hämtas: {error}',
  'mw.watchers_aria': '{count} bevakare',

  // ── Profile: public presentation (bio + URL) ──
  'profile.pres_h2': 'Publik presentation',
  'profile.pres_hint':
    'Visas på din författarsida. Bio är en kort text om dig; webbadressen kan peka på din organisation, ditt CV eller din forskningsprofil.',
  'profile.bio_label': 'Bio',
  'profile.bio_placeholder': 't.ex. Forskar om kollektivtrafikens terminologi vid …',
  'profile.url_label': 'Webbadress',
  'profile.url_placeholder': 'https://…',
  'profile.pres_save': 'Spara presentation',
  'profile.pres_saved': 'Presentationen är sparad.',
  'profile.pres_error': 'Presentationen kunde inte sparas: {error}',

  // ── Profile: email ──
  'profile.email_h2': 'E-post',
  'profile.email_current_label': 'E-postadress',
  'profile.email_none': 'Ingen e-postadress angiven.',
  'profile.email_verified': 'verifierad',
  'profile.email_unverified': 'ej verifierad',
  'profile.email_set_legend': 'Ange e-postadress',
  'profile.email_change_legend': 'Byt e-postadress',
  'profile.email_save': 'Spara e-postadress',
  'profile.email_sent': 'Verifieringsbrev skickat – under test hamnar all e-post i utkorgen.',
  'profile.email_error': 'E-postadressen kunde inte sparas: {error}',
  'profile.email_invalid': 'Ange en giltig e-postadress.',
  'profile.email_reverify_hint':
    'Byter du adress skickas ett nytt verifieringsbrev och adressen måste verifieras igen.',

  // ── Profile: password ──
  'profile.pw_h2': 'Byt lösenord',
  'profile.pw_current': 'Nuvarande lösenord',
  'profile.pw_new': 'Nytt lösenord (minst 12 tecken)',
  'profile.pw_change': 'Byt lösenord',
  'profile.pw_changed': 'Lösenordet är bytt.',
  'profile.pw_error': 'Lösenordet kunde inte bytas: {error}',
  'profile.pw_missing': 'Ange både nuvarande och nytt lösenord.',

  // ── Verify email (/verify-email) ──
  'profile.verify_head_title': 'Verifiera e-post – Kollepedia NG',
  'profile.verify_h1': 'Verifiera e-postadress',
  'profile.verify_wait': 'Verifierar …',
  'profile.verify_done': 'E-postadressen är verifierad.',
  'profile.verify_done_body':
    'Adressen är nu kopplad till ditt konto och kan användas för inloggning och återställningslänkar.',
  'profile.verify_no_token':
    'Länken saknar verifieringskod. Öppna länken från verifieringsbrevet i sin helhet.',
  'profile.verify_failed': 'Verifieringen misslyckades: {error}',
  'profile.verify_to_profile': 'Till min profil →',

  // ── Forgot password (on /reset without token) ──
  'profile.forgot_h2': 'Har du ingen länk?',
  'profile.forgot_body':
    'Ange din e-postadress eller ditt användarnamn. Har kontot en verifierad e-postadress skickas en återställningslänk dit.',
  'profile.forgot_label': 'E-postadress eller användarnamn',
  'profile.forgot_send': 'Skicka återställningslänk',
  'profile.forgot_sending': 'Skickar …',
  'profile.forgot_done':
    'Om kontot har en verifierad e-postadress har en återställningslänk skickats. Under test stannar all e-post i utkorgen.',
  'profile.forgot_error': 'Begäran kunde inte skickas: {error}',

  // ── Admin outbox (/admin/outbox) ──
  'profile.outbox_head_title': 'Utkorg – Kollepedia NG',
  'profile.outbox_h1': 'E-postutkorg',
  'profile.outbox_intro':
    'All e-post som systemet genererar samlas här för inspektion – verifieringsbrev, återställningslänkar och kommande utskick.',
  'profile.outbox_note':
    'Ingen e-post lämnar systemet till andra adresser än allowlistens – övriga mottagare blockeras och sparas här.',
  'profile.outbox_loading': 'Hämtar utkorgen …',
  'profile.outbox_load_error': 'Utkorgen kunde inte hämtas: {error}',
  'profile.outbox_empty': 'Utkorgen är tom.',
  'profile.outbox_th_to': 'Till',
  'profile.outbox_th_subject': 'Ämne',
  'profile.outbox_th_date': 'Datum',
  'profile.outbox_status_queued': 'köad',
  'profile.outbox_status_sent': 'skickad',
  'profile.outbox_status_blocked': 'blockerad',
  'profile.outbox_status_outbox': 'utkorg',
  'profile.outbox_show_body': 'Visa innehåll',
  'profile.outbox_users_link': 'Till användarhanteringen →',

  // ── Auth forms ──
  'profile.auth_email_label': 'E-postadress',
  'profile.auth_email_placeholder': 'namn@exempel.se',
  'profile.auth_identifier_label': 'E-post eller användarnamn',
  'profile.auth_error_login_missing': 'Ange e-post eller användarnamn samt lösenord.',
  'profile.auth_error_register_missing': 'Ange användarnamn, e-postadress och lösenord.',
  'profile.auth_claim_handle_label': 'Användarnamn som tas över',
  'profile.auth_claim_hint':
    'Har du blivit importerad som författare? Öppna din författarsida och aktivera kontot därifrån, så tar du över identiteten.',
  'profile.auth_registered_h': 'Kontot är skapat.',
  'profile.auth_registered_body':
    'Verifieringsbrev skickat till {email} – under test stannar all e-post i utkorgen.',
  'profile.auth_registered_done': 'Klar',
  'profile.auth_forgot_link': 'Glömt lösenord?',
  'profile.auth_review_pending_h': 'Kontot väntar på granskning.',
  'profile.auth_review_pending_body':
    'Din registrering har flaggats för manuell granskning. Du kan läsa allt, men inte bidra förrän en administratör godkänt kontot – du får ett mejl när det är klart.',
  'profile.auth_pointer_author_link': 'Visa författarsidan',
  'profile.auth_pointer_claim_link': 'Gör anspråk på identiteten',

  // ── Collection edit policy (coordinator addition) ──
  'coll.policy_label': 'Redigeringspolicy',
  'coll.policy_org': 'Endast egna organisationen',
  'coll.policy_anyone': 'Alla inloggade',
  'coll.policy_hint':
    'Skild från synligheten: en samling kan vara publik att läsa men redigeras enbart av organisationen.',

  // ── Error page (SSR: load functions throw error(404/…)) ──
  'errpage.notfound_h1': 'Sidan hittades inte',
  'errpage.generic_h1': 'Något gick fel',
  'errpage.notfound_body': 'Innehållet du söker finns inte – kontrollera länken.',
  'errpage.home_link': 'Till startsidan',

  // ── Infinite scroll (start- & samlingssidans listningar) ──
  'inf.loading_more': 'Fler resultat laddas',
  'inf.counter': '{count} av {total}',
  'pricing.head_title': 'Priser – Kollepedia NG',
} as const;
