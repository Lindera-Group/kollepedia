# Tidsmaskinen – historiken som spelas upp

Den centrala särskiljande funktionen: en filmisk, skrubbningsbar visualisering
av ett begrepps väg genom versioner och grenar. Målet är att göra
versionshistorik i git-klass begriplig – och vacker – för människor som aldrig
sett en diff.

## Övergången (version N → N+1): ändringarna spelas upp längs texten

En övergång går igenom texten **i läsordning, ändring för ändring**, som en
redaktör som arbetar från början till slut. För varje ändrat område: borttagen
text får en röd ton som tonas in medan texten gråar; ersätts den skrivs den nya
texten in på grön botten, tecken för tecken, med en lysande markör vid
skrivfronten och omgivande text som vidgas mjukt som en ridå som öppnas; sedan
tonas det röda ut och kollapsar, ridån stängs, och nästa ändring tar vid. De
gröna tonerna ligger kvar som ett spår av det nya och löses upp tillsammans i
det sista steget, så att version N+1 står i vila. Rubriken landar alltid före
definitionen.

Allt är en enda sammanhängande tidslinje som kan pausas var som helst. Knappen
**Ordning** växlar till den alternativa **samtidiga** koreografin: allt rött
markeras först, sedan skrivs allt grönt, sedan kollapsar allt rött på en gång.

Samma motor animerar begreppets **benämning** och dess **definition**. Fält
som inte är text (status, språk) får en mjuk puls när de ändras.
**Etikettpluppar** zoomar in från en punkt när de dyker upp och ut till en
punkt när de försvinner, med animerad bredd så att grannarna flyter om mjukt.

## Uppspelningsmodellen – historik som video

- En **tidslinje** ligger längst ner. Versionerna är punkter placerade
  **proportionellt mot verklig tid** (med ett minsta visuellt avstånd så att
  nästan samtidiga versioner går att skilja åt). Årtal ger skalan.
- **Spela/pausa** och ett dragbart **spelhuvud** låter dig spela upp hela
  historiken som en film eller pausa var som helst, även mitt i en övergång.
- **Kapitelpilar** hoppar till föregående eller nästa version.
- Vid **grenpunkter** låter ett grenval dig välja om uppspelningen följer
  huvudlinjen eller grenen; vägen räknas om och tidslinjen ritas om.
- Övergångens längd skalar med mängden ändrad text (med gränser), så att stora
  omskrivningar får andrum och stavfel går snabbt.

## Proveniens under markören (bläck-läge)

Varje ord vet vilken version som införde det (räknat genom att kedja diffar
längs den aktuella vägen – ett `git blame` per ord). I vila:

- **Hovra** över ett ord så markeras all text som infördes i samma version,
  och ett kort visar vem som skrev den, när, och versionens not.
- **Bläck-läget** tonar texten efter ålder: nyskrivna ord i fullt bläck, äldre
  lager allt blekare mot sepia – manuskriptets geologi i en blick.

## Tillgänglighet (ett krav från början, inte en putsning)

- `prefers-reduced-motion` (eller knappen på skärmen) växlar till en **statisk
  kombinerad diff** (rött genomstruket, grönt understruket) med lägena
  före/ändringar/efter – all information, ingen rörelse.
- Spelhuvudet är ett riktigt `role="slider"` med piltangenter (version för
  version), mellanslag för spela/pausa och en värdetext i stil med "version 3
  av 7, mars 2012".
- En **versionstabell** under scenen listar varje version med datum,
  upphovsperson, not och ändringssammanfattning – hela historien i vanlig DOM.

## Implementation (web/src/lib/timemachine/)

- `diff.ts` – Myers-diff på tokennivå. Tokens är *ord plus efterföljande
  blanksteg*; radbrytningar är egna tokens så att ordspann aldrig innehåller
  radbrytningar.
- `blame.ts` – kedjar diffarna v1 → … → vN för att märka varje token i varje
  version med den version som införde det.
- `script.ts` – ger varje ändrat ord egna **tidsfönster** längs en
  gemensam framstegsaxel: borttagna ord får ett markerings- och ett
  kollapsfönster, insatta ord ett skrivfönster. `layoutSequential` lägger
  fönstren efter varandra längs texten; `layoutGlobal` staplar dem i tre
  gemensamma takter. Samma rendering oavsett.
- `playback.svelte.ts` – motorn: en flyttalsposition (heltal = i vila på
  version i, bråkdel = inne i övergången i → i+1), rAF-loop, längd per övergång.
- `AnimatedText.svelte` – renderar tokens som mätta inline-block-spann. Arbetet
  per bildruta är **två CSS-variabler** på scenen (`--pm` framsteg, `--p4`
  avslut); varje stil per ord eller tecken är ett `calc()`/`clamp()` över dem
  med fönsterkonstanter per spann, så skrubbning är en enda stilskrivning per
  bildruta, ingen omrendering. Skrivmarkören är ett `::after` vars opacitet
  följer parabeln `4·t·(1−t)` av ordets lokala framsteg – synlig exakt medan
  ordet skrivs, noll i vila.
- `Timeline.svelte` – SVG-punkter och spelhuvud, grenval, reglagesemantik.
