# Att bidra till Kollepedia

Kollepedia är kollektivtrafikens gemensamma ordförråd, byggt av dem som
använder det. Felrapporter, terminologifrågor och kod är lika välkomna.

## Innan du börjar

- **Licens.** Koden är GNU AGPL-3.0-or-later. Genom att bidra godkänner du att
  ditt bidrag licensieras på samma sätt. *Innehållet* – terminologin – är
  licensierat per samling och ändras aldrig via pull requests: redigera det i
  appen, där proveniensen bokförs.
- **Signera dina commits (DCO).** Varje commit bär raden `Signed-off-by: Namn
  <e-post>` (`git commit -s`), som intygar att du har rätt att lämna bidraget
  under projektets licens. Se [Developer Certificate of
  Origin](https://developercertificate.org/). Inget CLA.
- **Små, avgränsade ändringar** slår stora. Öppna ett ärende först för allt
  som ändrar beteende användare kan se.

## Köra projektet

```
cd server && uv sync && DEV_AUTH=1 uv run uvicorn app.main:app --port 8088
cd web && npm install && npm run dev          # http://localhost:5181
```

Tester och kontroller, som CI kör på varje pull request:

```
cd server && uv run ruff check app scripts tests && uv run pytest
cd web && npm run check && npm test && npm run build
```

Webben har en designgrind (`npm test` kör den): tokens ur `app.css`, tre
teman och mönstren i `web/design-system.html`. Läs manualen innan du rör
något under `web/src/`.

## Pull requests

1. Utgå från `master`, ett ämne per gren.
2. Skriv eller uppdatera tester; serverns svit är `pytest`, webbens `vitest`.
3. Språk: kod och kodkommentarer på engelska, dokumentation på svenska.
   Produkten är tvåspråkig (svenska och engelska) och varje text i
   gränssnittet behöver båda nycklarna.
4. Beskriv *varför* i pull requesten. Releasenoterna skrivs av underhållarna
   utifrån sammanfogade pull requests.

## Rapportera ett säkerhetsproblem

Öppna inget publikt ärende. Se [SECURITY.md](SECURITY.md).

## Uppförande

Var den kollega du själv skulle vilja ha i ett terminologimöte: precis,
nyfiken, tålmodig med andras definitioner. Underhållarna tar bort bidrag och
bidragsgivare som inte är det.
