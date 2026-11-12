# Kollepedia – arkitektur

Komplement till [VISION.md](VISION.md): det här beskriver vad som faktiskt är
byggt och de val som gjorts där visionen lämnade utrymme.

## Domänmodell (server/app/models.py)

Den egna logiken är medvetet smal: tillägg av versioner, uttrycklig grening,
uttrycklig syntes och flytt av huvudpekaren. Ingen generell
sammanslagningsmotor.

```
Organisation ─┬─ User (roll: admin | editor | viewer)
              └─ Collection ── Concept ─┬─ Branch (namn, head_version_id)
                   │                    ├─ Version (oföränderlig)
                   │                    │    ├─ VersionEdge (barn → förälder, typad)
                   │                    │    ├─ Annotation (stand-off, W3C-form)
                   │                    │    └─ Endorsement (återkallbar)
                   │                    ├─ ConceptRelation (typad, med not)
                   │                    ├─ ChangeProposal (gren → main)
                   │                    ├─ Comment, Watch
                   │                    └─ (aktivitet beräknas, ingen händelsetabell)
                   └─ licens, synlighet, redigeringspolicy, lås, arkiv
PinList ── ListItem (fäster en viss version eller följer huvudet)
SavedPrompt, EmailMessage, ActivationLink, refresh-tokens
```

Bärande beslut:

- **Versioner är oföränderliga.** Det finns ingen uppdateringsändpunkt för
  versionsinnehåll. Redigering skapar en ny version och en typad kant till
  föräldern eller föräldrarna: `revised_from`, `branched_from`,
  `synthesized_from` (flera föräldrar, ordningstal 0 är huvudföräldern),
  `translated_from` (får korsa begrepp – det *är* översättningsmodellen) och
  `promoted_from` (äldre innehåll som nytt huvud).
- **Acyklisk genom konstruktion.** Kanter skapas bara tillsammans med en helt
  ny barnversion och föräldrarna måste redan finnas. Ingen ändpunkt länkar två
  befintliga versioner, så cykler kan inte uppstå.
- **Huvudpekare** ligger på `Branch` (varje begrepp har en gren `main`).
  `revise` kräver att basversionen är grenens huvud, annars 409 – den som
  förlorar en kapplöpning uppmanas grena. `promote` kopierar äldre innehåll
  till en ny huvudversion.
- **Etiketter ligger på versioner**, inte begrepp, så kategoriseringen är
  själv versionerad och historiken kan animera pluppar som kommer och går.
- **Annotationer** är stand-off-spann (`start`, `end`, `quote`, typat
  JSON-värde) per version: `section`, `author`, `variant`, `confidence`,
  `source_citation`. Eftersom versioner är oföränderliga förankras de aldrig om
  inom en version.
- **Proveniens** är ett JSON-objekt på varje version (`kind: human | llm |
  import`, plus modell, leverantör och prompt för modeller och källuppgifter
  för importer).
- **Fastställanden** är attribuerade rader per organisation och begrepp; ett
  återkallande sätter `withdrawn_at` och en not och raderar aldrig.
- **Status** på versionen följer `draft → proposed → deprecated | superseded`.
  Fastställd är ingen status utan ett fastställande.
- **Samlingar** bär synlighet (`public`, `org_private`, `private`),
  redigeringspolicy (`org`, `anyone`), licensfält med
  vidarespridningsrätt, lås och arkiv. En låst samling tar bara emot grenar
  och ändringsförslag; en arkiverad inga skrivningar alls.

## Lagring

SQLAlchemy 2.0 med `DATABASE_URL`. SQLite som standard (en fil i en Docker-
volym i drift); schemat använder bara portabla typer (strängar som id, JSON,
tidsstämplar) och är förberett för Postgres. Grafen traverseras i
tjänstelagret (`app/graph.py`) över det inlästa begreppet – historiker per
begrepp är små, så inga rekursiva frågor behövs.

Migreringar är idempotenta skript `scripts/migrate_NNN_*.py` som körs av
`scripts/run_migrations.py` vid containerstart och bokförs i
`schema_migrations`.

## API (server/app/routers/)

Bas `/api/v1`, dokumenterat på `/api/v1/docs`. Läsning av publika samlingar är
öppen; allt annat kräver konto.

- **Identitet.** `POST /auth/register` (e-post, visningsnamn, lösenord, valfritt
  användarnamn för att göra anspråk på en importerad upphovsperson; en
  proof-of-work-utmaning stoppar robotar), `POST /auth/login` (e-post eller
  användarnamn), åtkomsttoken JWT HS256 i `Authorization: Bearer` (12 timmar),
  förnyelsetoken i httpOnly-kaka (`POST /auth/refresh`, roteras, återkallbar),
  verifieringsbrev, glömt lösenord, lösenordsbyte. `X-User` som
  utvecklingsersättning finns bara när `DEV_AUTH=1`.
- **Begrepp och versioner.** `GET /concepts` (sök över huvudversioner med
  filter), `POST /concepts`, `GET /concepts/{id}`, `GET /concepts/{id}/graph`
  (hela historiken – tidsmaskinens last), `POST /concepts/{id}/versions`
  (`revise | branch | synthesize | translate`), `POST /concepts/{id}/promote`,
  `GET /versions/{id}` (permalänk).
- **Relationer, fastställanden, ändringsförslag, diskussioner, bevakning,
  aktivitet.** Egna routrar; förslag sammanfogas som snabbspolning eller som
  syntes med båda huvudena som föräldrar.
- **Samlingar och listor.** Skapa, ändra, låsa, arkivera; import per samling
  (CSV/XLSX, torrkörning); export av samlingar och listor som CSV, Markdown,
  JSON-LD, SKOS (Turtle) och TBX – spärrad för samlingar utan
  vidarespridningsrätt.
- **Organisationer.** Skapa, godkänna, medlemmar och roller, avstängning.
- **Administration.** Användare, granskning, aktiveringslänkar för importerade
  upphovspersoner, utkorg för e-post, händelselogg.
- **AI (bakom `FEATURE_AI`).** `POST /ai/draft` och `POST /ai/extract` med
  användarens egen nyckel i `X-LLM-Key`, proxad utan att sparas eller loggas;
  sparade prompter i `/prompts`. Avstängt svarar servern 404
  `feature_disabled`.
- **Övrigt.** `/stats`, `/tags`, `/features` (vilka flaggor som är på),
  `/health`.

Skyddslager: rate limiting per IP på `/auth/*` och `/ai/*`, hård
tillåtelselista för utgående e-post (`EMAIL_ALLOWLIST`, där bara värdet `*`
öppnar för alla), argon2-hashade lösenord, engångstoken som lagras hashade.

## Realtid

`/ws/collab/…` är ett Yjs-relä (`app/realtime.py`) för samskrivning av ett
utkast. Rummen är flyktiga – ingenting att säkerhetskopiera; det som sparas
blir som alltid en version.

## MCP

`app/mcp_public.py` monterar en MCP-server över Streamable HTTP på `/mcp` i
samma process som API:et, med samma synlighetsregel som en anonym besökare:
`list_collections`, `get_collection`, `search_concepts`, `get_concept`,
`get_concept_history`. `mcp_server.py` i serverroten är en stdio-variant för
lokal utveckling.

## Webb (web/)

SvelteKit 2 med Svelte 5-runor, serverrenderad via adapter-node. Den publika
läsvägen renderas på servern (SEO) och hydreras; inloggat och administrativt
innehåll hämtas i klienten. `hooks.server.ts` proxar `/api` och `/health` till
API:et (`API_URL`) så att allt är same-origin; `/healthz` besvaras lokalt för
containerns hälsokontroll. Sessionen ligger i webbläsaren och tas över vid
hydrering; förnyelsekakan är den enda inloggningssignal servern ser.

Designsystem: varmt papper i tre teman (ljust, mörkt, högkontrast), Crimson
Pro för innehåll, Familjen Grotesk för gränssnitt, Fragment Mono för metadata.
Designmanualen är `web/design-system.html`; `scripts/design-guard.mjs`
upprätthåller tokens, primitiver och sidstruktur mekaniskt. Gränssnittet är
tvåspråkigt (sv/en) med språket i en kaka så att servern renderar rätt språk.

Funktionsflaggor når webben som miljövariabler i webbcontainern och levereras
till klienten via rotlayoutens serverladdning (`web/src/lib/features.ts`).

## Portar

Utveckling: webb **5181**, server **8088**. I drift publiceras inga portar;
reverse proxyn är enda ingången.
