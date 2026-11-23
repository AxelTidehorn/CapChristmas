# MEDELTOMTEN — produktspecifikation och teknisk arkitektur

**Version:** 1.0, 23 november 2026  
**Status:** Implementationsunderlag för en första fungerande version  
**Mål:** En pålitlig, offlinekörbar webbapp för en julfest med cirka 40–75 deltagare.

## 1. Koncept

Deltagarna får en avsiktligt torr och kryptisk uppgift:

> **Rita en genomsnittstomte.**  
> Du har fem minuter på dig. Använd det medföljande pappret. Din teckning kommer att analyseras. Bedömningskriterierna offentliggörs efter avslutad uppgift.

Arrangören fotograferar/skannar de färdiga A4-teckningarna och laddar upp dem. Appen registrerar teckningarna i en gemensam koordinatram, beräknar en verklig medelvärdesbild och rangordnar teckningarna efter hur nära den representativa genomsnittsbilden de ligger enligt en öppen, deterministisk metod.

Showen ska vara oproportionerligt dramatisk: en växande/morfande sammanslagning av teckningarna, kriminaltekniskt skanningsgränssnitt, snabb kandidatsökning och en slutlig **MATCH FOUND**. Den matematiska analysen är äkta; showen ändrar aldrig vinnaren.

## 2. Produktmål och avgränsningar

### Måste uppnås
- En arrangör ska kunna hantera 40–75 teckningar från en laptop och visa en separat helskärmspresentation på projektor.
- Genomsnittet ska baseras på **faktiska inskickade teckningar**, inte generativ bild-AI.
- Vinnaren ska utses reproducerbart och förklarligt; rangordningen ska gå att granska efter showen.
- Analysen och presentationen ska fungera utan internet när beroenden har installerats i förväg.
- Enskilda felaktiga foton ska kunna granskas/korrigeras utan att hela batchen tas om.

### Ingår i V1
- Utskrivbar A4-ritmall, drag-and-drop/batchuppladdning (JPG/JPEG/PNG/WebP), deltagar-ID och valfri etikett.
- Geometrisk normalisering, kvalitetskontroll och manuell korrigering.
- Verklig medelvärdesbild (rå + separat visningsförstärkt).
- Flerskalig matematisk jämförelse och reproducerbar ranking.
- Adminvy och projektorvy, tydlig show, start/paus/fortsätt/hoppa/upprepa.
- Resultatsida med vinnare, topp 5, mest avvikande, galleri, transparent metod och dataexport.
- Test-/demoläge med tydligt markerade syntetiska testteckningar.

### Ingår inte i V1
- Konton, molndrift, deltagaruppladdning från egna telefoner eller samarbetsredigering.
- Generativ AI, ansiktsigenkänning, biometrisk analys eller ogrundade AI-confidence-procent.
- Automatisk identifiering av tomtens skägg/mössa/ansikte eller tränad specialmodell.
- Videorendering för export; webbläsarens fullskärmsläge räcker.

## 3. Användarflöde

1. **Förbered:** Arrangören öppnar `/control`, skriver ut A4-ritmallar och testar `/show` på projektorn.
2. **Genomför:** Deltagarna ritar på varsin mall under cirka fem minuter. Namn/nummer kan anges på avsedd rad utanför ritområdet.
3. **Digitalisera:** Samla in och fota/skanna arken. Fyra tryckta markörer ska helst synas i bild.
4. **Importera:** Ladda upp 40–75 bilder i en batch eller flera. Appen visar förhandsvisningar, ID, status och kvalitetsvarningar.
5. **Kontrollera:** Dåligt identifierade ark markeras `needs_review`; arrangören kan sätta fyra hörn manuellt eller utesluta oanvändbara bidrag med tydlig motivering.
6. **Beräkna & kör show:** En enda `Beräkna och starta show`-knapp på kontrollskärmen visar omedelbart en verklig analys-/förberedelseskärm på projektorn; när analysen är klar följer showen automatiskt. Alternativet `Beräkna utan att starta show` gör förberedelser i förväg.
7. **Avslöja:** Bygg upp medelbild, kör kandidatsökning, visa toppkandidater och lås till matematiskt vald vinnare.
8. **Efteråt:** Visa medelbild bredvid vinnaren, topp 5 och mest avvikande tomte; exportera medelbild och CSV/JSON.
9. **Städa:** `Radera session` tar bort bilder och metadata från den lokala appens sessionsmapp efter bekräftelse.

## 4. Ritmall och bildregistrering

### Utskrivbar A4-mall
- A4 stående, svartvit, fungerar med vanlig kontorsskrivare.
- Stor neutral centrerad rityta (exakt format dokumenteras i koden).
- Fyra unika ArUco-markörer utanför ritytan, en vid varje hörn, med positions- och ID-information i koden.
- Kort uppgift och fält för valfritt bidragsnummer utanför ritytan.
- Markörer, tryckta texter och ram **får aldrig** ingå i analysens pixeldata.
- Mall tillgänglig via en separat printvänlig webbsida med CSS för A4 och ett `Skriv ut`-kommando. Vid behov kan användaren skriva ut till PDF via webbläsaren.

### Förbehandlingspipeline
1. Läs bild, tillämpa EXIF-orientering och begränsa stora upplösningar innan beräkning; behåll tillräckliga detaljer för marköridentifiering.
2. Hitta de fyra ArUco-markörerna med OpenCV. Lös homografi, perspektivkorrigera och extrahera exakt den definierade ritytan.
3. Om markörer saknas: pröva tydlig sid-/ramdetektion, men acceptera inte osäkra resultat som korrekta; flagga till manuell fyrhörnskorrigering.
4. Skala ritytan till en fast kanvas, förslagsvis 512 × 512 px eller motsvarande dokumenterat format, utan att förvränga motivets proportioner (vid rektangulär rityta: välj dimensioner efter proportionerna, t.ex. 512 × 640). Alla bilder använder **samma** kanvas.
5. Neutralisera ljusvariationer och pappersbakgrund varsamt; omvandla till flyttalsbaserad **bläckkarta** `I_i(x,y)` i intervallet [0,1], där 0 är rent papper och 1 svart linje. Bevara blyerts-/pennstreck så långt möjligt.
6. Räkna täckningsgrad och annan kvalitet. Flagga tomma, överexponerade, beskurna och mycket svaga ark. Uteslut inte automatiskt utan synligt beslut.
7. Spara original, normaliserad kanvas, kvalitetsmetadata och valda hörn för reproducerbarhet.

**Viktig begränsning:** Motiven kan vara olika placerade eller stora **inom** ritytan. Det är del av teckningarna, inte nödvändigtvis ett fotograferingsfel. Gör därför inte okontrollerad, individuell smart beskärning eller AI-baserad omformning som ändrar vad deltagaren faktiskt ritat. Geometrin normaliserar framför allt papperets position och perspektiv.

## 5. Genomsnitt och urval

### 5.1 Äkta medelvärdesbild
För `N` giltiga ink maps på samma koordinatgrid:

`M(x,y) = (1/N) * Σ_i I_i(x,y)`.

Spara:
- `average_raw.png`: direkt rendering av `M` till ljus/grå bläckbild.
- `average_display.png`: ett visuellt förstärkt exemplar av samma data (för projektor), tydligt märkt som **visningsförstärkt**; påverkar aldrig rangordningen.

Det här är en verklig pixelmedelvärdesbild. Den kan se mjuk eller spöklik ut om teckningarna varierar mycket. Visa det hellre ärligt än att ersätta den med en påhittad AI-tomte.

### 5.2 Deterministisk likhetsberäkning (V1)
Mät form på flera skalor för att inte enbart straffa varje penndrag som hamnat några pixlar fel.

- För varje bild, bilda Gaussian-blurrade varianter av `I_i` vid tre fasta skalor, t.ex. `σ = 4, 16, 40` på 512 px-referensbredd. Skala sigman proportionellt om kanvasen är annan bredd.
- Skapa samma varianter av `M`.
- Beräkna för varje kandidat en viktad summa av mean squared error mellan kandidat och medelbild: `D_i = 0.20*MSE(G4(I_i), G4(M)) + 0.35*MSE(G16(I_i), G16(M)) + 0.45*MSE(G40(I_i), G40(M))`.
- Lägre `D_i` är bättre. Vikter/skalor är startvärden; lägg dem i en versionshanterad konfiguration, inte dolda magiska tal. Välj inte om dem manuellt efter att vinnaren blivit känd.
- Mest genomsnittliga teckning = lägst `D_i`.
- Mest avvikande = högst `D_i` bland godkända bidrag.
- Hantera lika resultat deterministiskt (t.ex. stabilt bidrags-ID som tie-breaker) och markera lika poäng i exporten.
- Beräkna inte fejkade procenttal som skulle kunna misstas för sannolikhet eller statistisk konfidens. UI kan använda placering `#1 av 73` och ett öppet redovisat relativt index vid behov.

**Kända risker:** Många vita pixlar, mycket olika detaljrikedom och stora positionsskillnader kan påverka avståndsmåttet. Kvalitetsgranska testmaterial och redovisa detta i metodpanelen. Om metoden visar sig systematiskt premiera nästan tomma teckningar: flagga sådan indata som potentiellt ogiltig, analysera varför och justera framtida algoritmversion öppet; ändra inte efterhand för en enskild tävling.

### 5.3 Resultatmetadata
Spara analysversion, normaliseringsparametrar, vägningskonfiguration, giltiga/uteslutna bidrag, SHA-256 för original, råa avstånd, rangordning och slumpfrö för showens kandidatordning.

## 6. Presentation och dramaturgi

### Visuell identitet
- Första skärmen: extremt enkel, nästan myndighetslik svensk formgivning. Stor typografi: **RITA EN GENOMSNITTSTOMTE.**
- Analysläge: 90-tals-/tidigt 2000-tals kriminalteknik. Mörk bakgrund, dämpat grönt/cyan, raster, hårkors, UI-rutor, exakt typografi.
- Snygg, medveten retrodesign – inte plottrig hackerparodi. Viktigt att skala bra till 16:9-projektor.
- Originalbilder och medelbild ska alltid vara visuellt tydliga och stora.

### Showsekvens
0. **STANDBY:** Projektor visar en neutral titel utan vinnare eller rankning.
1. **ANALYZING:** Börjar direkt när arrangören klickar på `Beräkna och starta show`; visar riktiga statussteg/progress från backend, inte falska procentsiffror.
2. **COMPOSITE:** Ett bildlager byggs upp av de faktiska teckningarna i en fixerad, sparad slumpordning. Beräkna gärna progressiva medelbilder för flera stadier och interpolera visuellt mellan dem; avsluta med `average_raw` och sedan en varsam visningsförstärkning. Inget krav på avancerad geometrisk bildmorphing som hittar på innehåll.
3. **IDENTIFY:** Kandidaterna passerar snabbt i ett avgränsat centralt fönster eller band med stabil bakgrund, skanningsramar och metadata. Visa minst varje godkänd bild en gång innan avslöjandet om tidsramen tillåter.
4. **NARROWING:** Ett mindre antal verkliga toppkandidater återstår. Visa inga ogrundade match-% och undvik att avslöja vinnaren i förtid.
5. **MATCH FOUND:** Kort ljud/visuell låsning, sedan stor vinnarteckning, ID/namn, `MEST GENOMSNITTLIG`, medelbilden bredvid.
6. **RESULT:** Visa topp 5, mest avvikande, galleri och en kort metodförklaring.

### Tidsstyrning och säkerhet
- Sätt konfigurerbara startvärden: composite 7 s, kandidatsekvens 12–20 s, narrowing 5 s, reveal 4 s; låt beräkningsfasen ta den verkliga tid som krävs.
- Vid 75 bilder bör kandidatflödet använda mindre bilder/thumbnailband, inte hårda helskärmsblinkningar. Undvik stroboskopeffekter och kraftiga luminansskiften; respektera `prefers-reduced-motion`.
- Ljud kan vara valfritt och avslaget från start (egenproducerade enkla UI-ljud, ingen upphovsrättsskyddad musik).
- Admin kan starta, pausa, återuppta, hoppa fram, spela om och återställa. Repris ska använda **samma analysresultat**.
- Resultatet får inte exponeras av misstag i projektorvyn före reveal. Admin kan se hela resultatet först i en separat panel.

## 7. Informationsarkitektur och UI

**`/control`** (arrangören):
- Session, antal bidrag och status.
- Ritmall/utskrift.
- Import, individuella thumbnails, labels, exkludering och status (`ok`, `needs_review`, `excluded`).
- Manuell hörnjustering för felaktiga foton.
- `Beräkna och starta show` samt `Beräkna endast`.
- Presentationskontroller, fullskärm/projektorlänk.
- Resultatgranskning och export.
- Radering med bekräftelse.

**`/show`** (publiken):
- Projektoranpassat 16:9 med bra läsbarhet på avstånd; ingen admin-/debugtext.
- Standby, analys, genomsnittsuppbyggnad, kandidatsökning, final, resultatskärm.
- Sömlös uppdatering från serverns session/show-state, även vid omladdning.

**`/print`**: utskrivbar A4-ritmall.

## 8. Teknisk arkitektur

### Stack
- **Frontend:** React + TypeScript + Vite. CSS/Canvas för animationer; använd ett animationsbibliotek endast om det ger konkret värde.
- **Backend:** Python 3.11+ och FastAPI, kör lokalt.
- **Bildbehandling:** NumPy, OpenCV (inklusive ArUco), Pillow; eventuellt scikit-image för diagnostiska metrikjämförelser, inte som nödvändigt beroende om OpenCV/NumPy räcker.
- **Lagring:** Lokal sessionsmapp med bilder, JSON-manifest och beräknade artefakter. Ingen extern databas behövs för en användare och en fest.
- **Paketering:** Ett produktionsbygge av Vite serveras från samma FastAPI-origin; ett startskript för Windows PowerShell och ett för macOS/Linux. Förbered beroenden när internet finns; runtime måste fungera offline.
- **Kommunikation:** REST för upload/metadata/analys; serverlagrat presentationstillstånd och kort pollingintervall (~0,5–1 s) för separation mellan admin- och projektorfönster. WebSocket inte nödvändigt i V1.

### Blockdiagram

```text
             Arrangör: /control              Projektor: /show
                      |                             |
                      +---------- HTTP ------------+
                                     |
                         FastAPI (localhost)
                                     |
              +----------------------+---------------------+
              |                      |                     |
         Sessions-/API          Analysjobb          Show state
              |                      |                     |
       data/<session>/         OpenCV / NumPy      Faser/tidsstämplar
              |                      |
       original + preview       inkmaps, average,
       corners + metadata       ranking, exports
```

### Förenklad katalogstruktur

```text
medeltomten/
  frontend/
    src/
      pages/{ControlPage,ShowPage,PrintPage}.tsx
      components/
      show/
      api/
    package.json
  backend/
    app/
      main.py
      api/
      imaging/{registration,normalization,average,scoring}.py
      services/{sessions,analysis_jobs,presentation}.py
      models/
    tests/
    requirements.txt
  scripts/{start.ps1,start.sh}
  data/                  # gitignored
  README.md
```

### API-kontrakt (kan förfinas i implementationen)

```text
POST   /api/sessions
GET    /api/sessions/{id}
POST   /api/sessions/{id}/drawings       multipart, en eller flera bilder
PATCH  /api/sessions/{id}/drawings/{drawingId}
POST   /api/sessions/{id}/analyze
GET    /api/sessions/{id}/analysis
GET    /api/sessions/{id}/results
GET    /api/sessions/{id}/presentation
POST   /api/sessions/{id}/presentation    start|pause|resume|advance|replay|reset
GET    /api/sessions/{id}/assets/{assetId}
DELETE /api/sessions/{id}                 explicit bekräftelse i UI
GET    /api/health
```

`GET /analysis` bör ge `queued|running|completed|failed`, faktisk progress där den går att mäta, aktuellt steg och användbar felinformation. `GET /results` ger original-ID, rank, distance och asset-referenser. `GET /presentation` innehåller aktuell fas, start-/pausstatus och tidsankare så att projektorvyn överlever omladdning. Håll bild-URL:er inom appens asset-endpoint och validera ID, filtyp och filstorlek.

### Resurskrav och robusthet
- Batchuppladdningar i flera omgångar; tillåt upp till cirka 100 bidrag och gör 40–75 till rekommenderat intervall, inte ett hårt villkor.
- Sätt dokumenterade rimliga filgränser (förslagsvis 20 MB per bild) och bearbeta stora original i begränsad minnesbudget.
- Gör analysen asynkront från UI via backend-jobb så att HTTP-anrop och projektorvy inte hänger sig.
- Undvik att importera/dekoda alla högupplösta original samtidigt; arbeta med nedskalade arbetskopior och thumbnails.
- Autospara sessionsstatus och mellanresultat atomärt; vid omstart ska appen kunna läsa tidigare session och visa begripligt läge.
- Ingen extern CDN, Google Fonts, API, analytics eller modellnedladdning vid runtime.
- Lokalt bind till `127.0.0.1` som standard. Exponera inte nätverksinterface utan explicit val.

## 9. Verifiering och acceptanskriterier

### Unit tests
- Exakt pixelmedelvärde på syntetiska små matriser.
- Reproducerbar ranking på kontrollerade exempel: identiska bilder ger lika score; en konstruerat närmare medelbild placerar sig bättre än en avvikare; stabil tie-break.
- Markörbaserad homografiregistrering på genererade A4-bilder som roterats/perspektivförvrängts.
- Bildbehandlingen ignorerar markörer och malltext.
- Avvisning/flaggning av tom, suddig eller ofullständig bild, utan tyst bortfall.
- Medelbild med display-förstärkning påverkar inte score.

### Integration/UI tests
- 40, 75 och 100 syntetiska testbilder kan importeras och analyseras utan minneskrasch.
- Manuellt rättade hörn leder till ny normalisering och resultat uppdateras först efter ny analys.
- Admin/show synkas i olika fönster; projektion visar inte vinnaren före reveal.
- Paus, fortsätt, hoppa, repris och sidomladdning fungerar.
- Vid ofullständigt uppladdningssteg kan giltiga bidrag behållas.
- Exporten innehåller verkliga distanser, algoritmversion och de identifierare som visats i appen.
- Appen kör efter bygg/installation med internet frånkopplat.

### Definition of Done
1. Körbara och dokumenterade kommandon för installation, lokal drift, test och produktionsbygge.
2. Fungerande ritmall och import-/granskningsflöde.
3. Verklig matematisk genomsnittsbild och en deterministisk vinnare.
4. Fungerande fullskärmsshow på separat display, med dramatisk men trovärdig reveal.
5. Automatiserade tester passerar och ett dokumenterat end-to-end-demo med syntetiska teckningar går att köra.
6. Inga låtsasvärden, placeholders, externa beroenden i runtime eller dolda fel som blockerar själva aktiviteten.

## 10. Teknisk riskanalys

| Risk | Åtgärd |
|---|---|
| Bilderna är olika beskurna/roterade | Utskriven mall med fyra ArUco-markörer; manuell fyrhörnskorrigering |
| Svaga blyertsstreck/fotoljus ger inkonsekvent bläckkarta | Varsam bakgrundskorrigering, preview och varningsstatus |
| Rå genomsnittsbild blir suddig | Visa den ärligt samt en separat display-förstärkt version |
| Ranking premierar nästan tom teckning | Kvalitetsflaggor och validering på verkliga exempel före festen |
| Tung import fryser UI eller tar mycket RAM | Backend-jobb, thumbnails, nedskalade kopior, begränsade batchar |
| App eller projektor tappar state | Sessionsmanifest, serverlagrad show state, polling, återupptag |
| Visuell effekt feltolkas som falsk AI-precision | Visa aldrig ogrundad konfidens; metodpanel efter avslöjandet |
| Stroboskopliknande animation | Konstanta bakgrunder, avgränsad kandidatvy, reducerad rörelse |

## 11. Prioritering för implementering

**Fas A — Fungerande kärna:** ritmall, import, registrering/manuell fallback, medelvärde, ranking, tester.

**Fas B — Användbar eventapp:** control/show, lokal session, synkronisering, presentation, export.

**Fas C — Polering:** finare CSI-typografi/animationer, egen UI-ljuddesign, responsivitet, test med realistiska foton och Windows-laptop/projektor.

Faserna beskriver arbetsordning **inom samma genomförande**, inte tre separata förslag eller påhittade redan implementerade funktioner.