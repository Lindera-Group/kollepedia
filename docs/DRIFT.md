# Kollepedia – drift

Så här driftsätts Kollepedia: två containrar bakom en reverse proxy, allt
miljöspecifikt i en `.env`. Beskrivningen gäller alla installationer; den
hostade instansen på kollepedia.se körs på samma sätt.

## Topologi

```
Internet ── reverse proxy (TLS, komprimering)
               │  Host(<PUBLIC_HOST>)
               │  └─ && PathPrefix(/ws | /mcp) ─────┐  (realtid, MCP)
               ▼                                     ▼
        web  (node, SvelteKit SSR, port 3000)   server (FastAPI, port 8088)
        ├── /            serverrenderade sidor       ├── /api/v1/…  REST
        ├── /api/…       proxy → server:8088         ├── /ws/collab  Yjs-relä
        ├── /health      proxy → server (hela kedjan)├── /mcp        MCP (HTTP)
        └── /healthz     lokalt (containerns hälsa)  └── /app/data   volym: SQLite + backuper
```

Compose-filerna förutsätter Traefik v2 med ett externt nätverk
`traefik-proxy` och en certresolver `letsencrypt`; en annan proxy fungerar
lika bra om etiketterna byts. Inga värdportar publiceras.

## Filer

| Fil | Roll |
|---|---|
| `docker-compose.deploy.yml` | Stacken för en driftsatt miljö (server, web, valfri Postgres). Namn på projekt, containrar, volymer och routrar härleds ur `APP_NAME`. |
| `docker-compose.alias.yml` | Valfritt tillägg: permanent omdirigering från alias-värdnamn (t.ex. `www.`) till `PUBLIC_HOST`. Används när `.env` har `ALIAS_HOSTS_RULE`. |
| `docker-compose.yml` | Bara lokal utveckling: en Postgres att prova mot. |
| `.env.example` | Alla variabler nedan med förklaringar. Kopieras till `.env` bredvid compose-filen på servern. |

## Miljövariabler (`.env`)

| Variabel | Krävs | Betydelse |
|---|---|---|
| `APP_NAME` | ja | Namnbas för projekt, containrar (`<APP_NAME>-server`, `-web`), volym (`<APP_NAME>-data`) och Traefik-routrar. Standard `kollepedia`; en testmiljö kan heta `kollepedia-staging`. |
| `PUBLIC_HOST` | ja | Värdnamnet proxyn ska svara på, t.ex. `kollepedia.se`. |
| `PUBLIC_ORIGIN` | ja | `https://` + värdnamnet. Används för absoluta länkar i mejl, CORS och adapter-nodes origin-kontroll. |
| `ALIAS_HOSTS_RULE` | nej | Traefik-regel för alias som ska omdirigeras, t.ex. ``Host(`www.kollepedia.se`)``. Aktiverar `docker-compose.alias.yml`. |
| `JWT_SECRET` | ja | Signerar åtkomsttoken (HS256). `openssl rand -hex 32`. Olika per miljö; byte loggar ut alla. |
| `EMAIL_ALLOWLIST` | nej | Tom eller saknad: bara den inbyggda standardadressen får post (testläge). Exakt `*`: alla mottagare (drift). Annars en kommaseparerad lista. |
| `EMAIL_FROM` | nej | Avsändaradress, t.ex. `no-reply@kollepedia.se`. Domänen behöver SPF, DKIM och DMARC hos reläet. |
| `SMTP_URL` | nej | `smtp://användare:lösenord@värd:587` (STARTTLS). Saknas den stannar breven i superadministratörens utkorg. |
| `FEATURE_AI` | nej | `1` slår på AI-utkast, textextraktion och promptmallar i server och webb. Standard `0`. |
| `DATABASE_URL` | nej | Standard SQLite i volymen. Postgres: se nedan. |
| `POSTGRES_PASSWORD` | nej | Bara med profilen `postgres`. |
| `DEV_AUTH` | nej | Av som standard och satt till `0` av compose-filen; `1` bara i lokal utveckling (tillåter `X-User`-huvudet). Utan `DEV_AUTH` vägrar servern starta om `JWT_SECRET` saknas eller är svag. |

## Installera

```bash
mkdir -p /opt/kollepedia && cd /opt/kollepedia
# lägg repots innehåll här (git clone eller rsync, utan .git och node_modules)
cp .env.example .env && chmod 600 .env   # fyll i värdena ovan
docker network inspect traefik-proxy >/dev/null   # proxyn måste redan köra
docker compose -f docker-compose.deploy.yml up -d --build
curl -s https://<PUBLIC_HOST>/health         # {"status":"ok"} = hela kedjan svarar
```

Med `ALIAS_HOSTS_RULE` i `.env`:

```bash
docker compose -f docker-compose.deploy.yml -f docker-compose.alias.yml up -d --build
```

Bilderna byggs på servern; inget register behövs. Migreringarna körs av
servercontainerns startskript innan API:et startar, så en uppgradering kan inte
lämna databasen efter. En misslyckad migrering håller containern ohälsosam –
återställ senaste backup, rätta, deploya igen.

Den första användaren som registrerar sig blir superadministratör.

## Driftsättning med GitHub Actions

Repot har två manuella workflows: *Deploy to Staging* (gren och databasläge
`keep | seed`) och *Deploy to Production* (kräver `staging_verified=true`).
Båda kör testerna, synkar källan till `/opt/<APP_NAME>` över SSH, kör
`docker compose up -d --build` på servern och verifierar hälsa, renderade
sidor och MCP-verktygen utifrån. Produktionsworkflown vägrar dessutom en
katalog utan `.env` och en datavolym utan tvättmarkören
`.production-scrubbed` (skrivs när en volym såtts från en annan miljö och
rensats från sessioner, tokens och mejl).

Repot behöver tre **secrets** – `VPS_HOST`, `VPS_SSH_KEY` (ed25519, publika
halvan i serverns `authorized_keys`), `VPS_KNOWN_HOSTS` (`ssh-keyscan`) – och
**variabler** per miljö: `STAGING_URL` och `PRODUCTION_URL` (det publika
ursprunget) samt valfritt `STAGING_ALIAS_RULE` / `PRODUCTION_ALIAS_RULE`.
Inför varje deploy skriver workflown miljöns identitet (`APP_NAME`,
`PUBLIC_HOST`, `PUBLIC_ORIGIN`, `ALIAS_HOSTS_RULE`) in i serverns `.env` ur
variablerna och lämnar hemligheterna orörda; värdnamn och sökvägar står alltså
varken i workflow-filerna eller i compose-filen. Rsyncen tar bara med det
bygget behöver (inte `.git`, `.github` eller interna kataloger).

## Backup och återställning

Databasen ligger i volymen `<APP_NAME>-data`. `scripts/backup_database.py`
körs i containern och skriver roterande kopior (tio senaste plus en per
ISO-vecka) till `/app/data/backups` i samma volym. Lägg en nattlig cron på
servern som kör skriptet och kopierar katalogen ut ur volymen:

```
30 3 * * * root docker exec kollepedia-server python scripts/backup_database.py \
  && docker cp kollepedia-server:/app/data/backups /srv/backup/kollepedia/
```

Återställning stoppar API:et, kör återställningsskriptet i en tillfällig
container på samma volym och startar igen (en säkerhetskopia av nuläget tas
automatiskt först):

```bash
docker compose -f docker-compose.deploy.yml stop server
docker compose -f docker-compose.deploy.yml run --rm --no-deps server python scripts/restore_database.py
docker compose -f docker-compose.deploy.yml start server
```

## Återgång

Deployer synkar källa och bygger om, så återgång är att deploya en känd god
ref: välj releasetaggen i workflowens ref-lista. Ändrade releasen schemat,
återställ också backupen från före deployen; migreringarna är additiva, så
rena kodåtergångar behöver sällan något databassteg.

## Övervakning

- Containrarnas hälsokontroller (`docker ps`, `docker inspect`).
- `curl -s https://<PUBLIC_HOST>/health` → `{"status":"ok"}` bevisar proxy →
  node → FastAPI; `curl -s https://<PUBLIC_HOST>/ | grep -c '<h1'` ≥ 1 bevisar
  serverrendering.
- Loggar: `docker logs -f <APP_NAME>-server` / `<APP_NAME>-web`.
- Minnesgränser i compose: 512 MB server, 256 MB webb.

## Säkerhetsläge

- Traefik sätter HSTS, `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy` och `Permissions-Policy` på alla svar (etiketterna i
  compose-filen); SvelteKit sätter Content-Security-Policy per svar
  (`web/svelte.config.js`). Containrarna kör utan privilegieeskalering.
- Webbcontainern läser klientadressen ur `X-Forwarded-For` (ett betrott hopp,
  Traefik) och API:et tar det sista värdet, så rate limiting räknas per
  besökare även bakom proxyn.
- `DEV_AUTH=0` i drift: bara riktiga Bearer-token godtas.
- `JWT_SECRET` måste sättas; servern varnar vid start om utvecklingsvärdet
  används utan `DEV_AUTH`.
- Appen är same-origin bakom proxyn; `CORS_ORIGINS` sätts till `PUBLIC_ORIGIN`
  och spelar bara roll för API-klienter i andra webbläsarursprung.
- Rate limiting på `/auth/*` och `/ai/*`; proof-of-work vid registrering;
  misstänkta registreringar går till manuell granskning.
- Rapportera sårbarheter enligt `SECURITY.md`.

## Publicering till det publika repot

Utvecklingen sker i ett arbetsrepo; varje releasetagg publiceras till
`Lindera-Group/kollepedia` av en workflow som bygger publiceringsträdet utan
interna kataloger, skannar det efter hemligheter och pushar en commit med
releasenoterna som meddelande och samma tagg. Pull requests utifrån tas emot
på det publika repot och förs in i arbetsrepot med upphovspersonen bevarad.

## SQLite → Postgres

Servern är förberedd (`DATABASE_URL`), och compose-filen har en valfri
Postgres bakom profilen `postgres`. Att gå över kräver drivrutinen
`psycopg[binary]` i `server/pyproject.toml`, ett engångsskript som kopierar
data, migreringsskript som inte är SQLite-specifika och en backup via
`pg_dump`. Inget av detta finns ännu; produktionen kör SQLite.
