/* i18n-content */
/** The in-app manual (/help), per UI language. Content-by-language module:
 * `manual` is typed as Record<Lang, ManualContent> and every section body is
 * keyed by SectionId, so a missing language or a missing section is a
 * compile-time error.
 *
 * Section ids are URLs (anchors like /help#historiken) and are shared
 * between languages — NEVER translate or change them. Section `html` is
 * trusted static authored content rendered with {@html} in +page.svelte; it
 * may contain <p>, <ul>, <ol>, <h3>, <table>, <pre>, <code>, <kbd>, <a>,
 * <strong>, <em> and the .duo/.rule-of-thumb/.table-scroll building blocks. */
import type { Lang } from '$lib/i18n.svelte';

export const SECTION_IDS = [
  'komma-igang',
  'sok',
  'begrepp',
  'historiken',
  'redigera',
  'andringsforslag',
  'samlingar-listor',
  'jamforelseverkstaden',
  'export',
  'import',
  'ai',
  'diskussioner',
  'epost',
  'profil',
  'permalankar',
  'organisationer',
  'mcp',
  'tillganglighet',
  'administration'
] as const;

export type SectionId = (typeof SECTION_IDS)[number];

/** Who a section is for. The manual adapts to the signed-in role (since
 * 2026-08-13): sections about features a role cannot reach are hidden
 * from both the ToC and the page. 'all' = everyone, including anonymous
 * readers; 'user' = any signed-in account; 'super_admin' = super admins.
 * Conceptual onboarding (editing, proposals, orgs …) stays 'all' on purpose —
 * it is how readers learn why an account is worth having. */
export type SectionAudience = 'all' | 'user' | 'super_admin';

export const SECTION_AUDIENCE: Record<SectionId, SectionAudience> = {
  'komma-igang': 'all',
  sok: 'all',
  begrepp: 'all',
  historiken: 'all',
  redigera: 'all',
  andringsforslag: 'all',
  'samlingar-listor': 'all',
  jamforelseverkstaden: 'all',
  export: 'all',
  import: 'all',
  ai: 'all',
  diskussioner: 'all',
  epost: 'user',
  profil: 'user',
  permalankar: 'all',
  organisationer: 'all',
  mcp: 'all',
  tillganglighet: 'all',
  administration: 'super_admin'
};

export interface ManualSection {
  title: string;
  html: string;
}

export interface ManualContent {
  kicker: string;
  title: string;
  lede: string;
  tocTitle: string;
  sections: Record<SectionId, ManualSection>;
  foot: string;
}

export const manual: Record<Lang, ManualContent> = {
  sv: {
    kicker: 'Manual',
    title: 'Så använder du Kollepedia',
    lede: 'Från första sökningen till en fryst upphandlingsordlista. Att läsa kräver inget konto – och allt du behöver veta för att bidra ryms på den här sidan. Varje avsnitt har en egen länk, så du kan peka en kollega rakt in i rätt stycke.',
    tocTitle: 'Innehåll',
    sections: {
      'komma-igang': {
        title: 'Komma igång',
        html: `
        <p>
          Kollepedia är öppet att läsa. Du kan söka bland begreppen, bläddra i samlingarna,
          öppna vilket begrepp som helst och spela upp dess historia i historiken – utan
          konto, utan inloggning.
        </p>
        <p>
          Vill du bidra – redigera begrepp, skapa listor, lägga till relationer – behöver du
          ett konto: varje ändring blir en oföränderlig del av historiken och måste kunna
          tillskrivas en person. Klicka på <strong>Logga in</strong> i sidhuvudet och välj
          fliken <strong>Skapa konto</strong>. Du anger, i den ordningen:
        </p>
        <ul>
          <li><strong>Användarnamn</strong> – ditt offentliga @namn (gemener, siffror, bindestreck).</li>
          <li><strong>Visningsnamn</strong> – ditt författarnamn, som visas vid dina bidrag.</li>
          <li><strong>E-postadress</strong> – inloggningsidentitet; ett verifieringsbrev skickas,
            se <a href="#epost">E-post &amp; verifiering</a>.</li>
          <li><strong>Lösenord</strong> – minst 12 tecken.</li>
        </ul>
        <p>
          I bakgrunden körs en <em>robotkontroll</em> – helt utan tredjepartstjänster; inget
          lämnar webbplatsen. Registreringar som ser misstänkta ut kan flaggas för manuell
          granskning: kontot kan då läsa allt men inte bidra förrän en administratör godkänt
          det, och du får ett mejl när granskningen är klar. Du loggar in med e-postadressen
          eller användarnamnet.
        </p>
        <p>
          <em>Har ditt namn tidigare importerats som upphovsperson?</em> Då gör du anspråk
          på identiteten via din författarsida (aktiveringslänken leder till
          <code>/activate?handle=…</code>): användarnamnet visas skrivskyddat och kontot knyts
          till alla dina historiska bidrag.
        </p>
        <p>
          <em>Organisationer i korthet:</em> en organisation samlar kollegor kring gemensamma
          samlingar, med rollerna läsare, redaktör och admin. Mer i avsnittet
          <a href="#organisationer">Organisationer &amp; behörigheter</a>.
        </p>
        <p>
          I sidhuvudet finns också temaknappen <strong>Byt tema</strong> (ljust, mörkt,
          högkontrast), <strong>aktivitetsklockan</strong> som leder till dina bevakade
          begrepps händelser (utgråad tills du loggat in) och språkväxlaren SV/EN.
        </p>`
      },
      sok: {
        title: 'Sök',
        html: `
        <p>
          Sökfältet på startsidan söker fritext över begreppens <em>benämningar och
          definitioner</em>, i alla samlingar du har tillgång till. Resultaten visar vilken
          samling träffen kommer från och vilken status versionen har. Vill du söka inom en
          enda samling: öppna samlingen och använd dess eget fält
          <strong>Sök i samlingen …</strong>
        </p>
        <p>
          Under sökfältet finns filterpanelen: <strong>Fler filter</strong> fäller ut
          filter för språk, kategorier, taggar, samlingar och status – samma knapp heter
          <strong>Dölj filter</strong> när panelen är öppen, och räknebadgen intill visar
          hur många filter som är aktiva även när panelen är stängd. Aktiva filter visas
          som borttagbara pluppar under fältet, och <strong>Rensa filter</strong>
          nollställer alltihop.
        </p>
        <p>
          Definitioner kan innehålla korsreferenser skrivna som [[dubbla hakparenteser]] –
          klickar du på en sådan öppnas en sökning på det begreppet.
        </p>`
      },
      begrepp: {
        title: 'Begrepp & versioner',
        html: `
        <p>
          Ett <em>begrepp</em> är en varaktig identitet – ”hållplats” som idé. Det du läser på
          en begreppssida är alltid en viss <em>version</em> av begreppet: en oföränderlig
          ögonblicksbild av benämning, definition, status och etiketter.
        </p>
        <p>
          <strong>Ingenting skrivs någonsin över.</strong> Varje ändring blir en ny version
          som läggs till historiken, ungefär som en commit i git. Därför kan Kollepedia
          alltid visa exakt vem som skrev vad, när – och varför.
        </p>
        <p>
          <em>Varför</em>-frågan besvaras av <strong>noten</strong>: den motivering som varje
          version bär med sig. Den är obligatorisk när du redigerar och visas i
          proveniens-kortet på begreppssidan och i historiken. Tänk på den som versionens
          commit-meddelande.
        </p>
        <p>
          Varje version har en <strong>status</strong> som följer livscykeln
          <em>utkast → föreslagen → utfasad/ersatt</em>. <em>Fastställd</em> är ingen
          status utan en uttrycklig, attribuerad stämpel som en organisation sätter på en
          viss version (visas som ★ <em>Fastställd av …</em>). Stämpeln kan återkallas – men även
          återkallandet är en spårbar händelse; historiken skrivs aldrig om. Flera
          fastställda definitioner av samma sak kan samexistera: Kollepedia visar attribuerad
          oenighet i stället för att utse vinnare.
        </p>
        <p>
          Varje version bär också <strong>proveniens</strong>: om den skapades av en
          människa, av en AI (märks <em>AI-genererad</em> med modellnamn) eller genom import
          (märks <em>Importerad från …</em>).
        </p>
        <p>
          Begrepp kan knytas ihop med typade <strong>relationer</strong> – relaterat begrepp,
          överordnat/underordnat, exakt/nära motsvarighet, ersätter – var och en med en
          valfri anteckning om varför de hör ihop. Översättningar är en egen sak: de knyter
          versioner mellan språk och listas under <em>Översättningar</em> på begreppssidan.
        </p>`
      },
      historiken: {
        title: 'Historik',
        html: `
        <p>
          Öppna <strong>Öppna historiken</strong> på en begreppssida för att se begreppets
          hela historia spelas upp som en film: text som tas bort får en röd ton och
          kollapsar, ny text skrivs in på grön botten. Rubriken hinner alltid landa före
          definitionen.
        </p>
        <ul>
          <li>
            <strong>Spela, pausa, skrubba.</strong> Playknappen (<em>Spela upp
            historiken</em>) startar och pausar. Dra spelhuvudet på tidslinjen till valfritt
            ögonblick – även mitt i en övergång. Versionspunkterna sitter proportionellt mot
            verklig tid, med årtal som skala. Knappen <strong>×</strong>-hastighet ändrar
            uppspelningstempot.
          </li>
          <li>
            <strong>Kapitelpilar.</strong> <em>Föregående version</em> och
            <em>Nästa version</em> hoppar version för version, som kapitelmarkörer.
          </li>
          <li>
            <strong>Grenval.</strong> Där historiken förgrenar sig visas en liten grensymbol
            på tidslinjen. Klicka på den och välj under <em>Följ historiken längs…</em> om
            uppspelningen ska följa huvudlinjen (main) eller en namngiven gren – tidslinjen
            ritas om efter valet.
          </li>
          <li>
            <strong>Ordning.</strong> Knappen <strong>Ordning</strong> växlar mellan
            <em>längs texten</em> (ändringarna spelas upp i läsordning, som om någon
            redigerade från start till slut) och <em>samtidigt</em> (allt rött markeras
            först, sedan skrivs allt grönt).
          </li>
          <li>
            <strong>Bläck-läge.</strong> Tonar texten efter ålder: ord skrivna i den visade
            versionen står i fullt bläck, äldre lager bleknar stegvis mot sepia – textens
            geologi i en blick. En legend förklarar skalan. Bläck-läget kräver att
            uppspelningen står stilla; det snäpper automatiskt till närmaste version.
          </li>
          <li>
            <strong>Hovra för upphovsperson.</strong> När uppspelningen vilar kan du hålla
            muspekaren över vilket ord som helst: allt som skrevs i samma version markeras,
            och ett kort visar vem som skrev det, när, och versionens not.
          </li>
          <li>
            <strong>Statisk vy.</strong> Knappen <strong>Statisk vy</strong> stänger av all
            rörelse och visar i stället en kombinerad diff med lägena
            <strong>Före</strong> / <strong>Ändringar</strong> / <strong>Efter</strong>.
            Under scenen finns dessutom <em>Versionslistan</em> – en vanlig tabell med datum,
            författare, status, ändringstyp och not för varje version. Se
            <a href="#tillganglighet">Tillgänglighet</a>.
          </li>
        </ul>
        <p>
          Panelen till höger visar alltid den fokuserade versionens upphovsperson, datum,
          ändringstyp (revidering, gren, syntes, översättning eller återställd version),
          proveniens och not. Där finns också knappen
          <strong>Gör till gällande version</strong> – se
          <a href="#redigera">Redigera</a>.
        </p>`
      },
      redigera: {
        title: 'Redigera',
        html: `
        <p>
          Redigering kräver ett konto (<a href="#komma-igang">Komma igång</a>). Utan
          inloggning är knapparna avstängda med hänvisningen <em>Logga in för att kunna
          redigera</em>.
        </p>
        <ol>
          <li>Öppna begreppet och klicka på <strong>Redigera</strong>.</li>
          <li>
            Panelen <em>Redigera – skapar en ny version</em> öppnas. Ändra benämning,
            definition (Markdown-lätt: **fet**, *kursiv* och [[korsreferenser]]),
            etiketter och status.
          </li>
          <li>
            Skriv en <strong>Motivering</strong> – den är obligatorisk. <em>Varför görs
            ändringen?</em> Motiveringen följer med versionen för alltid.
          </li>
          <li>
            Klicka på <strong>Spara ny version</strong>. Inget skrivs över: din ändring blir
            en ny version på huvudlinjen, tillskriven ditt konto.
          </li>
        </ol>
        <p>
          <strong>Grenar.</strong> Vill du utforska en alternativ formulering utan att röra
          huvudlinjen: välj <strong>Skapa gren</strong> i redigeringspanelen och ge grenen
          ett namn. Grenen blir en egen linje i historiken, synlig i historikens grenval –
          och kan senare skickas till granskning som ett
          <a href="#andringsforslag">ändringsförslag</a>.
        </p>
        <p>
          <strong>Om någon annan hunnit före (konflikt).</strong> Två personer kan redigera
          samma begrepp samtidigt. Sparar du mot en version som inte längre är den senaste
          svarar Kollepedia inte med att skriva över någonting – du möts av beskedet
          <em>”Någon annan har hunnit före”</em> och erbjuds att skapa en gren i stället.
          Det är modellen <em>gren och förena</em>: båda ändringarna bevaras som varsin
          linje, och sammanjämkningen är ett medvetet mänskligt beslut – antingen genom en
          syntes i <a href="#jamforelseverkstaden">Jämför begrepp</a> eller genom att
          en av versionerna görs gällande. Vill du hellre skriva om din ändring utifrån den
          nya versionen väljer du <strong>Tillbaka till redigeringen</strong>.
        </p>
        <p>
          <strong>Återställa en äldre version.</strong> Öppna historiken, ställ dig på den
          version du vill ha tillbaka och klicka på
          <strong>Gör till gällande version</strong>. En ny version skapas med samma
          innehåll och en bakåtreferens till originalet – huvudet flyttas, men historien
          skrivs aldrig om. Ångra är alltså aldrig destruktivt.
        </p>
        <p>
          <strong>Nytt begrepp</strong> skapar du via <strong>+ Nytt begrepp</strong> på en
          samlingssida (eller <strong>+ Nytt begrepp i samlingen</strong> från en
          begreppssida). Begreppet får en första version på huvudlinjen; varje senare
          ändring blir en ny version.
        </p>`
      },
      andringsforslag: {
        title: 'Ändringsförslag',
        html: `
        <p>
          Ett <em>ändringsförslag</em> är Kollepedias motsvarighet till en pull request: en
          gren skickas till granskning för att förenas med huvudlinjen. Det är den ordnade
          vägen att föreslå ändringar i begrepp du inte förvaltar själv – och den enda vägen
          in i låsta samlingar.
        </p>
        <ol>
          <li>
            Skapa en <strong>gren</strong> med din formulering
            (<a href="#redigera">Redigera</a>).
          </li>
          <li>
            På begreppssidan, under <em>Ändringsförslag</em>: välj
            <strong>Föreslå ändring från gren …</strong>, ge förslaget en
            <strong>Titel</strong> och en beskrivning, och klicka
            <strong>Skicka ändringsförslag</strong>. En gren kan bara ha ett öppet förslag
            åt gången.
          </li>
          <li>
            Granskaren öppnar förslaget – via begreppssidan eller samlingssidan för alla
            förslag på <code>/proposals</code> – och ser en diff <em>före/efter</em> mot
            gällande version.
          </li>
          <li>
            Avgörandet är uttryckligt och motiverat: <strong>Sammanfoga</strong> skapar en
            ny version på huvudlinjen med grenens innehåll (har huvudlinjen hunnit vidare
            blir det en syntes med båda som föräldrar); <strong>Avvisa</strong> stänger
            förslaget med motivering. Förslagsställaren kan själv välja
            <strong>Dra tillbaka</strong>.
          </li>
        </ol>
        <p>
          <strong>Låsta samlingar.</strong> I en låst samling är vanliga skrivningar
          blockerade för alla utom samlingens administratörer – men att skapa
          <em>grenar</em> är tillåtet för alla inloggade. Det är avsiktligt:
          låst innehåll utvecklas genom grenar och ändringsförslag, aldrig genom direkta
          ändringar. Rättigheten att sammanfoga eller avvisa ligger hos den som förvaltar
          samlingen (samlingsbehörighet, ägarorganisationens admin eller superadmin).
        </p>
        <p>
          Som allt annat är avgöranden spårbara: ett sammanfogat eller avvisat förslag
          behåller sin motivering, sin diskussion och sin historik.
        </p>`
      },
      'samlingar-listor': {
        title: 'Samlingar & listor',
        html: `
        <p>
          Det här är den viktigaste distinktionen i hela Kollepedia. Får du med dig den,
          faller resten på plats.
        </p>

        <div class="duo ui">
          <div class="duo-card">
            <h3>Samling</h3>
            <p class="duo-tag">Där begrepp lever och utvecklas.</p>
            <p>
              En samling är ett vokabulär – en hylla i biblioteket. Transmodel,
              Kollektivtrafikordboken, er interna begreppslista. Här <em>bor</em> begreppen:
              de har sin historik här, får nya versioner här, fastställs här. Varje begrepp
              har exakt ett hem – sin samling.
            </p>
          </div>
          <div class="duo-card">
            <h3>Lista</h3>
            <p class="duo-tag">Det du samlat, för ett syfte.</p>
            <p>
              En lista är din urvalslåda – det du plockat från hyllorna för ett bestämt
              ändamål: en upphandling, ett projekt, en ordlista till en rapport. Listan
              <em>äger inga begrepp</em>; den pekar på dem. Och den pekar inte löst på
              ”begreppet”, utan <em>fäster exakta versioner</em>.
            </p>
          </div>
        </div>

        <p>
          Därför lägger du aldrig en upphandlings termer <em>in i</em> Transmodel. Du bygger
          en <em>lista</em> som refererar precis de Transmodel-versioner du behöver – fästa,
          så att de inte kan glida i väg när samlingen fortsätter utvecklas.
        </p>

        <h3>Samlingsöversikten</h3>
        <p>
          Sidan <strong>Samlingar</strong> är grupperad efter närhet: inloggad ser du
          <em>Mina samlingar</em>, sedan <em>Organisationssamlingar</em> och sist
          <em>Publika samlingar</em>; utan konto visas bara de publika. Varje kort visar
          samlingens nyckelfakta – år, antal begrepp, licens, synlighet,
          redigeringspolicy – och ett ifyllt hänglås intill namnet betyder att samlingen
          är skrivskyddad.
        </p>
        <p>
          Egna samlingar är alltid <em>privata</em> – bara du ser dem. Kortets
          <strong>Dela</strong>-knapp leder till en sida som förklarar vägen till delat
          innehåll: skapa eller gå med i en organisation och flytta samlingen dit.
        </p>

        <h3>Samlingssidans verktygsrad</h3>
        <p>
          På en samlings sida, under metainformationen, ligger verktygsraden med
          <strong>Skrivskydda</strong> (respektive <strong>Lås upp</strong>),
          <strong>Redigera</strong>, <strong>Exportera</strong> och
          <strong>Importera</strong> – knapparna visas utifrån dina behörigheter. Mer om
          skrivskydd i <a href="#organisationer">Organisationer &amp; behörigheter</a>,
          om formaten i <a href="#export">Export</a> och <a href="#import">Import</a>.
        </p>

        <h3>Exempel: upphandlingen</h3>
        <ol>
          <li>
            Gå till <strong>Listor</strong> i sidhuvudet och klicka på
            <strong>+ Ny lista</strong>. Namnge den, t.ex. <em>Upphandling stadsbuss
            2027</em>, och ange gärna syftet.
          </li>
          <li>
            Sök upp de begrepp upphandlingen behöver. Öppna varje begrepp och klicka på
            <strong>⚲ Lägg i lista</strong>. Välj listan och alternativet
            <strong>Fäst denna version</strong> – <em>fryst, ändras inte när begreppet
            uppdateras</em>.
          </li>
          <li>
            Osäker på vilken definition som är rätt? Öppna listan och klicka på
            <strong>Jämför begreppen</strong> för att se kandidaterna sida vid sida i
            <a href="#jamforelseverkstaden">Jämför begrepp</a>.
          </li>
          <li>
            När urvalet är klart: exportera listan som fryst ordlista
            (<a href="#export">Export</a>) och bilagera den i förfrågningsunderlaget.
          </li>
        </ol>
        <p>
          Poängen: när Transmodel-samlingen får nya versioner nästa år betyder din bilaga
          <em>fortfarande exakt det den betydde när anbuden lämnades</em>. Kolumnen
          <em>Version</em> i listan visar för varje rad om den är
          <em>fäst vid version …</em> eller <em>följer senaste</em>.
        </p>

        <h3>Följ senaste – ett aktivt val</h3>
        <p>
          Att fästa är standard. Vill du i stället att en rad i listan alltid ska visa
          begreppets senaste version – till exempel i ett levande projektglossar – väljer du
          <strong>Följ senaste</strong> när du lägger till begreppet
          (<em>uppdateras när begreppet får en ny version</em>). Det är medvetet ett
          opt-in: en lista som glider utan att du bett om det är farligare än en som står
          stilla.
        </p>

        <p class="rule-of-thumb">
          <strong>Tumregel:</strong> Är det en definition som ska förvaltas och utvecklas?
          → samling. Är det ett urval för ditt syfte? → lista.
        </p>`
      },
      jamforelseverkstaden: {
        title: 'Jämför begrepp',
        html: `
        <p>
          Jämför begrepp ställer konkurrerande definitioner sida vid sida – <em>se vad
          som skiljer, och smid en gemensam</em>. Du når den via
          <strong>Jämför begreppen</strong> på en lista, eller direkt på adressen
          <code>/compare</code>.
        </p>
        <ul>
          <li>
            <strong>Kolumner.</strong> Varje begrepp är en kolumn med benämning, samling,
            status, etiketter, definition och upphovsperson. Lägg till fler via sökfältet
            <strong>Lägg till begrepp …</strong>; ta bort en kolumn med
            <strong>×</strong>-knappen i dess hörn.
          </li>
          <li>
            <strong>Utgångspunkt.</strong> En kolumn är alltid <em>utgångspunkt</em>
            (markeras med radioknappen i kolumnhuvudet). Den är måttstocken: alla skillnader
            räknas mot den, och den blir basen när du harmoniserar.
          </li>
          <li>
            <strong>Diff-läge.</strong> Slå på <strong>Diff-läge</strong> i verktygsraden så
            markeras ordagrant vad som skiljer: rött genomstruket finns
            <em>endast i utgångspunkten</em>, grönt <em>endast i denna kolumn</em>.
          </li>
          <li>
            <strong>Dela med en länk.</strong> Hela jämförelsen ligger i adressfältet
            (<code>/compare?ids=…</code>) – kopiera URL:en och skicka till en kollega, så
            ser hen exakt samma uppställning.
          </li>
          <!--ai--><li>
            <strong>✦ Harmonisera</strong> skapar ett AI-utkast som sammanför kolumnernas
            definitioner – se <a href="#ai">AI-funktioner</a>.
          </li><!--/ai-->
        </ul>`
      },
      export: {
        title: 'Export',
        html: `
        <p>
          Under <strong>Exportera</strong> på en listas sida finns knappar för fem format.
          På en samlings sida öppnar <strong>Exportera</strong> i verktygsraden en meny
          med samma format. Välj efter mottagare:
        </p>
        <ul>
          <li>
            <strong>CSV</strong> – kalkylblad och vidare bearbetning; öppnas direkt i Excel.
          </li>
          <li>
            <strong>Markdown</strong> – läsbar text för dokument, bilagor och wikis; det
            naturliga valet för upphandlingsbilagan.
          </li>
          <li>
            <strong>JSON-LD</strong> – länkade data för systemintegration och utvecklare.
          </li>
          <li>
            <strong>SKOS</strong> – (Turtle) för vokabulärverktyg och den semantiska
            webben; begrepp, definitioner och relationer följer med.
          </li>
          <li>
            <strong>TBX</strong> – terminologistandarden ISO 30042, för
            terminologihanterings- och översättningsverktyg; språkpar följer med där
            översättningslänkar finns.
          </li>
        </ul>
        <p>
          <strong>Fästa versioner gör exporten frusen.</strong> En lista exporterar exakt de
          versioner den fäst – <em>den frysta ordlistan överlever senare ändringar i
          samlingarna</em>. Rader som i stället följer senaste exporterar den version som är
          gällande i exportögonblicket.
        </p>`
      },
      import: {
        title: 'Import',
        html: `
        <p>
          Import sker per samling och tar emot CSV- eller Excel-filer (.xlsx, första
          bladet); du når importvyn via <strong>Importera</strong> i samlingssidans
          verktygsrad. Börja alltid med att hämta <em>mallen</em> från samlingens importvy – den
          innehåller rubrikraden och en exempelrad. Kolumnrubrikerna måste stavas exakt så
          här:
        </p>

        <div class="table-scroll">
          <table class="ui">
            <thead>
              <tr>
                <th scope="col">Kolumn</th>
                <th scope="col">Obligatorisk</th>
                <th scope="col">Format &amp; betydelse</th>
                <th scope="col">Exempel</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>canonical_form</code></td>
                <td>ja</td>
                <td>Begreppets benämning</td>
                <td>anropsstyrd trafik</td>
              </tr>
              <tr>
                <td><code>language</code></td>
                <td>nej</td>
                <td><code>sv</code> eller <code>en</code> (standard: <code>sv</code>)</td>
                <td>sv</td>
              </tr>
              <tr>
                <td><code>definition</code></td>
                <td>ja</td>
                <td>Definitionstexten</td>
                <td>Kollektivtrafik som körs efter beställning …</td>
              </tr>
              <tr>
                <td><code>status</code></td>
                <td>nej</td>
                <td>utkast, föreslagen, utfasad, ersatt – eller API-värdena draft, proposed,
                  deprecated, superseded (fastställd/endorsed tolkas som föreslagen; fastställande
                  görs i appen)</td>
                <td>utkast</td>
              </tr>
              <tr>
                <td><code>tags</code></td>
                <td>nej</td>
                <td>Etiketter, separerade med <code>;</code></td>
                <td>drift;planering</td>
              </tr>
              <tr>
                <td><code>categories</code></td>
                <td>nej</td>
                <td>Globala kategorier, separerade med <code>;</code> – namn (svenskt
                  eller engelskt) ur den globala vokabulären; okända namn ger radfel</td>
                <td>Drift;Urban mobilitet</td>
              </tr>
              <tr>
                <td><code>part</code></td>
                <td>nej</td>
                <td>Del i samlingens part-taxonomi (kräver att samlingen har en);
                  okänt namn ger radfel</td>
                <td>Fare Management</td>
              </tr>
              <tr>
                <td><code>note</code></td>
                <td>nej</td>
                <td>Motivering – versionens not</td>
                <td>Ur ordlistan 2024, kap. 3</td>
              </tr>
              <tr>
                <td><code>author</code></td>
                <td>nej</td>
                <td>Upphovsperson</td>
                <td>Anna Andersson</td>
              </tr>
              <tr>
                <td><code>author_affiliation</code></td>
                <td>nej</td>
                <td>Upphovspersonens organisation</td>
                <td>K2</td>
              </tr>
              <tr>
                <td><code>variants</code></td>
                <td>nej</td>
                <td>Varianter (böjningar, förkortningar, synonymer), separerade med
                  <code>;</code></td>
                <td>anropstrafik;flextrafik</td>
              </tr>
              <tr>
                <td><code>related_to</code></td>
                <td>nej</td>
                <td>Benämningar på relaterade begrepp, separerade med <code>;</code></td>
                <td>hållplats;linje</td>
              </tr>
              <tr>
                <td><code>broader</code></td>
                <td>nej</td>
                <td>Benämning på överordnat begrepp</td>
                <td>kollektivtrafik</td>
              </tr>
              <tr>
                <td><code>narrower</code></td>
                <td>nej</td>
                <td>Benämning på underordnat begrepp</td>
                <td>flextur</td>
              </tr>
              <tr>
                <td><code>exact_match</code></td>
                <td>nej</td>
                <td>Benämning på exakt motsvarighet</td>
                <td>demand-responsive transport</td>
              </tr>
              <tr>
                <td><code>translation_of</code></td>
                <td>nej</td>
                <td>Benämningen på samma begrepp på det andra språket (en rad i samma fil,
                  eller ett befintligt begrepp i samlingen)</td>
                <td>demand-responsive transport</td>
              </tr>
              <tr>
                <td><code>source</code></td>
                <td>nej</td>
                <td>Fri källhänvisning</td>
                <td>Ordbok för framtidens resande, 2024</td>
              </tr>
            </tbody>
          </table>
        </div>

        <p>
          Relationer och översättningar löses upp i två steg: först mot rader i samma fil,
          sedan mot begrepp som redan finns i samlingen. Upphovspersoner i
          <code>author</code>-kolumnen blir användare i systemet – de kan senare göra
          anspråk på sin identitet genom att registrera sig med samma namn. Varje importerad
          version får proveniensen <em>import</em>, med filnamn och radnummer.
        </p>
        <p>
          <strong>Torrkörning först.</strong> Kör alltid importen som torrkörning innan du
          importerar skarpt: hela filen valideras – antal rader, vad som skulle skapas, fel
          och varningar med radnummer – men <em>ingenting skrivs</em>. När rapporten är ren
          kör du samma import på riktigt.
        </p>
        <!--ai--><p>
          <strong>Ostrukturerad text via AI.</strong> Har du en ordlista som bara finns som
          löpande text – en PDF, ett gammalt Word-dokument? Klistra in texten så föreslår
          AI:n (med din egen nyckel, se <a href="#ai">AI-funktioner</a>) färdiga importrader
          i samma kolumnformat. Förslagen är alltid utkast för din granskning och går genom
          samma torrkörning – ingenting importeras automatiskt.
        </p><!--/ai-->`
      },
      ai: {
        title: 'AI-funktioner',
        html: `
        <p>
          All AI i Kollepedia är <em>bring your own key</em>: du använder din egen nyckel
          hos en leverantör du själv väljer, och plattformen bär ingen tokenkostnad.
          Kollepedia är dessutom fullt användbart helt utan AI.
        </p>

        <h3>AI-leverantörer</h3>
        <p>
          Klicka på <strong>AI-inställningar</strong> i Jämför begrepp-sidans verktygsrad
          (eller i importvyns AI-flik). Där väljer du <strong>Leverantör</strong>:
        </p>
        <ul>
          <li>
            <strong>Anthropic</strong> – standardvalet; nyckel <code>sk-ant-…</code>,
            standardmodell <code>claude-sonnet-5</code>.
          </li>
          <li>
            <strong>Berget.ai (OpenAI-kompatibel)</strong> – svensk leverantör med drift i
            svenskt datacenter, ett bra val när data inte ska lämna EU. Standardmodell
            <code>meta-llama/Llama-3.3-70B-Instruct</code>; kolla Bergets modellkatalog och
            skriv modellnamnet i <strong>Modell</strong>-fältet – det skickas som
            <code>model</code> i anropet.
          </li>
          <li>
            <strong>OpenAI-kompatibel (egen bas-URL)</strong> – valfri tjänst som talar
            OpenAI:s chat-completions-format: ange <strong>Bas-URL</strong>
            (t.ex. <code>https://api.openai.com/v1</code> eller din egen gateway) och
            modell (standard <code>gpt-4o-mini</code>).
          </li>
        </ul>
        <p>
          <strong>Nyckeln</strong> klistras in i samma dialog och du väljer
          <strong>Spara</strong>. Nyckel, leverantör och modell lagras <em>endast i din
          webbläsare</em>; nyckeln skickas aldrig till Kollepedias server annat än vid
          själva anropet, som proxas utan att sparas eller loggas. <strong>Rensa</strong>
          tar bort alltihop när du vill. Modellfältets platshållare visar leverantörens
          standardmodell – lämnar du fältet tomt används den.
        </p>

        <h3>Promptmallar</h3>
        <p>
          Vägledningar du använder ofta – <em>”Prioritera Transmodels terminologi, håll
          definitionen under 50 ord”</em> – kan sparas som mallar. Skriv vägledningen i
          harmoniseringspanelen och klicka <strong>Spara som mall …</strong>; ge mallen ett
          namn och bocka i <em>Delad</em> om kollegor ska se den. Nästa gång väljer du den i
          <strong>Mall</strong>-listan. När ett utkast skapas med en mall vald följer
          mallens id med i versionens proveniens – prompter är förstaklassmedborgare, inte
          löst skräp.
        </p>
        <p>
          <strong>Harmonisera-flödet.</strong> Med minst två begrepp laddade i
          Jämför begrepp och nyckeln på plats tänds <strong>✦ Harmonisera</strong>:
        </p>
        <ol>
          <li>
            Välj vilken kolumn som ska vara <em>utgångspunkt</em> – den blir basen för
            syntesen.
          </li>
          <li>
            Skriv eventuellt en vägledning till modellen (t.ex. <em>”Prioritera Transmodels
            terminologi, håll definitionen under 50 ord”</em>) och klicka på
            <strong>Skapa AI-utkast</strong>.
          </li>
          <li>
            Granska och redigera utkastets term, definition och anteckning – utkastet är
            just ett utkast, och du är redaktören.
          </li>
          <li>
            <strong>Spara som syntes till ”…”</strong> skriver en ny version med status
            <em>utkast</em> på utgångspunktens begrepp, med alla jämförda versioner som
            föräldrar. I historiken syns den som <em>Syntes av flera versioner</em>.
          </li>
        </ol>
        <p>
          <strong>Människan granskar alltid.</strong> Inget AI-utkast sparas utan att du
          sett, kunnat redigera och aktivt sparat det. Och allt som har sitt ursprung i en
          modell märks så i proveniensen – <em>AI-genererad</em>, med modellnamn – synligt på
          begreppssidan, i historiken och i versionslistan.
        </p>`
      },
      diskussioner: {
        title: 'Diskussioner, bevakning & aktivitet',
        html: `
        <p>
          <strong>Diskussion.</strong> Varje begreppssida och varje ändringsförslag har en
          diskussionstråd. Skriv ett inlägg och klicka <strong>Publicera</strong> – frågor,
          källor, invändningar; det som inte hör hemma i själva definitionen men behövs för
          att komma överens. Inlägg är attribuerade och kan bara tas bort av författaren
          själv (eller superadmin). Diskussionen är samtalet <em>bredvid</em> historiken –
          själva besluten lever som versioner och förslag.
        </p>
        <p>
          <strong>Bevaka.</strong> Knappen <strong>Bevaka</strong> på begreppssidan följer
          begreppet åt dig; den växlar till <em>Bevakar</em>. Bevakningen kräver konto.
        </p>
        <p>
          <strong>Aktivitet.</strong> Sidan <a href="/activity">Aktivitet</a> samlar
          händelserna i dina bevakade begrepp – nya versioner, fastställanden, inlägg och
          ändringsförslag – nyast först, med länkar rakt in i begreppen. Varje begreppssida
          har dessutom sitt eget aktivitetsflöde med samma händelsetyper.
        </p>`
      },
      epost: {
        title: 'E-post & verifiering',
        html: `
        <p>
          Konton skapas med e-postadress, och adressen används för verifiering och
          återställningslänkar. En adress räknas som <em>verifierad</em> först när du
          klickat på länken i verifieringsbrevet (<code>/verify-email?token=…</code>).
          Byter du adress – på <a href="#profil">profilsidan</a> – skickas ett nytt brev
          och adressen måste verifieras igen.
        </p>
        <p>
          <strong>Glömt lösenord.</strong> Länken <strong>Glömt lösenord?</strong> på
          inloggningsfliken leder till ett formulär där du anger e-postadress eller
          användarnamn. Svaret är alltid neutralt (ingen kontouppräkning); en återställningslänk
          skickas bara om kontot har en verifierad adress. Administratörer kan dessutom
          alltid skapa en återställningslänk manuellt via användarhanteringen.
        </p>
        <p>
          <strong>Utkorgen och tillåtelselistan.</strong> På kollepedia.se skickas breven
          från <code>no-reply@kollepedia.se</code>; dyker brevet inte upp inom några minuter,
          titta i skräpposten. Varje brev som systemet skapar bokförs också i utkorgen på
          <code>/admin/outbox</code> (endast superadmin). I en installation utan
          mejlrelä stannar breven där, och en <em>tillåtelselista</em> i servern avgör vilka
          adresser som får ta emot post – brev till andra mottagare markeras
          <em>blockerad</em> och sparas för inspektion i stället för att skickas.
        </p>`
      },
      profil: {
        title: 'Profil',
        html: `
        <p>
          <strong>Min profil</strong> i kontomenyn (sidhuvudet) är ditt kontos hem. Där
          ser du användarnamn, visningsnamn, affiliering och organisation, med länk till din
          publika författarsida – den som visar dina bidrag för alla andra.
        </p>
        <ul>
          <li>
            <strong>E-post.</strong> Ange eller byt e-postadress; adressen visas med sin
            verifieringsstatus (<em>verifierad</em> / <em>ej verifierad</em>). Varje
            ändring utlöser ett nytt verifieringsbrev – se
            <a href="#epost">E-post &amp; verifiering</a>.
          </li>
          <li>
            <strong>Byt lösenord.</strong> Ange nuvarande och nytt lösenord (minst 12
            tecken). Bytet gäller direkt vid nästa inloggning.
          </li>
        </ul>`
      },
      permalankar: {
        title: 'Permalänkar & citering',
        html: `
        <p>
          Eftersom versioner är oföränderliga kan de citeras med gott samvete. Varje
          version har en permanent adress – <code>/versions/&lt;id&gt;</code> – som visar
          exakt den frusna versionen, oavsett hur begreppet utvecklas efteråt. Du når den
          från historikens versionslista.
        </p>
        <p>
          Sidan visar en banner om att versionen aldrig ändras, en not om huruvida den
          fortfarande är begreppets gällande version, och en <strong>Citera</strong>-ruta
          med två kopierbara fält: den permanenta adressen och en färdig källhänvisning
          (benämning, samling, version, datum, URL) – klar att klistra in i rapporten
          eller förfrågningsunderlaget. Länkar tillbaka till begreppet och dess
          historik finns intill.
        </p>`
      },
      organisationer: {
        title: 'Organisationer & behörigheter',
        html: `
        <p>
          En organisation samlar kollegor kring gemensamma samlingar. Du skapar en
          organisation (namn och kortnamn) inloggad med konto; du blir själv dess admin. Nya
          organisationer godkänns av en superadministratör innan de tas i full drift.
        </p>
        <p>Medlemmar läggs till med sitt användarnamn och får en av tre roller:</p>
        <ul>
          <li>
            <strong>Läsare</strong> – ser organisationens privata innehåll.
          </li>
          <li>
            <strong>Redaktör</strong> – skapar och redigerar begrepp i organisationens
            samlingar.
          </li>
          <li>
            <strong>Admin</strong> – allt ovan, plus hanterar medlemmar, roller och
            samlingarnas inställningar.
          </li>
        </ul>
        <p>
          <strong>Synlighet.</strong> En samling är <em>publik</em> (läsbar för alla,
          även utan konto), <em>org-privat</em> (syns bara för organisationens medlemmar
          – det gäller överallt: sök, begreppssidor, jämförelser och export) eller
          <em>privat</em> (en personlig samling som bara skaparen ser). Att skriva i en
          organisationsägd samling kräver rollen redaktör eller admin; en privat samling
          redigeras bara av sin skapare. De publika samlingarna utan ägarorganisation –
          systemsamlingarna, som Transmodel – förvaltas av superadministratören och är
          skrivskyddade: alla andra bidrar via grenar och
          <a href="#andringsforslag">ändringsförslag</a>.
        </p>
        <p>
          <strong>Lås &amp; arkiv.</strong> Den som förvaltar en samling kan
          <strong>låsa</strong> den – knappen heter <strong>Skrivskydda</strong> i
          samlingssidans verktygsrad, och <strong>Lås upp</strong> häver låset. Vanliga
          skrivningar blockeras då för alla utom
          samlingens administratörer, men grenar – och därmed
          <a href="#andringsforslag">ändringsförslag</a> – förblir öppna. Att
          <strong>arkivera</strong> går längre: samlingen döljs i samlingslistan, får en
          <em>Arkiverad</em>-banner och blockerar alla skrivningar tills den avarkiveras.
          Inget av besluten raderar någonting.
        </p>
        <p>
          Superadministratören förvaltar helheten: godkänner organisationer, utser
          auktoritativa samlingar, hanterar användare (<code>/admin/users</code>) och
          inspekterar e-postutkorgen (<code>/admin/outbox</code>). I en egen installation
          blir den först registrerade användaren superadmin.
        </p>`
      },
      mcp: {
        title: 'För utvecklare & agenter',
        html: `
        <p>
          Kollepedia är byggt för att även maskiner ska kunna arbeta med begreppen – med
          samma spårbarhet som människor.
        </p>
        <p>
          <strong>MCP-servern</strong> låter AI-agenter (t.ex. Claude) läsa och söka i
          begreppen via Model Context Protocol. Den publika ändpunkten
          <code>https://kollepedia.se/mcp</code> kräver inget konto och ser samma innehåll
          som en anonym besökare. Verktygen är <code>list_collections</code>,
          <code>get_collection</code>, <code>search_concepts</code>,
          <code>get_concept</code> och <code>get_concept_history</code>; samlingar utan
          vidarespridningsrätt är sökbara men märks som icke exporterbara. Inloggad
          åtkomst med skrivningar kommer i ett senare steg. Registrera servern:
        </p>
        <pre class="ui" tabindex="0" role="region" aria-label="Kommandorad för MCP-registrering"><code>claude mcp add --transport http kollepedia https://kollepedia.se/mcp</code></pre>
        <p>
          <strong>REST-API:t</strong> ligger under <code>/api/v1</code>: läsning är öppen
          (publika samlingar), skrivning kräver identitet – Bearer-token från
          <code>/auth/login</code>. Export- och importflödena i den här manualen är samma endpoints
          som gränssnittet använder.
        </p>`
      },
      tillganglighet: {
        title: 'Tillgänglighet',
        html: `
        <p>
          Tillgänglighet är ett arkitekturkrav i Kollepedia, inte en efterhandsputs. All
          information som visas med rörelse eller drag finns också utan.
        </p>
        <ul>
          <li>
            <strong>Tre perceptuella kanaler för förändring.</strong> Historikens
            färgläge visar borttag/tillägg som rött och grönt. <strong>Bläck-läget</strong>
            är en helt färgoberoende läsning av samma animation: borttagen text tonar
            bort och kollapsar, ny text skrivs i tungt bläck och äldre lager åldras i
            vikt och styrka – väl lämpat vid färgblindhet. <strong>Statisk vy</strong>
            använder dessutom genomstrykning och understrykning utöver färg. Ingen
            information bärs alltså av kulör ensam.
          </li>
          <li>
            <strong>Tangentbord i tidslinjen.</strong> Tidslinjen är ett riktigt reglage:
            <kbd>←</kbd>/<kbd>→</kbd> stegar version för version,
            <kbd>Skift</kbd>+pil finskrubbar, <kbd>Home</kbd>/<kbd>End</kbd> hoppar till
            första/sista versionen och <kbd>Mellanslag</kbd> eller <kbd>Enter</kbd> spelar
            och pausar. Skärmläsare får värdetext i stil med <em>”Version 3 av 7 ·
            12 mars 2012”</em>.
          </li>
          <li>
            <strong>Reducerad rörelse.</strong> Har du <em>prefers-reduced-motion</em>
            aktiverat i systemet startar historiken automatiskt i <strong>Statisk
            vy</strong> – en kombinerad diff med lägena Före/Ändringar/Efter, all
            information utan rörelse. Läget kan också slås på manuellt.
          </li>
          <li>
            <strong>Versionslistan</strong> under historikens scen är en vanlig tabell med
            hela historien i klartext: datum, benämning, författare, status, ändringstyp
            och not.
          </li>
          <li>
            <strong>Teman.</strong> Knappen <strong>Byt tema</strong> i sidhuvudet växlar
            ljust → mörkt → högkontrast. Högkontrastläget är byggt mot WCAG:s skärpta
            kontrastkrav.
          </li>
          <li>
            <strong>Fokus och dialoger.</strong> Alla popovers och paneler stängs med
            <kbd>Esc</kbd>, fokus återvänder till knappen som öppnade dem, och synliga
            fokusmarkeringar finns genomgående.
          </li>
        </ul>`
      },
      administration: {
        title: 'Administration',
        html: `
        <p>
          Det här avsnittet visas bara för superadministratörer – verktygen nedan finns
          inte för andra roller. Ingångarna samlas i <strong>adminnavet</strong> på
          <code>/admin</code>.
        </p>
        <h3>Användargranskning</h3>
        <p>
          Registreringar som flaggas av spamskyddet – och alla anspråk på importerade
          författarprofiler som görs <em>utan</em> personlig aktiveringslänk – hamnar i
          manuell granskning. Ett väntande konto kan läsa allt men inte skriva förrän du
          godkänt det under <strong>Användare</strong>. Godkänn eller avvisa; personen får
          mejl när granskningen är klar.
        </p>
        <h3>Författarutskick och aktiveringslänkar</h3>
        <p>
          <strong>Uppsökande kontakt</strong> är arbetsbänken för att bjuda in importerade
          författare. Ingenting skickas automatiskt: verktyget bokför din egen manuella
          kontakt och tar fram kopieringsfärdiga inbjudningstexter. Avböjd kontakt är
          helig – en författare som tackat nej kontaktas aldrig igen.
        </p>
        <p>
          I inbjudningspanelen kan du skapa en <strong>personlig aktiveringslänk</strong>:
          en engångslänk, giltig i 30 dagar, knuten till just den författaren. Ett anspråk
          som görs via länken är verifierat i sig och aktiveras direkt – utan länk går
          anspråket till manuell granskning enligt ovan. Länken bakas automatiskt in i
          inbjudningstexten.
        </p>
        <h3>Utkorgen</h3>
        <p>
          All utgående e-post går genom den hårda adresslistan och samlas i
          <strong>utkorgen</strong> på <code>/admin/outbox</code>, där varje brev kan
          öppnas och kontrolleras – särskilt viktigt under test, då inga brev lämnar
          systemet.
        </p>`
      }
    },
    foot: 'Hittar du något i manualen som inte stämmer med verkligheten? Det räknas som en bugg – säg till.'
  },
  en: {
    kicker: 'Manual',
    title: 'How to use Kollepedia',
    lede: 'From your first search to a frozen procurement glossary. Reading requires no account — and everything you need to know to contribute fits on this page. Every section has its own link, so you can point a colleague straight to the right paragraph.',
    tocTitle: 'Contents',
    sections: {
      'komma-igang': {
        title: 'Getting started',
        html: `
        <p>
          Kollepedia is open to read. You can search the concepts, browse the collections,
          open any concept and play back its history in the history view — no account, no
          login.
        </p>
        <p>
          If you want to contribute — edit concepts, create lists, add relations — you need
          an account: every change becomes an immutable part of the history and must be
          attributable to a person. Click <strong>Log in</strong> in the header and choose
          the <strong>Create account</strong> tab. You enter, in this order:
        </p>
        <ul>
          <li><strong>Username</strong> — your public @name (lower case, digits, hyphens).</li>
          <li><strong>Display name</strong> — your author name, shown next to your contributions.</li>
          <li><strong>Email address</strong> — the login identity; a verification email is
            sent, see <a href="#epost">Email &amp; verification</a>.</li>
          <li><strong>Password</strong> — at least 12 characters.</li>
        </ul>
        <p>
          A <em>bot check</em> runs in the background — entirely without third-party
          services; nothing leaves the site. Registrations that look suspicious can be
          flagged for manual review: the account can then read everything but not
          contribute until an administrator approves it, and you get an email when the
          review is done. You log in with the email address or the username.
        </p>
        <p>
          <em>Has your name previously been imported as an author?</em> Then you claim the
          identity via your author page (the activation link leads to
          <code>/activate?handle=…</code>): the username is shown read-only and the account
          is tied to all your historical contributions.
        </p>
        <p>
          <em>Organisations in brief:</em> an organisation gathers colleagues around shared
          collections, with the roles viewer, editor and admin. More in the section
          <a href="#organisationer">Organisations &amp; permissions</a>.
        </p>
        <p>
          The header also holds the <strong>Switch theme</strong> button (light, dark,
          high contrast), the <strong>activity bell</strong> leading to events in the
          concepts you watch (greyed out until you log in) and the SV/EN language switch.
        </p>`
      },
      sok: {
        title: 'Search',
        html: `
        <p>
          The search field on the home page performs a free-text search across the concepts’
          <em>names and definitions</em>, in every collection you have access to. The
          results show which collection each hit comes from and the status of the version.
          To search within a single collection: open the collection and use its own field
          <strong>Search the collection …</strong>
        </p>
        <p>
          Below the search field sits the filter panel: <strong>More filters</strong>
          unfolds filters for language, categories, tags, collections and status — the
          same button reads <strong>Hide filters</strong> while the panel is open, and
          the count badge next to it shows how many filters are active even when the
          panel is closed. Active filters appear as removable chips below the field, and
          <strong>Clear filters</strong> resets everything.
        </p>
        <p>
          Definitions may contain cross-references written as [[double square brackets]] —
          clicking one opens a search for that concept.
        </p>`
      },
      begrepp: {
        title: 'Concepts & versions',
        html: `
        <p>
          A <em>concept</em> is a durable identity — “hållplats” as an idea. What you read
          on a concept page is always a particular <em>version</em> of the concept: an
          immutable snapshot of name, definition, status and tags.
        </p>
        <p>
          <strong>Nothing is ever overwritten.</strong> Every change becomes a new version
          appended to the history, much like a commit in git. That is why Kollepedia can
          always show exactly who wrote what, when — and why.
        </p>
        <p>
          The <em>why</em> question is answered by the <strong>note</strong>: the
          justification every version carries with it. It is required when you edit and is
          shown in the provenance card on the concept page and in the history view. Think
          of it as the version’s commit message.
        </p>
        <p>
          Every version has a <strong>status</strong> that follows the lifecycle
          <em>draft → proposed → deprecated/superseded</em>. <em>Endorsed</em> is not a
          status but an explicit, attributed stamp an organisation puts on one particular
          version (shown as ★ <em>Endorsed by …</em>). The stamp can be withdrawn — but even
          the withdrawal is a traceable event; history is never rewritten. Several endorsed
          definitions of the same thing can coexist: Kollepedia shows attributed
          disagreement instead of naming winners.
        </p>
        <p>
          Every version also carries <strong>provenance</strong>: whether it was created by
          a human, by an AI (marked <em>AI-generated</em> with the model name) or through an
          import (marked <em>Imported from …</em>).
        </p>
        <p>
          Concepts can be tied together with typed <strong>relations</strong> — related
          concept, broader/narrower, exact/close match, supersedes — each with an optional
          note about why they belong together. Translations are their own thing: they link
          versions across languages and are listed under <em>Translations</em> on the
          concept page.
        </p>`
      },
      historiken: {
        title: 'History',
        html: `
        <p>
          Open <strong>Open the history view</strong> on a concept page to watch the
          concept’s entire history play like a film: text being removed takes on a red tint
          and collapses, new text is written in on a green background. The heading always
          lands before the definition.
        </p>
        <ul>
          <li>
            <strong>Play, pause, scrub.</strong> The play button (<em>Play the
            history</em>) starts and pauses. Drag the playhead on the timeline to any
            moment — even in the middle of a transition. The version dots sit
            proportionally to real time, with years as the scale. The
            <strong>×</strong>-speed button changes the playback tempo.
          </li>
          <li>
            <strong>Chapter arrows.</strong> <em>Previous version</em> and
            <em>Next version</em> jump version by version, like chapter markers.
          </li>
          <li>
            <strong>Branch choice.</strong> Where the history forks, a small branch symbol
            appears on the timeline. Click it and choose under <em>Follow the history
            along…</em> whether the playback should follow the mainline (main) or a named
            branch — the timeline is redrawn after the choice.
          </li>
          <li>
            <strong>Order.</strong> The <strong>Order</strong> button toggles between
            <em>along the text</em> (the changes play in reading order, as if someone
            edited from start to finish) and <em>simultaneous</em> (everything red is
            marked first, then everything green is written).
          </li>
          <li>
            <strong>Ink mode.</strong> Fades the text by age: words written in the shown
            version stand in full ink, older layers fade step by step towards sepia — the
            text’s geology at a glance. A legend explains the scale. Ink mode requires the
            playback to be at rest; it automatically snaps to the nearest version.
          </li>
          <li>
            <strong>Hover for the author.</strong> While the playback is at rest you can
            hold the pointer over any word: everything written in the same version is
            highlighted, and a card shows who wrote it, when, and the version’s note.
          </li>
          <li>
            <strong>Static view.</strong> The <strong>Static view</strong> button switches
            off all motion and instead shows a combined diff with the modes
            <strong>Before</strong> / <strong>Changes</strong> / <strong>After</strong>.
            Below the stage there is also the <em>version list</em> — a plain table with
            date, author, status, change type and note for every version. See
            <a href="#tillganglighet">Accessibility</a>.
          </li>
        </ul>
        <p>
          The panel on the right always shows the focused version’s author, date, change
          type (revision, branch, synthesis, translation or restored version), provenance
          and note. It also holds the button <strong>Make current version</strong> — see
          <a href="#redigera">Editing</a>.
        </p>`
      },
      redigera: {
        title: 'Editing',
        html: `
        <p>
          Editing requires an account (<a href="#komma-igang">Getting
          started</a>). Without one, the buttons are disabled with the hint <em>Log in
          to edit</em>.
        </p>
        <ol>
          <li>Open the concept and click <strong>Edit</strong>.</li>
          <li>
            The panel <em>Edit — creates a new version</em> opens. Change the name, the
            definition (Markdown-lite: **bold**, *italic* and [[cross-references]]), the
            tags and the status.
          </li>
          <li>
            Write a <strong>Justification</strong> — it is required. <em>Why is this change
            being made?</em> The justification stays with the version forever.
          </li>
          <li>
            Click <strong>Save new version</strong>. Nothing is overwritten: your change
            becomes a new version on the mainline, attributed to your account.
          </li>
        </ol>
        <p>
          <strong>Branches.</strong> If you want to explore an alternative wording without
          touching the mainline: choose <strong>Create branch</strong> in the edit panel
          and give the branch a name. The branch becomes its own line in the history,
          visible in the history view’s branch choice — and can later be sent for review as
          a <a href="#andringsforslag">change proposal</a>.
        </p>
        <p>
          <strong>If someone else got there first (conflict).</strong> Two people can edit
          the same concept at the same time. If you save against a version that is no
          longer the latest, Kollepedia does not respond by overwriting anything — you are
          met with the message <em>“Someone else got there first”</em> and offered to
          create a branch instead. This is the <em>branch and unite</em> model: both
          changes are preserved as their own lines, and the reconciliation is a deliberate
          human decision — either through a synthesis in
          <a href="#jamforelseverkstaden">the Comparison Workbench</a> or by making one of
          the versions current. If you would rather rework your change on top of the new
          version, choose <strong>Back to editing</strong>.
        </p>
        <p>
          <strong>Restoring an older version.</strong> Open the history view, stand on the
          version you want back and click <strong>Make current version</strong>. A new
          version is created with the same content and a back-reference to the original —
          the head moves, but history is never rewritten. Undo is therefore never
          destructive.
        </p>
        <p>
          You create a <strong>new concept</strong> via <strong>+ New concept</strong> on a
          collection page (or <strong>+ New concept in the collection</strong> from a
          concept page). The concept gets a first version on the mainline; every later
          change becomes a new version.
        </p>`
      },
      andringsforslag: {
        title: 'Change proposals',
        html: `
        <p>
          A <em>change proposal</em> is Kollepedia’s counterpart to a pull request: a
          branch is sent for review to be united with the mainline. It is the orderly way
          to propose changes to concepts you do not curate yourself — and the only way into
          locked collections.
        </p>
        <ol>
          <li>
            Create a <strong>branch</strong> with your wording
            (<a href="#redigera">Editing</a>).
          </li>
          <li>
            On the concept page, under <em>Change proposals</em>: choose
            <strong>Propose a change from a branch …</strong>, give the proposal a
            <strong>Title</strong> and a description, and click
            <strong>Submit change proposal</strong>. A branch can only have one open
            proposal at a time.
          </li>
          <li>
            The reviewer opens the proposal — via the concept page or the collection page
            for all proposals at <code>/proposals</code> — and sees a <em>before/after</em>
            diff against the current version.
          </li>
          <li>
            The decision is explicit and justified: <strong>Merge</strong> creates a new
            version on the mainline with the branch’s content (if the mainline has moved
            on, it becomes a synthesis with both as parents); <strong>Reject</strong>
            closes the proposal with a justification. The proposer can choose
            <strong>Withdraw</strong> themselves.
          </li>
        </ol>
        <p>
          <strong>Locked collections.</strong> In a locked collection, ordinary writes are
          blocked for everyone except the collection’s administrators — but creating
          <em>branches</em> is allowed for anyone signed in. That is
          deliberate: locked content evolves through branches and change proposals, never
          through direct changes. The right to merge or reject lies with whoever curates
          the collection (collection rights, the owning organisation’s admin, or a super
          admin).
        </p>
        <p>
          Like everything else, decisions are traceable: a merged or rejected proposal
          keeps its justification, its discussion and its history.
        </p>`
      },
      'samlingar-listor': {
        title: 'Collections & lists',
        html: `
        <p>
          This is the most important distinction in all of Kollepedia. Once you have it,
          the rest falls into place.
        </p>

        <div class="duo ui">
          <div class="duo-card">
            <h3>Collection</h3>
            <p class="duo-tag">Where concepts live and evolve.</p>
            <p>
              A collection is a vocabulary — a shelf in the library. Transmodel,
              Kollektivtrafikordboken, your internal concept list. This is where the
              concepts <em>live</em>: they have their history here, get new versions here,
              are endorsed here. Every concept has exactly one home — its collection.
            </p>
          </div>
          <div class="duo-card">
            <h3>List</h3>
            <p class="duo-tag">What you have gathered, for a purpose.</p>
            <p>
              A list is your selection box — what you have picked from the shelves for a
              particular purpose: a procurement, a project, a glossary for a report. The
              list <em>owns no concepts</em>; it points to them. And it does not point
              loosely at “the concept” — it <em>pins exact versions</em>.
            </p>
          </div>
        </div>

        <p>
          That is why you never put a procurement’s terms <em>into</em> Transmodel. You
          build a <em>list</em> that references precisely the Transmodel versions you
          need — pinned, so they cannot drift away as the collection keeps evolving.
        </p>

        <h3>The collections overview</h3>
        <p>
          The <strong>Collections</strong> page is grouped by proximity: logged in you
          see <em>My collections</em>, then <em>Organisation collections</em> and last
          <em>Public collections</em>; without an account only the public ones are
          shown. Each card shows the collection’s key facts — year, number of concepts,
          licence, visibility, edit policy — and a filled padlock next to the name means
          the collection is write-protected.
        </p>
        <p>
          Your own collections are always <em>private</em> — only you see them. The
          card’s <strong>Share</strong> button leads to a page explaining the path to
          shared content: create or join an organisation and move the collection there.
        </p>

        <h3>The collection page’s tool row</h3>
        <p>
          On a collection’s page, below the metadata, sits the tool row with
          <strong>Write-protect</strong> (or <strong>Unlock</strong>),
          <strong>Edit</strong>, <strong>Export</strong> and <strong>Import</strong> —
          the buttons appear according to your permissions. More on write protection in
          <a href="#organisationer">Organisations &amp; permissions</a>, on the formats
          in <a href="#export">Export</a> and <a href="#import">Import</a>.
        </p>

        <h3>Example: the procurement</h3>
        <ol>
          <li>
            Go to <strong>Lists</strong> in the header and click
            <strong>+ New list</strong>. Name it, e.g. <em>City bus procurement 2027</em>,
            and preferably state its purpose.
          </li>
          <li>
            Search for the concepts the procurement needs. Open each concept and click
            <strong>⚲ Add to list</strong>. Choose the list and the option
            <strong>Pin this version</strong> — <em>frozen, does not change when the
            concept is updated</em>.
          </li>
          <li>
            Unsure which definition is the right one? Open the list and click
            <strong>Compare the concepts</strong> to see the candidates side by side in
            <a href="#jamforelseverkstaden">the Comparison Workbench</a>.
          </li>
          <li>
            When the selection is done: export the list as a frozen glossary
            (<a href="#export">Export</a>) and attach it to the tender documents.
          </li>
        </ol>
        <p>
          The point: when the Transmodel collection gets new versions next year, your annex
          <em>still means exactly what it meant when the bids were submitted</em>. The
          <em>Version</em> column in the list shows for each row whether it is
          <em>pinned to version …</em> or <em>follows latest</em>.
        </p>

        <h3>Follow latest — an active choice</h3>
        <p>
          Pinning is the default. If you instead want a row in the list to always show the
          concept’s latest version — for example in a living project glossary — choose
          <strong>Follow latest</strong> when adding the concept (<em>updates when the
          concept gets a new version</em>). It is deliberately an opt-in: a list that
          drifts without you asking for it is more dangerous than one that stands still.
        </p>

        <p class="rule-of-thumb">
          <strong>Rule of thumb:</strong> Is it a definition to be curated and evolved?
          → collection. Is it a selection for your purpose? → list.
        </p>`
      },
      jamforelseverkstaden: {
        title: 'The Comparison Workbench',
        html: `
        <p>
          The Comparison Workbench puts competing definitions side by side — <em>see what
          differs, and forge a shared one</em>. You reach it via
          <strong>Compare the concepts</strong> on a list, or directly at the address
          <code>/compare</code>.
        </p>
        <ul>
          <li>
            <strong>Columns.</strong> Each concept is a column with name, collection,
            status, tags, definition and author. Add more via the search field
            <strong>Add concept …</strong>; remove a column with the
            <strong>×</strong> button in its corner.
          </li>
          <li>
            <strong>Base.</strong> One column is always the <em>base</em> (marked with the
            radio button in the column header). It is the yardstick: all differences are
            calculated against it, and it becomes the foundation when you harmonise.
          </li>
          <li>
            <strong>Diff mode.</strong> Switch on <strong>Diff mode</strong> in the toolbar
            and exactly what differs is marked word by word: red strikethrough exists
            <em>only in the base</em>, green <em>only in this column</em>.
          </li>
          <li>
            <strong>Share with a link.</strong> The whole comparison lives in the address
            bar (<code>/compare?ids=…</code>) — copy the URL and send it to a colleague,
            and they see exactly the same arrangement.
          </li>
          <!--ai--><li>
            <strong>✦ Harmonise</strong> creates an AI draft that unifies the columns’
            definitions — see <a href="#ai">AI features</a>.
          </li><!--/ai-->
        </ul>`
      },
      export: {
        title: 'Export',
        html: `
        <p>
          Under <strong>Export</strong> on a list’s page there are buttons for five
          formats. On a collection’s page, <strong>Export</strong> in the tool row opens
          a menu with the same formats. Choose by recipient:
        </p>
        <ul>
          <li>
            <strong>CSV</strong> — spreadsheets and further processing; opens directly in
            Excel.
          </li>
          <li>
            <strong>Markdown</strong> — readable text for documents, annexes and wikis; the
            natural choice for the procurement annex.
          </li>
          <li>
            <strong>JSON-LD</strong> — linked data for system integration and developers.
          </li>
          <li>
            <strong>SKOS</strong> — (Turtle) for vocabulary tools and the semantic web;
            concepts, definitions and relations come along.
          </li>
          <li>
            <strong>TBX</strong> — the terminology standard ISO 30042, for
            terminology-management and translation tools; language pairs come along where
            translation links exist.
          </li>
        </ul>
        <p>
          <strong>Pinned versions make the export frozen.</strong> A list exports exactly
          the versions it has pinned — <em>the frozen glossary survives later changes in
          the collections</em>. Rows that instead follow latest export the version that is
          current at the moment of export.
        </p>`
      },
      import: {
        title: 'Import',
        html: `
        <p>
          Import happens per collection and accepts CSV or Excel files (.xlsx, first
          sheet); you reach the import view via <strong>Import</strong> in the
          collection page’s tool row. Always start by downloading <em>the template</em> from the collection’s
          import view — it contains the header row and one example row. The column headers
          must be spelled exactly like this:
        </p>

        <div class="table-scroll">
          <table class="ui">
            <thead>
              <tr>
                <th scope="col">Column</th>
                <th scope="col">Required</th>
                <th scope="col">Format &amp; meaning</th>
                <th scope="col">Example</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><code>canonical_form</code></td>
                <td>yes</td>
                <td>The concept’s name</td>
                <td>anropsstyrd trafik</td>
              </tr>
              <tr>
                <td><code>language</code></td>
                <td>no</td>
                <td><code>sv</code> or <code>en</code> (default: <code>sv</code>)</td>
                <td>sv</td>
              </tr>
              <tr>
                <td><code>definition</code></td>
                <td>yes</td>
                <td>The definition text</td>
                <td>Kollektivtrafik som körs efter beställning …</td>
              </tr>
              <tr>
                <td><code>status</code></td>
                <td>no</td>
                <td>draft, proposed, deprecated, superseded — or the Swedish labels utkast, föreslagen,
                  utfasad, ersatt (endorsed is read as proposed; endorsing is done in the app)</td>
                <td>utkast</td>
              </tr>
              <tr>
                <td><code>tags</code></td>
                <td>no</td>
                <td>Tags, separated by <code>;</code></td>
                <td>drift;planering</td>
              </tr>
              <tr>
                <td><code>categories</code></td>
                <td>no</td>
                <td>Global categories, separated by <code>;</code> — names (Swedish or
                  English) from the global vocabulary; unknown names are row errors</td>
                <td>Operations;Urban Mobility</td>
              </tr>
              <tr>
                <td><code>part</code></td>
                <td>no</td>
                <td>Part in the collection’s part taxonomy (requires the collection to
                  have one); an unknown name is a row error</td>
                <td>Fare Management</td>
              </tr>
              <tr>
                <td><code>note</code></td>
                <td>no</td>
                <td>Justification — the version’s note</td>
                <td>Ur ordlistan 2024, kap. 3</td>
              </tr>
              <tr>
                <td><code>author</code></td>
                <td>no</td>
                <td>Author</td>
                <td>Anna Andersson</td>
              </tr>
              <tr>
                <td><code>author_affiliation</code></td>
                <td>no</td>
                <td>The author’s organisation</td>
                <td>K2</td>
              </tr>
              <tr>
                <td><code>variants</code></td>
                <td>no</td>
                <td>Variants (inflections, abbreviations, synonyms), separated by
                  <code>;</code></td>
                <td>anropstrafik;flextrafik</td>
              </tr>
              <tr>
                <td><code>related_to</code></td>
                <td>no</td>
                <td>Names of related concepts, separated by <code>;</code></td>
                <td>hållplats;linje</td>
              </tr>
              <tr>
                <td><code>broader</code></td>
                <td>no</td>
                <td>Name of the broader concept</td>
                <td>kollektivtrafik</td>
              </tr>
              <tr>
                <td><code>narrower</code></td>
                <td>no</td>
                <td>Name of the narrower concept</td>
                <td>flextur</td>
              </tr>
              <tr>
                <td><code>exact_match</code></td>
                <td>no</td>
                <td>Name of an exact match</td>
                <td>demand-responsive transport</td>
              </tr>
              <tr>
                <td><code>translation_of</code></td>
                <td>no</td>
                <td>The name of the same concept in the other language (a row in the same
                  file, or an existing concept in the collection)</td>
                <td>demand-responsive transport</td>
              </tr>
              <tr>
                <td><code>source</code></td>
                <td>no</td>
                <td>Free-text source reference</td>
                <td>Ordbok för framtidens resande, 2024</td>
              </tr>
            </tbody>
          </table>
        </div>

        <p>
          Relations and translations are resolved in two steps: first against rows in the
          same file, then against concepts that already exist in the collection. Authors in
          the <code>author</code> column become users in the system — they can later claim
          their identity by registering with the same name. Every imported version gets the
          provenance <em>import</em>, with the file name and row number.
        </p>
        <p>
          <strong>Dry run first.</strong> Always run the import as a dry run before
          importing for real: the whole file is validated — number of rows, what would be
          created, errors and warnings with row numbers — but <em>nothing is written</em>.
          When the report is clean, run the same import for real.
        </p>
        <!--ai--><p>
          <strong>Unstructured text via AI.</strong> Do you have a glossary that only
          exists as running text — a PDF, an old Word document? Paste the text and the AI
          (with your own key, see <a href="#ai">AI features</a>) suggests ready-made import
          rows in the same column format. The suggestions are always drafts for your review
          and go through the same dry run — nothing is imported automatically.
        </p><!--/ai-->`
      },
      ai: {
        title: 'AI features',
        html: `
        <p>
          All AI in Kollepedia is <em>bring your own key</em>: you use your own key with a
          provider of your choice, and the platform carries no token costs. Kollepedia is,
          moreover, fully usable entirely without AI.
        </p>

        <h3>AI providers</h3>
        <p>
          Click <strong>AI settings</strong> in the Comparison Workbench’s toolbar (or in
          the import view’s AI tab). There you choose a <strong>Provider</strong>:
        </p>
        <ul>
          <li>
            <strong>Anthropic</strong> — the default choice; key <code>sk-ant-…</code>,
            default model <code>claude-sonnet-5</code>.
          </li>
          <li>
            <strong>Berget.ai (OpenAI-compatible)</strong> — a Swedish provider running in
            a Swedish data centre, a good choice when data must not leave the EU. Default
            model <code>meta-llama/Llama-3.3-70B-Instruct</code>; check Berget’s model
            catalogue and type the model name in the <strong>Model</strong> field — it is
            sent as <code>model</code> in the request.
          </li>
          <li>
            <strong>OpenAI-compatible (custom base URL)</strong> — any service that speaks
            OpenAI’s chat-completions format: enter the <strong>Base URL</strong>
            (e.g. <code>https://api.openai.com/v1</code> or your own gateway) and a model
            (default <code>gpt-4o-mini</code>).
          </li>
        </ul>
        <p>
          <strong>The key</strong> is pasted into the same dialog and you choose
          <strong>Save</strong>. Key, provider and model are stored <em>only in your
          browser</em>; the key is never sent to Kollepedia’s server except with the actual
          request, which is proxied without being stored or logged. <strong>Clear</strong>
          removes it all whenever you like. The model field’s placeholder shows the
          provider’s default model — leave the field empty and that is what is used.
        </p>

        <h3>Prompt presets</h3>
        <p>
          Guidance texts you use often — <em>“Prefer Transmodel terminology, keep the
          definition under 50 words”</em> — can be saved as presets. Write the guidance in
          the harmonisation panel and click <strong>Save as preset …</strong>; give the
          preset a name and tick <em>Shared</em> if colleagues should see it. Next time,
          choose it in the <strong>Preset</strong> list. When a draft is created with a
          preset selected, the preset’s id travels with the version’s provenance — prompts
          are first-class citizens, not loose scraps.
        </p>
        <p>
          <strong>The harmonise flow.</strong> With at least two concepts loaded in the
          Comparison Workbench and the key in place, <strong>✦ Harmonise</strong> lights
          up:
        </p>
        <ol>
          <li>
            Choose which column should be the <em>base</em> — it becomes the foundation of
            the synthesis.
          </li>
          <li>
            Optionally write a guidance text for the model (e.g. <em>“Prefer Transmodel
            terminology, keep the definition under 50 words”</em>) and click
            <strong>Create AI draft</strong>.
          </li>
          <li>
            Review and edit the draft’s term, definition and note — the draft is just a
            draft, and you are the editor.
          </li>
          <li>
            <strong>Save as a synthesis of “…”</strong> writes a new version with the
            status <em>draft</em> on the base’s concept, with all compared versions as
            parents. In the history view it appears as <em>Synthesis of several
            versions</em>.
          </li>
        </ol>
        <p>
          <strong>A human always reviews.</strong> No AI draft is saved without you having
          seen it, been able to edit it and actively saved it. And everything that
          originates in a model is marked so in its provenance — <em>AI-generated</em>,
          with the model name — visible on the concept page, in the history view and in the
          version list.
        </p>`
      },
      diskussioner: {
        title: 'Discussions, watching & activity',
        html: `
        <p>
          <strong>Discussion.</strong> Every concept page and every change proposal has a
          discussion thread. Write a post and click <strong>Post</strong> — questions,
          sources, objections; the things that do not belong in the definition itself but
          are needed to reach agreement. Posts are attributed and can only be deleted by
          their author (or a super admin). The discussion is the conversation
          <em>beside</em> the history — the decisions themselves live as versions and
          proposals.
        </p>
        <p>
          <strong>Watch.</strong> The <strong>Watch</strong> button on the concept page
          follows the concept for you; it switches to <em>Watching</em>. Watching requires
          an account.
        </p>
        <p>
          <strong>Activity.</strong> The <a href="/activity">Activity</a> page gathers the
          events in your watched concepts — new versions, endorsements, posts and change
          proposals — newest first, with links straight into the concepts. Every concept
          page also has its own activity feed with the same event types.
        </p>`
      },
      epost: {
        title: 'Email & verification',
        html: `
        <p>
          Accounts are created with an email address, and the address is used for
          verification and reset links. An address counts as <em>verified</em> only once
          you have clicked the link in the verification email
          (<code>/verify-email?token=…</code>). If you change the address — on
          <a href="#profil">the profile page</a> — a new email is sent and the address must
          be verified again.
        </p>
        <p>
          <strong>Forgot password.</strong> The <strong>Forgot your password?</strong> link
          on the login tab leads to a form where you enter an email address or a username.
          The answer is always neutral (no account enumeration); a reset link is only sent
          if the account has a verified address. Administrators can also always create a
          reset link manually via user management.
        </p>
        <p>
          <strong>The outbox and the allowlist.</strong> On kollepedia.se the messages are
          sent from <code>no-reply@kollepedia.se</code>; if one does not arrive within a few
          minutes, check your spam folder. Every message the system creates is also recorded
          in the outbox at <code>/admin/outbox</code> (super admin only). In an installation
          without a mail relay the messages stay there, and an <em>allowlist</em> in the
          server decides which addresses may receive mail at all — email to other recipients
          is marked <em>blocked</em> and stored for inspection instead of being sent.
        </p>`
      },
      profil: {
        title: 'Profile',
        html: `
        <p>
          <strong>My profile</strong> in the account menu (header) is your account’s home.
          There you see your username, display name, affiliation and organisation, with a
          link to your public author page — the one that shows your contributions to
          everyone else.
        </p>
        <ul>
          <li>
            <strong>Email.</strong> Set or change your email address; the address is shown
            with its verification status (<em>verified</em> / <em>not verified</em>).
            Every change triggers a new verification email — see
            <a href="#epost">Email &amp; verification</a>.
          </li>
          <li>
            <strong>Change password.</strong> Enter your current and your new password (at
            least 12 characters). The change applies immediately at your next login.
          </li>
        </ul>`
      },
      permalankar: {
        title: 'Permalinks & citation',
        html: `
        <p>
          Because versions are immutable, they can be cited with a clear conscience. Every
          version has a permanent address — <code>/versions/&lt;id&gt;</code> — that shows
          exactly that frozen version, however the concept evolves afterwards. You reach it
          from the history view’s version list.
        </p>
        <p>
          The page shows a banner saying the version never changes, a note on whether it is
          still the concept’s current version, and a <strong>Cite</strong> box with two
          copyable fields: the permanent address and a ready-made citation (name,
          collection, version, date, URL) — ready to paste into the report or the tender
          documents. Links back to the concept and its History sit alongside.
        </p>`
      },
      organisationer: {
        title: 'Organisations & permissions',
        html: `
        <p>
          An organisation gathers colleagues around shared collections. You create an
          organisation (name and slug) while logged in with an account; you become its
          admin yourself. New organisations are approved by a super administrator before
          they are taken into full use.
        </p>
        <p>Members are added by their username and get one of three roles:</p>
        <ul>
          <li>
            <strong>Viewer</strong> — sees the organisation’s private content.
          </li>
          <li>
            <strong>Editor</strong> — creates and edits concepts in the organisation’s
            collections.
          </li>
          <li>
            <strong>Admin</strong> — all of the above, plus manages members, roles and the
            collections’ settings.
          </li>
        </ul>
        <p>
          <strong>Visibility.</strong> A collection is <em>public</em> (readable by
          anyone, even without an account), <em>organisation-private</em> (visible only
          to the organisation’s members — and that applies everywhere: search, concept
          pages, comparisons and export) or <em>private</em> (a personal collection only
          its creator sees). Writing in an organisation-owned collection requires the
          editor or admin role; a private collection is edited only by its creator. The
          public collections without an owning organisation — the system collections,
          such as Transmodel — are curated by the super administrator and are
          write-protected: everyone else contributes through branches and
          <a href="#andringsforslag">change proposals</a>.
        </p>
        <p>
          <strong>Locking &amp; archiving.</strong> Whoever curates a collection can
          <strong>lock</strong> it — the button is called <strong>Write-protect</strong>
          in the collection page’s tool row, and <strong>Unlock</strong> lifts the lock.
          Ordinary writes are then blocked for everyone except the
          collection’s administrators, but branches — and thereby
          <a href="#andringsforslag">change proposals</a> — remain open. To
          <strong>archive</strong> goes further: the collection is hidden from the
          collection list, gets an <em>Archived</em> banner and blocks all writes until it
          is restored. Neither decision deletes anything.
        </p>
        <p>
          The super administrator manages the whole: approves organisations, designates
          authoritative collections, manages users (<code>/admin/users</code>) and
          inspects the email outbox (<code>/admin/outbox</code>). In a fresh installation,
          the first registered user becomes super admin.
        </p>`
      },
      mcp: {
        title: 'For developers & agents',
        html: `
        <p>
          Kollepedia is built so that machines, too, can work with the concepts — with the
          same traceability as humans.
        </p>
        <p>
          <strong>The MCP server</strong> lets AI agents (e.g. Claude) read and search the
          concepts via the Model Context Protocol. The public endpoint
          <code>https://kollepedia.se/mcp</code> needs no account and sees the same content
          as an anonymous visitor. The tools are <code>list_collections</code>,
          <code>get_collection</code>, <code>search_concepts</code>,
          <code>get_concept</code> and <code>get_concept_history</code>; collections without
          redistribution rights are searchable but marked as not exportable. Signed-in
          access with writes comes in a later step. Register the server:
        </p>
        <pre class="ui" tabindex="0" role="region" aria-label="Command line for MCP registration"><code>claude mcp add --transport http kollepedia https://kollepedia.se/mcp</code></pre>
        <p>
          <strong>The REST API</strong> lives under <code>/api/v1</code>: reading is open
          (public collections), writing requires an identity — a Bearer token from
          <code>/auth/login</code>. The export and import flows in this manual are the same endpoints the
          interface uses.
        </p>`
      },
      tillganglighet: {
        title: 'Accessibility',
        html: `
        <p>
          Accessibility is an architectural requirement in Kollepedia, not an afterthought.
          All information presented with motion or dragging is also available without it.
        </p>
        <ul>
          <li>
            <strong>Three perceptual channels for change.</strong> The history view’s
            colour mode shows removals/additions as red and green. <strong>Ink
            mode</strong> is an entirely colour-independent reading of the same animation:
            removed text fades away and collapses, new text is written in heavy ink and
            older layers age in weight and strength — well suited to colour blindness.
            <strong>Static view</strong> additionally uses strikethrough and underline
            beyond colour. No information is carried by hue alone.
          </li>
          <li>
            <strong>Keyboard on the timeline.</strong> The timeline is a real slider:
            <kbd>←</kbd>/<kbd>→</kbd> steps version by version,
            <kbd>Shift</kbd>+arrow fine-scrubs, <kbd>Home</kbd>/<kbd>End</kbd> jumps to the
            first/last version and <kbd>Space</kbd> or <kbd>Enter</kbd> plays and pauses.
            Screen readers get value text along the lines of <em>“Version 3 of 7 ·
            12 March 2012”</em>.
          </li>
          <li>
            <strong>Reduced motion.</strong> If you have <em>prefers-reduced-motion</em>
            enabled in your system, the history view automatically starts in
            <strong>Static view</strong> — a combined diff with the modes
            Before/Changes/After, all the information without motion. The mode can also be
            switched on manually.
          </li>
          <li>
            <strong>The version list</strong> below the history view’s stage is a plain
            table with the whole history in clear text: date, name, author, status, change
            type and note.
          </li>
          <li>
            <strong>Themes.</strong> The <strong>Switch theme</strong> button in the header
            cycles light → dark → high contrast. The high-contrast mode is built against
            WCAG’s stricter contrast requirements.
          </li>
          <li>
            <strong>Focus and dialogs.</strong> All popovers and panels close with
            <kbd>Esc</kbd>, focus returns to the button that opened them, and visible
            focus markers are present throughout.
          </li>
        </ul>`
      },
      administration: {
        title: 'Administration',
        html: `
        <p>
          This section is shown to super administrators only — the tools below do not
          exist for other roles. The entry points are gathered in the
          <strong>admin hub</strong> at <code>/admin</code>.
        </p>
        <h3>Account review</h3>
        <p>
          Registrations flagged by the spam protection — and every claim on an imported
          author profile made <em>without</em> a personal activation link — land in manual
          review. A pending account can read everything but cannot write until you approve
          it under <strong>Users</strong>. Approve or reject; the person is emailed when
          the review is done.
        </p>
        <h3>Author outreach and activation links</h3>
        <p>
          <strong>Outreach</strong> is the workbench for inviting imported authors.
          Nothing is ever sent automatically: the tool bookkeeps your own manual contact
          and produces copy-ready invitation texts. Opt-out is sacred — an author who has
          declined is never contacted again.
        </p>
        <p>
          In the invitation panel you can create a <strong>personal activation link</strong>:
          a single-use link, valid for 30 days, tied to that specific author. A claim made
          through the link is verified by construction and activates directly — without a
          link the claim goes to manual review as above. The link is baked into the
          invitation text automatically.
        </p>
        <h3>The outbox</h3>
        <p>
          All outgoing email passes the hard allowlist and is collected in the
          <strong>outbox</strong> at <code>/admin/outbox</code>, where every message can
          be opened and inspected — especially important during testing, when no mail
          leaves the system.
        </p>`
      }
    },
    foot: 'Found something in the manual that does not match reality? That counts as a bug — let us know.'
  }
};
