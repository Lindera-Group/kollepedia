# Kollepedia – vision och principer

Det här dokumentet beskriver varför Kollepedia finns och vilka principer
plattformen bygger på. Hur det är byggt står i [ARKITEKTUR.md](ARKITEKTUR.md),
hur det driftsätts i [DRIFT.md](DRIFT.md).

## Syfte

Kollepedias uppgift är **gemensam förståelse mellan människor och
organisationer i kollektivtrafiken**: att de använder samma begrepp och lätt
kan enas om en definition – eller hantera det öppet när flera definitioner
finns.

Verkligheten är fragmenterad. Dussintals ordlistor lever i
upphandlingsunderlag, standardutkast, forskningsrapporter och interna wikis,
var och en med sin vinkel och sitt syfte. Kollepedia bekämpar inte den
verkligheten utan tar hand om den. Effekten av att fler arbetar i Kollepedia
ska vara att **kanoniska definitioner av de centrala begreppen växer fram och
förankras i standarder**, och att redan standardiserade begrepp återanvänds
allt bredare, i stället för att uppfinnas lokalt på bekostnad av
interoperabiliteten.

Två principer går igenom allt:

- **Proveniens och spårbarhet för allt.** Varje version av varje begrepp, och
  varje relation mellan begrepp, vet vem eller vad som skapade den (en
  människa, en import eller en modell), vad den härstammar från och **varför**
  den ändrades – en motivering i stil med ett commit-meddelande.
- **AI är hävstång, inte skatt.** All AI är *bring your own key*; plattformen
  bär ingen tokenkostnad. Och verktyget är fullt användbart helt utan AI.

## Vad som skiljer Kollepedia

Samarbetande, versionerad, flerspråkig terminologihantering är ett moget fält:
VocBench, Wikibase, PoolParty och andra gör det. Kollepedias särart är
kombinationen:

1. en **versionsgraf** per begrepp – revidering, gren, syntes, översättning och
   återställning som typade kanter mellan oföränderliga versioner – som är mer
   uttrycksfull än en linjär historik;
2. **listor som fästa profiler** för upphandling och projekt: frys exakta
   versioner medan kanonen fortsätter utvecklas;
3. **AI-valfritt, självhostbart och med egen nyckel**, för en offentlig sektor
   med suveränitetskrav.

Interoperabilitet är ett kärnvärde: modellen mappar till **PROV-O**
(proveniens), **SKOS/SKOS-XL** (begrepp och relationer), **ODRL**
(rättigheter) och **TBX** (utbyte), och exporterar till dem.

## Kärnbegrepp

| Begrepp | Vad det är | Liknelse |
|---|---|---|
| **Begrepp** | Den varaktiga identiteten för en idé ("hållplats"). Bär historik, redigeras aldrig direkt. | En artikels identitet |
| **Version** | En oföränderlig ögonblicksbild: benämning, språk, definition, annotationer, status, proveniens, not. | En commit |
| **Annotation** | Ett typat, fritt överlappande textspann över en versions definition (avsnitt, upphovsperson, källa …), lagrat bredvid texten. | En överstrykningspenna |
| **Relation** | En typad, motiverad länk mellan begrepp (relaterat, över-/underordnat, motsvarighet, ersätter). | En wikilänk med skäl |
| **Not** | Motiveringen på varje version och relation – ändringens *varför*. | `git commit -m` |
| **Samling** | Ett vokabulär där begrepp lever och utvecklas (Transmodel, en branschorganisations begreppslista). Ett hem per begrepp. Bär en innehållslicens. | En ordbok, ett namnrum |
| **Lista** | Ett urval för ett syfte (en upphandling, ett projekt) som refererar *fästa* versioner. Äger aldrig begrepp. | En profil, en spellista |
| **Fastställande** | En uttrycklig, attribuerad och återkallbar stämpel från en organisation: "den här definitionen använder vi". | Ett standardutskotts godkännande |
| **Organisation och roll** | Hemvist och behörigheter: superadmin → org-admin → redaktör → läsare → allmänhet. | – |

Skillnaden mellan samling och lista är det en användare måste förstå. Man
lägger inte en upphandlings termer *in i* Transmodel; man bygger en **lista**
som refererar exakt de Transmodel-versioner man behöver, fästa så att de inte
glider.

## Datamodellen

### Versionsgrafen

Ett begrepp är en stabil identitet; dess historik är en **riktad acyklisk graf
av oföränderliga versioner**. Redigering ändrar aldrig en version utan skapar
en ny, med en typad kant till föräldern: `revised_from` (linjär ändring),
`branched_from` (gren), `synthesized_from` (flera föräldrar → en, där
licensföljder spåras), `translated_from` (översättning av en bestämd
källversion – så modelleras tvåspråkighet) och `promoted_from` (en äldre
version görs gällande igen: ny version, bakåtreferens, historiken skrivs
aldrig om). Varje kant kan bära en not.

Logiken är medvetet smal: tillägg av versioner, uttrycklig grening, uttrycklig
syntes och flytt av huvudpekaren. Ingen generell trevägssammanslagning.
Oföränderlighet plus graf ger på köpet tidsresor, grenvisualisering, syntes
med flera föräldrar, fullständig revision och ett ångra som aldrig förstör
något.

### Stand-off-annotationer

Delar av en definition kan bära typade attribut som får överlappa fritt. Det
kräver att annotationerna lagras *bredvid* texten som teckenintervall – W3C
Web Annotation-modellens form. Eftersom versioner är oföränderliga behöver
annotationer aldrig förankras om inom en version; bara när de bärs vidare till
en ny version, och då flaggas osäkra fall för mänsklig granskning.

### Proveniens, kanon och låsning

- **Proveniens** på varje version: `human`, `import` eller `llm`, för modeller
  med modellnamn, leverantör och prompt.
- **Kanon är samexistens.** Flera attribuerade, fastställda definitioner av
  samma sak får finnas sida vid sida. Plattformens uppgift är att *visa
  attribuerad oenighet* väl, inte att utse vinnare mellan SUTI, Transmodel,
  NOPTIS eller nationella och europeiska linjer. Fastställd är därför inte en
  status på versionen utan en organisations återkallbara flagga på en viss
  version; ett återkallande är en ny spårbar händelse.
- **Låsning.** En låst samling ändras bara genom grenar och ändringsförslag,
  aldrig genom direkta skrivningar.

### Samtidighet

Två personer som redigerar samma begrepp samtidigt får varsin version eller
gren; den som sparar mot en föråldrad bas erbjuds att grena. Att jämka ihop är
ett medvetet mänskligt beslut: syntes eller att göra en version gällande.
Realtidssamskrivning av ett utkast finns som komplement, men besluten lever
som versioner.

## AI-principer

AI ligger som ett lager *ovanpå* modellen och bär aldrig upp vanlig användning.

- **Egen nyckel.** Användaren använder sin egen nyckel hos vald leverantör.
  Nyckeln lagras bara i webbläsaren och skickas med själva anropet, som
  proxas av servern utan att sparas eller loggas. Institutionella nycklar
  hör hemma i ett serverläge utan persistens, aldrig i webbläsaren.
- **Människan granskar alltid.** AI ger utkast; inget sparas utan att en
  människa sett, kunnat ändra och aktivt sparat. Allt som har sitt ursprung i
  en modell märks så i proveniensen.
- **Suveränitet i segment.** Offentliga aktörer med höga krav självhostar med
  lokal eller EU-hostad modell; forskning och konsultverksamhet kan använda
  egen nyckel; en publik demo klarar sig utan AI. All hostad drift är
  EU-baserad.
- **Avstängt tills det är klart.** AI-funktionerna styrs av en funktionsflagga
  och är avstängda i den hostade instansen under betan.

## Gränssnittsprinciper

- **Inga överlägg.** Ett begrepp eller en samling är en egen sida med egen
  adress och brödsmula; aldrig en modal.
- **Stegvis fördjupning.** Definition och det väsentliga först; historik,
  proveniens, relationer och annotationer ett medvetet steg djupare.
- **Historiken som film.** En dragbar tidslinje där ändringarna spelas upp
  längs texten; grenar och återställningar syns.
- **Jämförelsen är verkstaden** där kanon smids: fullständiga definitioner i
  kolumner, en utgångspunkt, ordagrann diff.
- **Tillgänglighet är ett arkitekturkrav.** All information som visas med
  rörelse eller drag finns också utan: tangentbordsstyrd tidslinje, statisk
  diff, versionstabell i klartext, tre teman med WCAG-kontrast, reducerad
  rörelse som förstaklassläge.

## Innehållsrättigheter

Kodlicensen är en sak, innehållets licens en annan – och innehållet är
produktens värde. Varje samling bär därför en uttrycklig, maskinläsbar
rättighetsbeskrivning: licens, om vidarespridning är tillåten, källa och
attribution. Samlingar utan vidarespridningsrätt är läsbara men inte
exporterbara. Syntes över samlingar med oförenliga licenser varnas för. Vad
som gäller för en viss samling står på dess sida.

## Teknik

FastAPI och SQLAlchemy på servern, SvelteKit på webben, SQLite som standard
med modellen förberedd för Postgres. Två containrar bakom en reverse proxy,
allt miljöspecifikt i miljövariabler, Docker Compose som leveransform för
självhostning. En publik MCP-server och ett dokumenterat REST-API är
förstaklassytor.

## Licens

Koden är GNU AGPL-3.0-or-later: plattformen är fri för sektorn att använda,
granska och driva själv, och den som erbjuder en ändrad version till andra
delar sina ändringar – så förblir det gemensamma gemensamt. Självhostning,
API- och MCP-integration är fria; det som kostar är organisationsbruk med
privata rum, drift och support. Innehållet har egna licenser per samling.

## Det som återstår

Inloggad MCP-åtkomst med personliga API-nycklar, AI-funktionerna i skarp drift,
ett serverläge för institutionella nycklar, kontinuerlig replikering av
databasen och Postgres i drift. Medvetet uppskjutet: fullständig
trevägssammanslagning bortom syntes, mobilappar och automatisk
standardkonformanskontroll.
