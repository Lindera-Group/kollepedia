# Kollepedia NG

> Begreppsbank för kollektivtrafiken – gemensam förståelse mellan människor
> och organisationer, med versionshistorik för varje definition.

Kollepedia samlar kollektivtrafikens terminologi – från Transmodel och NeTEx
till svenska ordböcker och branschens begreppslistor – i en gemensam,
versionerad begreppsbank. En definition är inte en textrad utan en graf av
oföränderliga versioner: den kan revideras, grenas, syntetiseras och
översättas, och varje steg bevaras med upphovsperson, tidpunkt och motivering.
Historiken kan spelas upp ord för ord i **historiken** (tidsmaskinen), se
[`docs/TIDSMASKINEN.md`](docs/TIDSMASKINEN.md).

Kollepedia är i skarp drift, i beta, på [kollepedia.se](https://kollepedia.se).
Varför plattformen finns och vilka principer den bygger på står i
[`docs/VISION.md`](docs/VISION.md). Bakgrunden – från wikin som föddes i
KOMIMP-projektet till i dag – finns på [kollepedia.se/about](https://kollepedia.se/about).

## Repots delar

```
server/          FastAPI + SQLAlchemy (SQLite som standard, förberett för Postgres)
├── app/         modeller, graftjänst, API-routrar, realtidsrelä, publik MCP-server
├── scripts/     migreringar (körs vid containerstart), import, backup/återställning
└── tests/       graf-invarianter och API-tester (pytest)
web/             SvelteKit (Svelte 5, SSR via adapter-node)
├── src/lib/timemachine/       diff-, uppspelnings- och animationsmotorn
├── design-system.html         designmanualen
└── scripts/design-guard.mjs   den mekaniska designgrinden (körs i npm test)
docs/            VISION · ARKITEKTUR · TIDSMASKINEN · DRIFT
```

## Komma igång lokalt

```bash
# Server (port 8088) – kräver uv (https://docs.astral.sh/uv/)
cd server
uv sync
uv run python scripts/run_migrations.py          # skapar/uppdaterar server/data/kollepedia.db
DEV_AUTH=1 uv run uvicorn app.main:app --reload --port 8088

# Webb (port 5181)
cd web
npm install
npm run dev
```

Öppna http://localhost:5181. Databasen är tom från början; en första
superadministratör blir den som registrerar sig först. Innehåll kommer in via
importvyn (CSV eller Excel per samling) eller skripten i `server/scripts/`.
Med `DEV_AUTH=1` i miljön tillåter utvecklingsservern `X-User`-huvudet som
inloggningsersättning; flaggan är av som standard och alltid av i drift.

Kvalitetsgrindar, samma som CI kör:

```bash
cd server && uv run ruff check app scripts tests && uv run pytest -q
cd web && npm run check && npm test && npm run build
```

## Arkitektur i korthet

Servern äger datamodellen: begrepp med en riktad acyklisk graf av oföränderliga
versioner, stand-off-annotationer, typade relationer, samlingar och listor,
organisationer med roller, ändringsförslag, diskussioner och bevakning.
Webben renderar den publika läsvägen på servern (SEO) och proxar `/api` till
API:et, så allt är same-origin bakom en reverse proxy. Detaljer i
[`docs/ARKITEKTUR.md`](docs/ARKITEKTUR.md).

Funktioner som inte är färdiga är avstängda med funktionsflaggor i miljön;
i dag gäller det AI-stödet (`FEATURE_AI`, standard av). Se `docs/DRIFT.md`.

## MCP

Kollepedia talar Model Context Protocol. Den hostade ändpunkten är publik och
skrivskyddad – samma synlighet som en anonym besökare, inget konto behövs:

```
claude mcp add --transport http kollepedia https://kollepedia.se/mcp
```

Verktygen är `list_collections`, `get_collection`, `search_concepts`,
`get_concept` och `get_concept_history`. Samlingar vars licens inte tillåter
vidarespridning är sökbara men inte exporterbara, och verktygen säger det.
Inloggad åtkomst (skrivningar, privata samlingar) med personliga API-nycklar
är nästa steg. Implementationen är `server/app/mcp_public.py`;
`server/mcp_server.py` är en stdio-variant för lokal utveckling.

## Driftsättning

Kollepedia körs som två containrar (server och webb) bakom en reverse proxy
med TLS, konfigurerade med miljövariabler i en `.env` bredvid compose-filen.
Allt miljöspecifikt – värdnamn, ursprung, mejlrelä, funktionsflaggor – ligger
i den filen, inte i repot. Hur man sätter upp, uppgraderar, säkerhetskopierar
och återställer en installation står i [`docs/DRIFT.md`](docs/DRIFT.md).

## Versioner och releaser

Taggarna heter `ng-vX.Y.Z` under betaperioden på kollepedia.se; `v1.0.0` blir
den första releasen när betan är över. Releasenoterna finns på GitHub och
speglas i [`CHANGELOG.md`](CHANGELOG.md).

## Var utvecklingen sker

Linderå Group utvecklar Kollepedia i ett arbetsrepo med full historik. Varje
release publiceras hit som en commit med releasenoterna som meddelande och
samma tagg. Pull requests mot det här repot är välkomna – de förs in i
arbetsrepot med upphovspersonen bevarad och kommer med i nästa release. Läs
[`CONTRIBUTING.md`](CONTRIBUTING.md) först.

## Licens

Koden är [GNU AGPL-3.0-or-later](LICENSE): fri att köra, läsa, ändra, hosta och
sälja tjänster kring; den som erbjuder en ändrad version till andra, även
över nätet, erbjuder dem källkoden på samma villkor. *Innehållet* – själva
terminologin – har egna licenser per samling och omfattas inte av
kodlicensen. Bidrag tas emot under samma licens med en DCO-signatur, se
[`CONTRIBUTING.md`](CONTRIBUTING.md).
