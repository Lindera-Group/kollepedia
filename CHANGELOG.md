# Ändringslogg – Kollepedia NG

Taggarna heter `ng-vX.Y.Z` under betaperioden på kollepedia.se; `v1.0.0` blir
den första releasen när betan är över. Noterna här speglar GitHub-releaserna.
Prototypen v1 (0.5.0–0.10.0, 2024–2026) har sin egen logg i Linderå Groups
arbetsrepo.

## ng-v0.8.2 – 2026-11-13

Kontaktvägar utan mejladress: ingen personlig adress i källkoden, dokumentationen eller på sajten.

- **Prissidan** länkar till Linderå Groups kontaktformulär i stället för en mejladress (”Kontakta oss”, ”Begär offert”, ”Hör av dig”).
- **SECURITY.md** hänvisar till GitHubs privata sårbarhetsrapportering.
- **Vakt mot adresser:** `.github/scripts/check_public_tree.py` godkänner bara exempeladresser och en uttrycklig lista roll- och tjänsteadresser. Den körs i CI på varje push och på publiceringsträdet innan något når det publika repot.

## ng-v0.8.1 – 2026-11-10

Typografifix: svenska texter på sajten använder tankstreck (–), engelska behåller det långa strecket (—).

- **Språkneutral markup följer språket.** Sidtitlar (`… – Kollepedia NG`), avgränsare i aktivitetsflöden och historiken, tomma tabellceller och citatraden hämtar strecket ur den nya ordboksnyckeln `typo.dash` i stället för ett inskrivet tecken.
- **Svenska texter rättade:** utkastmejlet till författare, mailto-ämnena på prissidan, serverns svenska meddelanden (robotkontrollen, för många förfrågningar, importrapporten, mallens exempelrad, godkännandemejlet).
- **Engelska meningsstreck** som var kortstreck är nu långa streck; intervall (`a–z`, `{from}–{to}`) behålls.
- **Vakttest** (`typography.guard.test.ts`) stoppar nya långa streck i svensk text, streck längre än ett långt streck i båda språken, och inskrivna långa streck i språkneutral kod.

## ng-v0.8.0 – 2026-11-10

Städad och härdad inför att källkoden görs publik: svensk dokumentation utan interna anteckningar, ofärdig funktionalitet avstängd, säkerhetsgranskning åtgärdad och miljöspecifik konfiguration flyttad ur repot.

### Innehåll
- **Om Kollepedia** (tidigare "Om projektet") berättar historien från wikin i KOMIMP-projektet 2007 – byggd av Transportidé AB med Mats Börjesson som drivande kraft, borta från nätet omkring 2012 – till dagens plattform, och pekar på samlingen *Kollepedia* med de 225 artiklar som räddats ur Wayback Machine.
- **AI-stödet är avstängt tills det är klart.** Funktionsflaggan `FEATURE_AI` (standard av) styr både servern, som svarar 404 `feature_disabled` på `/ai/*` och `/prompts`, och webben, som döljer Harmonisera, AI-inställningarna, importens AI-flik och manualens AI-avsnitt. Prissidan markerar AI-funktionerna som kommande. `GET /api/v1/features` visar flaggornas läge.
- **Manualen stämmer med produkten:** lösenord minst 12 tecken, fastställd är en stämpel och ingen status, e-post skickas på riktigt från no-reply@kollepedia.se, MCP-avsnittet beskriver den publika ändpunkten `https://kollepedia.se/mcp` med dess fem läsverktyg. Det interna acceptanstestprotokollet är borttaget ur appen.
- **Sidfotens länk** går till rätt GitHub-organisation.

### Säkerhet
- Markdownlänkar accepterar bara http(s), mailto, relativa adresser och ankare – `javascript:`- och `data:`-länkar renderas som text (lagrad XSS).
- Rate limiting och registreringsheuristiken räknas per besökare bakom proxyn (webben läser `X-Forwarded-For` från Traefik, API:et tar det sista värdet) i stället för att alla delade en hink.
- AI-proxyns valfria bas-URL kräver https mot en publik värd (SSRF); AI-anropen kräver skrivrätt.
- Servern vägrar starta utan stark `JWT_SECRET` när `DEV_AUTH` är av, och `DEV_AUTH` är av som standard. Förnyelsekakan är `Secure` i drift; lösenords- och e-postbyte loggar ut övriga sessioner.
- Säkerhetsheaders (HSTS, nosniff, frameDeny, Referrer-Policy, Permissions-Policy) via Traefik och Content-Security-Policy via SvelteKit; containrarna kör med `no-new-privileges`.
- Importen avbryter inläsningen vid radtaket, kontrollerar filtyp på innehåll, parsar XML med `defusedxml` och attribuerar bara rader till importören eller oanspråkade profiler. Fritextfält har maxlängder.
- E-post: utan tillåtelselista skickas ingenting när ett relä är konfigurerat; inga personadresser som standardvärden.
- Uppdaterade beroenden med kända sårbarheter (pyjwt, mcp, certifi, anyio, cryptography; @sveltejs/kit, devalue, prosemirror-view, markdown-it, cookie).

### Drift
- **En compose-fil för alla miljöer:** `docker-compose.deploy.yml` härleder projekt-, container-, volym- och routernamn ur `APP_NAME` och läser `PUBLIC_HOST`/`PUBLIC_ORIGIN` ur `.env`; `docker-compose.alias.yml` lägger till omdirigering från aliasnamn. Inga värdnamn i repot.
- **Deploy-workflowerna** hämtar miljöns adress ur repovariabler (`STAGING_URL`, `PRODUCTION_URL`, valfria `*_ALIAS_RULE`), skriver identiteten in i serverns `.env` före varje deploy, synkar inte interna kataloger och har `permissions: contents: read`.
- **Dokumentationen är på svenska** och beskriver nuläget: `docs/VISION.md`, `docs/ARKITEKTUR.md`, `docs/TIDSMASKINEN.md`, `docs/DRIFT.md`, nya README, CONTRIBUTING, SECURITY och CLAUDE.md. Linderå Groups egna driftdetaljer ligger utanför publiceringsträdet. `.env.example` följer med till det publika repot.
- **Publika repot** börjar om med en ren historik från den här releasen.

## ng-v0.7.0 – 2026-11-09

### Innehåll
- **Kollepedia NG i skarp drift på [kollepedia.se](https://kollepedia.se), i
  beta.** Första produktionsreleasen: öppen källkod under AGPL-3.0-or-later,
  publik MCP-server på `/mcp`, exportspärr för licensbundet innehåll.
  Taggarna heter `ng-vX.Y.Z` under betan; `v1.0.0` kommer när den är över.
- **Mejlen har riktiga länkar och Kollepedias formspråk.** Verifierings- och
  återställningsbreven bygger absoluta länkar från miljövariabeln
  `PUBLIC_ORIGIN` och skickas som HTML med ordmärke, knapp och länken i
  klartext; textversionen följer med för klienter utan HTML. Tidigare stod
  bara en relativ sökväg i brevet.

### Drift
- **NG ersatte prototypen på kollepedia.se 2026-11-09.** Produktionsdatabasen
  såddes från testmiljön och rensades från sessioner, engångstoken, mejlrader
  och seed-lösenord innan den togs i bruk. `www.kollepedia.se` och
  `kollepedia.linderagroup.com` omdirigerar (301) till `kollepedia.se`.
- **_Deploy to Production_ vägrar** en katalog som saknar `.env` eller
  fortfarande ser ut som prototypen, i stället för att kräva filer som bara
  deployen själv kan lägga dit.

## ng-v0.6.0 – 2026-11-09

### Licens
- **Koden är GNU AGPL-3.0-or-later** (var Apache-2.0). Plattformen är gratis
  för sektorn och organisationer betalar för privata rum, hosting och
  support, så det som ska skyddas är den gemensamma kanonen. AGPL:s
  nätverksklausul gör återgivande till regel för den som hostar en ändrad
  Kollepedia, medan självhosting, API/MCP-integration och
  singel-tenant-erbjudandet är fria. Innehållslicenserna per samling är
  oförändrade. Nya `CONTRIBUTING.md` (DCO, ingen CLA) och `SECURITY.md`.

### Drift
- **MCP, steg 1: läsa och söka publikt.** `/mcp` är en MCP-server över
  Streamable HTTP utan inloggning, monterad i API-servern med samma
  synlighetsregel som en anonym besökare. Fem verktyg: `list_collections`,
  `get_collection`, `search_concepts`, `get_concept`, `get_concept_history`.
  Inga skrivningar; samlingar utan vidarespridningsrätt är sökbara men
  markerade som icke exporterbara. Steg 2, inloggad åtkomst med personliga
  API-nycklar, återstår.
- **Publikt repo.** Utvecklingen sker i ett arbetsrepo; det publika
  `Lindera-Group/kollepedia` får en commit per release med releasenoterna som
  meddelande och samma tagg, efter en hemlighetsskanning av
  publiceringsträdet. Bidrag utifrån kommer som pull requests på det publika
  repot och förs in med upphovspersonen bevarad.
- **E-post till alla med `EMAIL_ALLOWLIST=*`.** Tillåtelselistan för utgående
  mejl hade inget läge för riktiga användare. Det enda värdet `*` öppnar nu
  för alla mottagare; allt annat är fortfarande en hård lista. SMTP-relä
  anges i `SMTP_URL` och avsändare i `EMAIL_FROM`.
- **Produktion blir kollepedia.se.** Alias omdirigeras permanent till den
  kanoniska adressen. Konton som skapas administrativt får en oanvändbar
  slumphash i stället för tomt lösenord – en tom hash är en övertagbar profil.

### Rättat
- **Samtrafikens begreppslista är låst** som de andra referenssamlingarna
  (migrering 018). Låsningen 2026-07-15 tog bara de organisationslösa publika
  samlingarna, och Samtrafikens lista ägs av Samtrafiken, så den stod olåst
  sedan publiceringen 2026-09-15. Direkta ändringar kan nu bara göras av
  Samtrafikens organisationsadministratörer och superadministratörer; alla
  inloggade kan fortfarande föreslå via grenar.
- **Ingen export av samlingar utan vidarespridningsrätt.** En samling vars
  licens säger `redistribution: not_permitted` kan läsas och sökas på sajten
  och i API:et men inte laddas ner som CSV, Markdown, JSON-LD, SKOS eller TBX:
  servern svarar 403 `export_not_permitted`, samlingssidan visar förklaringen
  i stället för exportknappen, och listexporter utelämnar sådana begrepp med
  en notis. Listposter kan inte längre fästa en version från ett annat
  begrepp än det de pekar på (400 `version_mismatch`).

## ng-v0.5.1 – 2026-11-08

### Drift
- **NG tar över repot.** Prototypen lämnar trädet; `server/`, `web/` och
  `docs/` ligger i repots rot. Interna namn tappar "ng": paketen heter
  `kollepedia-server` och `kollepedia-web`, databasfilen `kollepedia.db` och
  lagringsnycklarna i webbläsaren `kollepedia-*`. Produktnamnet Kollepedia NG
  är oförändrat.
- **CI** kör på varje push till `master` och varje pull request.

### Rättat
- **Begreppssidor svarade 500 vid direktladdning.** Webbens runtime-image
  saknade `node_modules`, men adapter-node lämnar paketen under
  `dependencies` (tiptap, yjs) utanför bundlen, så serverrenderingen av
  `/concepts/<id>` föll på `ERR_MODULE_NOT_FOUND`; navigering inne i appen
  fungerade och dolde felet. Imagen installerar nu produktionsberoendena, och
  deploy-workflowen röktestar en begreppssida efter hälsokontrollen.

## ng-v0.5.0 – 2026-11-07

### Innehåll
- **Tre nya samlingar med Transmodel-mappningar**: NOPTIS (174 termer ur
  specifikationerna, delar per gränssnitt), Nordic NeTEx Profile (370 element
  och 937 ER-relationer ur Enturs dokumentation) och SUTI (256 begrepp ur
  SUTI-dokumentationen). 123 NOPTIS- och 346 NeTEx-mappningar till Transmodel
  granskade och tillämpade.
- **Samtrafikens begreppslista publicerad med tillstånd**: öppen att läsa med
  `edit_policy=org`, licensetikett "publicerad med tillstånd, ingen
  vidaredistribution" samt maskinläsbara rättighetsfält.
- **Inkrementell import** av samlingar i en befintlig databas utan att tömma
  den.
- **Skyltfönstret pseudonymiserat**: demonstrationssamlingen använder fiktiva
  aktörer och märks "alla aktörer är fiktiva".

### Drift
- **Migreringar körs vid containerstart** (`scripts/run_migrations.py`,
  tabellen `schema_migrations`); en fallerande migrering håller containern
  ohälsosam.
- **Migrering 017**: organisationsägda samlingar får `edit_policy=org`.
- **API-dokumentation under `/api/v1`**: `/api/v1/openapi.json`,
  `/api/v1/docs` och `/api/v1/redoc` passerar SvelteKit-proxyn.
- **Versionssträngarna samordnade** till 0.5.0 i server och webb.

## ng-v0.4.0 – 2026-08-13

### Säkerhet
- **Personliga aktiveringslänkar**: superadmin skapar en engångslänk (giltig
  30 dagar) per importerad upphovsperson; anspråk utan länk går till manuell
  granskning innan kontot får skrivrätt.
- **Listgrinden täppt**: konton som väntar på granskning kan inte skapa
  listor eller listposter.
- **429-fix**: rate-limit-prefixet `/auth` matchade även `/authors`.
- **Lösenordskrav höjt till 12 tecken** för nya lösenord.

### Funktioner
- **Rollanpassad manual** med Administration-avsnitt bara för superadmins.
- **Författarlänkar överallt** (i historiken, versionstabellen, jämförelsen
  och förslagen).
- **Verktygsrad på samlingssidan**: Redigera/Exportera/Importera/Skrivskydda.
- `/activate` visar bara det relevanta formuläret.

## ng-v0.3.0 – 2026-07-15

Första taggade NG-releasen; etablerar `ng-v*`-taggserien skild från
prototypens `v0.x`.

- **design-guard.mjs** i nolltoleransläge (pre-commit + vitest + CI): inga
  hårdkodade CSS-värden, primitiver, designmanual och tre teman i synk.
- **Nivå 3-harness** (`tests/design/`): rytmkontrakt, axe-core WCAG A/AA per
  sida × tre teman, visuell regression.
- **Designkontrakt v1.1**: Crimson Pro i höjd läsyteskala, logotypsnitt,
  sidrubriker under logotypen.
- **Begreppskort, sökflöde, jämförelsevy och CollectionBadge** enligt
  kontraktet.
