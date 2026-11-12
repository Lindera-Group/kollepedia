# Kollepedia NG

Begreppsbank för kollektivtrafiken, byggd av Linderå Group. Begrepp med en
graf av oföränderliga versioner, historik som spelas upp (tidsmaskinen),
samlingar och listor, organisationer, ändringsförslag, realtidssamskrivning
och en publik MCP-server. Läs `docs/VISION.md` (varför), `docs/ARKITEKTUR.md`
(hur) och `docs/DRIFT.md` (drift) innan du ändrar något väsentligt.

Prototypen Kollepedia v1 (2024–2026) finns arkiverad i Linderå Groups
arbetsrepo; kopiera aldrig kod därifrån in i det här trädet. "NG" är en del av
produktnamnet, inget i sökvägar, paket, containrar eller lagringsnycklar bär
det.

## Struktur

- `server/` – FastAPI + SQLAlchemy, Python 3.13, hanterat med uv. Modeller,
  graftjänst och routrar i `app/`; migreringar, import, backup/återställning
  i `scripts/`; tester i `tests/`.
- `web/` – SvelteKit (Svelte 5, SSR via adapter-node), Node 22. Designmanualen
  är `web/design-system.html`; den mekaniska grinden `web/scripts/design-guard.mjs`.
- `docs/` – vision, arkitektur, tidsmaskinen, drift.
- `.github/workflows/` – `ci.yml`, `deploy-staging.yml`, `deploy-production.yml`.

## Kommandon

```bash
# Server
cd server
uv sync
uv run python scripts/run_migrations.py           # skapar/uppdaterar server/data/kollepedia.db
DEV_AUTH=1 uv run uvicorn app.main:app --reload --port 8088
uv run ruff check app scripts tests && uv run pytest -q

# Webb
cd web
npm install
npm run dev                                       # port 5181
npm run check && npm test && npm run build        # npm test kör även designgrinden

# Designgrinden ensam (körs också som pre-commit; aktivera en gång per klon:
# git config core.hooksPath .githooks)
cd web && node scripts/design-guard.mjs
```

Portarna är webb 5181 och server 8088; använd aldrig ramverkens standardportar.

## Databas och migreringar

- Utvecklingsdatabas: `server/data/kollepedia.db` (gitignorerad). Driftsatta
  databaser ligger i namngivna Docker-volymer.
- En migrering är ett nytt idempotent `server/scripts/migrate_NNN_*.py` som tar
  databasens sökväg som första argument. `scripts/run_migrations.py` kör dem i
  ordning och bokför dem i `schema_migrations`; servercontainern kör det vid
  start, så en deploy kan aldrig lämna en miljö efter.

## Funktionsflaggor

Ofärdig funktionalitet är avstängd med miljövariabler och får inte synas i
gränssnittet när flaggan är av. I dag: `FEATURE_AI` (AI-utkast, textextraktion
och promptmallar; standard `0`). Servern vägrar anropen och webben döljer
knappar, flikar och manualavsnitt. Nya flaggor följer samma mönster
(`server/app/features.py`, `web/src/lib/features.ts`).

## Kvalitetsgrindar före varje commit

ruff + pytest (server), `npm run check` + `npm test` + `npm run build` (webb),
designgrinden ren. Conventional commits; trailern anger modellen som skrev
koden (`Co-Authored-By: Claude <modell> <noreply@anthropic.com>`). Ladda
skillen `ui-guardrails` för varje ändring under `web/src/`. Kod och
kodkommentarer på engelska, dokumentation på svenska, gränssnittstexter på
både svenska och engelska.

## Driftsättning

Bara via GitHub Actions – aldrig rsync för hand. *Deploy to Staging* tar gren
och databasläge; *Deploy to Production* kräver `staging_verified=true`. Allt
miljöspecifikt (värdnamn, ursprung, mejl, flaggor) ligger i serverns `.env`
och i repots Actions-variabler, inte i filerna. Se `docs/DRIFT.md`.

## Versioner och releaser

Taggarna heter `ng-vX.Y.Z` under betan på kollepedia.se; `v1.0.0` blir den
första releasen när betan är över. Fråga före varje release vilken höjning
(patch/minor/major) som gäller. I en releasecommit: höj de fem
versionssträngarna (`server/pyproject.toml`, projektraden i `server/uv.lock`,
`version=` i `server/app/main.py`, `web/package.json` och båda fälten i
`web/package-lock.json`), tagga, skapa GitHub-releasen med svenska noter
(`## Innehåll` / `## Drift` / `## Rättat`), spegla dem i `CHANGELOG.md` och
deploya staging och sedan produktion så att `/api/v1/openapi.json` visar den
nya versionen på båda.

## Data och rättigheter

Partnerinnehåll (K2, Samtrafiken, Transmodel, NOPTIS, NeTEx, SUTI …)
publiceras under rättigheter per samling. Committa aldrig databasfiler,
säkerhetskopior eller exporter.
