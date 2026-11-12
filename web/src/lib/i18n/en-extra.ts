import type { svExtra } from './sv-extra';

/** Iteration 4 — English mirror of ./sv-extra.ts, typed against its key union so
 * a missing or extra key is a compile-time error.
 * Spread into ./en.ts as the LAST line of the dictionary object. */
export const enExtra: Record<keyof typeof svExtra, string> = {
  // ── AI provider settings ──
  'aiprov.button': 'AI settings',
  'aiprov.dialog_aria': 'AI settings',
  'aiprov.provider_label': 'Provider',
  'aiprov.provider_anthropic': 'Anthropic',
  'aiprov.provider_berget': 'Berget.ai (OpenAI-compatible)',
  'aiprov.provider_openai': 'OpenAI-compatible (custom base URL)',
  'aiprov.model_label': 'Model',
  'aiprov.model_hint_berget': "Check Berget's model catalogue — the field is sent as model.",
  'aiprov.base_url_label': 'Base URL',
  'aiprov.key_label': 'API key',
  'aiprov.saved': 'The settings are stored in your browser.',
  'aiprov.custody_note':
    'Key, provider and model are stored in your browser only. The key is sent with the request itself and proxied by the server without being stored or logged.',
  'aiprov.hint_key': 'First add your AI key under “AI settings”.',

  // ── Saved prompts ──
  'aiprov.preset_label': 'Preset',
  'aiprov.preset_none': 'No preset — custom guidance',
  'aiprov.preset_shared_suffix': 'shared',
  'aiprov.save_as_preset': 'Save as preset …',
  'aiprov.preset_name_label': 'Preset name',
  'aiprov.preset_name_placeholder': 'e.g. Transmodel first, max 50 words',
  'aiprov.preset_shared_label': 'Shared — visible to everyone signed in',
  'aiprov.preset_save': 'Save preset',
  'aiprov.preset_saving': 'Saving preset …',
  'aiprov.preset_saved': 'The preset has been saved.',
  'aiprov.preset_error_no_name': 'Give the preset a name.',
  'aiprov.preset_error_no_text': 'Write a guidance text to save as a preset.',
  'aiprov.preset_save_failed': 'The preset could not be saved: {error}',

  // ── Profile page ──
  'profile.my_profile': 'My profile',
  'profile.head_title': 'My profile — Kollepedia NG',
  'profile.h1': 'My profile',
  'profile.guard_body': 'This page requires an account. Log in via the header.',
  'profile.loading': 'Loading profile …',
  'profile.load_error': 'The profile could not be loaded: {error}',
  'profile.handle_label': 'Username',
  'profile.affiliation_label': 'Affiliation',
  'profile.org_label': 'Organisation',
  'profile.no_org': 'No organisation',
  'profile.author_page_link': 'Open my author page →',
  'profile.author_page_pending': 'Your author page becomes public once you have contributed content.',

  // ── Most watched (home teaser + /most-watched) ──
  'mw.kicker': 'Most watched',
  'mw.all_link': 'All watched, in popularity order →',
  'mw.head_title': 'Most watched — Kollepedia NG',
  'mw.h1': 'Most watched',
  'mw.intro':
    'The concepts most people watch right now. The list only shows what your session is allowed to see.',
  'mw.loading': 'Fetching the list …',
  'mw.empty': 'No watched concepts yet.',
  'mw.load_error': 'The list could not be fetched: {error}',
  'mw.watchers_aria': '{count} watchers',

  // ── Profile: public presentation (bio + URL) ──
  'profile.pres_h2': 'Public presentation',
  'profile.pres_hint':
    'Shown on your author page. The bio is a short text about you; the URL can point to your organisation, CV or research profile.',
  'profile.bio_label': 'Bio',
  'profile.bio_placeholder': 'e.g. Researching public transport terminology at …',
  'profile.url_label': 'Web address',
  'profile.url_placeholder': 'https://…',
  'profile.pres_save': 'Save presentation',
  'profile.pres_saved': 'The presentation has been saved.',
  'profile.pres_error': 'The presentation could not be saved: {error}',

  // ── Profile: email ──
  'profile.email_h2': 'Email',
  'profile.email_current_label': 'Email address',
  'profile.email_none': 'No email address set.',
  'profile.email_verified': 'verified',
  'profile.email_unverified': 'not verified',
  'profile.email_set_legend': 'Set email address',
  'profile.email_change_legend': 'Change email address',
  'profile.email_save': 'Save email address',
  'profile.email_sent': 'Verification email sent — during testing all email lands in the outbox.',
  'profile.email_error': 'The email address could not be saved: {error}',
  'profile.email_invalid': 'Enter a valid email address.',
  'profile.email_reverify_hint':
    'Changing the address sends a new verification email and the address must be verified again.',

  // ── Profile: password ──
  'profile.pw_h2': 'Change password',
  'profile.pw_current': 'Current password',
  'profile.pw_new': 'New password (at least 12 characters)',
  'profile.pw_change': 'Change password',
  'profile.pw_changed': 'The password has been changed.',
  'profile.pw_error': 'The password could not be changed: {error}',
  'profile.pw_missing': 'Enter both your current and your new password.',

  // ── Verify email ──
  'profile.verify_head_title': 'Verify email — Kollepedia NG',
  'profile.verify_h1': 'Verify email address',
  'profile.verify_wait': 'Verifying …',
  'profile.verify_done': 'The email address has been verified.',
  'profile.verify_done_body':
    'The address is now linked to your account and can be used for login and reset links.',
  'profile.verify_no_token':
    'The link is missing a verification code. Open the link from the verification email in full.',
  'profile.verify_failed': 'Verification failed: {error}',
  'profile.verify_to_profile': 'To my profile →',

  // ── Forgot password ──
  'profile.forgot_h2': 'No link?',
  'profile.forgot_body':
    'Enter your email address or your username. If the account has a verified email address, a reset link will be sent there.',
  'profile.forgot_label': 'Email address or username',
  'profile.forgot_send': 'Send reset link',
  'profile.forgot_sending': 'Sending …',
  'profile.forgot_done':
    'If the account has a verified email address, a reset link has been sent. During testing all email stays in the outbox.',
  'profile.forgot_error': 'The request could not be sent: {error}',

  // ── Admin outbox ──
  'profile.outbox_head_title': 'Outbox — Kollepedia NG',
  'profile.outbox_h1': 'Email outbox',
  'profile.outbox_intro':
    'All email the system generates is collected here for inspection — verification emails, reset links and future outreach.',
  'profile.outbox_note':
    'No email leaves the system to addresses outside the allowlist — other recipients are blocked and stored here.',
  'profile.outbox_loading': 'Loading the outbox …',
  'profile.outbox_load_error': 'The outbox could not be loaded: {error}',
  'profile.outbox_empty': 'The outbox is empty.',
  'profile.outbox_th_to': 'To',
  'profile.outbox_th_subject': 'Subject',
  'profile.outbox_th_date': 'Date',
  'profile.outbox_status_queued': 'queued',
  'profile.outbox_status_sent': 'sent',
  'profile.outbox_status_blocked': 'blocked',
  'profile.outbox_status_outbox': 'outbox',
  'profile.outbox_show_body': 'Show content',
  'profile.outbox_users_link': 'To user management →',

  // ── Auth forms ──
  'profile.auth_email_label': 'Email address',
  'profile.auth_email_placeholder': 'name@example.com',
  'profile.auth_identifier_label': 'Email or username',
  'profile.auth_error_login_missing': 'Enter your email or username, and your password.',
  'profile.auth_error_register_missing': 'Enter a username, an email address and a password.',
  'profile.auth_claim_handle_label': 'Username being claimed',
  'profile.auth_claim_hint':
    'Were you imported as an author? Open your author page and activate the account from there to claim the identity.',
  'profile.auth_registered_h': 'The account has been created.',
  'profile.auth_registered_body':
    'Verification email sent to {email} — during testing all email stays in the outbox.',
  'profile.auth_registered_done': 'Done',
  'profile.auth_forgot_link': 'Forgot your password?',
  'profile.auth_review_pending_h': 'The account is awaiting review.',
  'profile.auth_review_pending_body':
    'Your registration was flagged for manual review. You can read everything, but not contribute until an administrator has approved the account — you will get an email when it is done.',
  'profile.auth_pointer_author_link': 'View the author page',
  'profile.auth_pointer_claim_link': 'Claim the identity',

  // ── Collection edit policy (coordinator addition) ──
  'coll.policy_label': 'Editing policy',
  'coll.policy_org': 'Own organisation only',
  'coll.policy_anyone': 'Any signed-in user',
  'coll.policy_hint':
    'Separate from visibility: a collection can be publicly readable yet editable only by the organisation.',

  // ── Error page ──
  'errpage.notfound_h1': 'Page not found',
  'errpage.generic_h1': 'Something went wrong',
  'errpage.notfound_body': 'The content you are looking for does not exist — check the link.',
  'errpage.home_link': 'Back to the start page',

  // ── Infinite scroll (start & collection listings) ──
  'inf.loading_more': 'Loading more results',
  'inf.counter': '{count} of {total}',
  'pricing.head_title': 'Pricing — Kollepedia NG',
};
