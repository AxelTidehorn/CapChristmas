# MEDELTOMTEN

Lokal webbapp för julfesten. **V2** analyserar alla inkluderade teckningar med multimodal AI, bygger en
sammanhängande genomsnittstomte från gruppens konsensus och matchar originalen mot den godkända bilden.
Arrangören granskar konsensus, bildversion och vinnare. Den färdiga CSI-showen fungerar helt offline.

**AI-förberedelsen kräver internet, en serverkonfigurerad API-nyckel och API-saldo.** Det separata
**legacy-läget V1** behåller det helt lokala pixelmedelvärdet och den deterministiska pixelrankingen.

Läs [V2: konfiguration, metod, API-källor och kostnader](docs/V2.md) samt
[faktisk verifiering och kvarvarande begränsningar](docs/VERIFIERING-V2.md).
V2 implementerar [issue #3](https://github.com/AxelTidehorn/CapChristmas/issues/3) och bygger på den faktiska
V1-koden i [draft PR #2](https://github.com/AxelTidehorn/CapChristmas/pull/2). Den historiska
[produktspecifikationen](docs/PRODUKTSPEC.md) nedan beskriver V1; issue #3 ersätter dess produktkrav på publik
pixelmedelbild och offline-analys för V2.

## Installation utan Node.js på eventdatorn

Ett **färdigbyggt paket** innehåller `frontend/dist`. Då behöver datorn bara Python 3.11+;
installationsskripten installerar Python-paketen och hoppar över Node helt. Konfigurera `.env`
och kör sedan det vanliga startskriptet. GitHubs vanliga **Download ZIP** innehåller enbart
källkod och saknar dessa byggda filer.

Paketet byggs på en utvecklingsdator med Node och Git:

```bash
python scripts/build-package.py /tmp/CapChristmas-Windows.zip
```

Packa upp hela paketet före installation. Läs `LAS-MIG.txt` i paketet. Utvecklare som behöver
pytest installerar separat `backend/requirements-dev.txt`; vanligt appbruk kräver inte testverktygen.

## Snabbstart (Windows)

Kräver Python 3.11+ (python.org, med `py`-launchern) och Node.js 20+.

**1. Installera – en gång, med internet:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

Skapar `.venv`, installerar Python-paketen, kör `npm ci` och bygger frontend till `frontend/dist`.

**2. Konfigurera AI (för V2):** Kopiera `.env.example` till `.env`, fyll i `OPENAI_API_KEY` på servern och läs [V2-guiden](docs/V2.md). Hoppa över detta för legacy eller repris av en färdig show.

**3. Starta – showen fungerar utan internet:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

Öppnar `http://127.0.0.1:8000/control`. Servern binder endast till `127.0.0.1`. Annan port: `$env:MEDELTOMTEN_PORT=8080`.

macOS/Linux: `scripts/install.sh` respektive `scripts/start.sh`.

Inga CDN, externa typsnitt eller analytics. Bilder och frontend serveras från samma FastAPI-process. Endast V2-förberedelsen använder externa AI-API:er.

## Sidor

| Sida | Vem | Innehåll |
|---|---|---|
| `/control` | arrangören | sessioner, import, granskning, manuella hörn, analys, showstyrning, resultat, export, radering |
| `/show?session=<id>` | projektorn | publik 16:9-show utan adminknappar. `F` eller dubbelklick = helskärm |
| `/print` | skrivaren | A4-ritmall med fyra ArUco-markörer |

## Eventflöde V2

Importera → granska → analysera gruppen → granska/godkänn konsensus → generera → godkänn bildversion → matcha
→ förhandsgranska/godkänn vinnare → starta show. Kostnadsuppskattning och leverantörsstatus visas i kontrollpanelen.
Varje ny generering beställs uttryckligt. Bytt underlag eller godkänd referens kräver nya steg; gamla bilder sparas.
Förbered i förväg med nätverk och repetera sedan med nätverket avstängt. Använd exporter för referens, rapporter,
provenance och originalgalleri. Fullständig [event- och metodguide](docs/V2.md).

## Eventflöde legacy V1

1. **Förbered:** Skapa session i `/control` (*inte* demoläge). Skriv ut mallar från `/print` (A4, 100 %/faktisk storlek).
2. **Projektor:** Klicka *Öppna projektorvy*, dra fönstret till projektorn, tryck `F`. Standby visar bara uppdraget.
3. **Rita:** fem minuter. Namn/nummer på raden under ramen (utanför analysytan).
4. **Fota:** Rakt ovanifrån räcker inte – det viktiga är att **alla fyra hörnmarkörerna syns** och att bilden är skarp.
5. **Importera:** Dra in bilderna (JPG/PNG/WebP, max 20 MB/st, gärna i flera omgångar). Dubbletter avvisas.
6. **Granska:** Bidrag märkta *Granska* måste få ett manuellt beslut: *Godkänn*, *Justera hörn manuellt* eller *Uteslut* (med anledning). Inget utesluts automatiskt; analysen vägrar starta så länge något är ogranskat.
7. **Beräkna och starta show:** Projektorn går direkt till *ANALYZING* med verklig progress och fortsätter automatiskt genom showen när analysen är klar.
8. **Styr:** Paus / Fortsätt / Nästa fas / Spela om / Återställ. *Spela om* använder samma sparade resultat.
9. **Efteråt:** Resultatpanelen i `/control` – CSV, JSON, medelbilder och galleri-zip.
10. **Städa:** *Radera session* tar bort alla bilder och resultat från disken.

### Eventchecklista

- [ ] `scripts\install.ps1` körd på eventdatorn med internet, och `scripts\start.ps1` testad **med nätverket avstängt**.
- [ ] Skrivit ut mallar (+ reserv). Kontrollera att markörerna i hörnen är skarpa och inte beskurna av skrivaren.
- [ ] Testat kameran/mobilen: fota en ifylld provmall och kontrollera att den blir *Godkänd* med ”ArUco, 4 markörer”.
- [ ] HDMI/projektor i **utökat skrivbord** (inte duplicerat), så att kontrollpanelen inte syns för publiken.
- [ ] Demo-repetition: ny session med *Demoläge*, generera 75 syntetiska teckningar (+ problemfall), kör hela showen.
- [ ] Windows Update, notiser och skärmsläckare pausade; datorn på laddare; energisparläge av.
- [ ] Demosessionen raderad före det skarpa läget (eller skapa en ny, separat session – de blandas aldrig).

## Demoläge

En session skapad med *Demoläge* kan bara innehålla tydligt syntetiska teckningar och en riktig session kan
aldrig ta emot syntetiska (servern avvisar båda). De syntetiska bilderna är renderade mallar med enkla tomtar som
”fotograferas” med perspektiv, rotation, ojämnt ljus och brus, och går genom exakt samma registrering och analys.
Projektorn visar `DEMO · SYNTETISKA TESTTECKNINGAR` under hela showen. Valfria problemfall: tomt ark och ark utan
markörer.

## Legacy-bildanalys (algoritm `medeltomten-v1.0`)

Alla parametrar finns i [`backend/app/config.py`](backend/app/config.py). Ändras något som påverkar resultatet ska
`ALGORITHM_VERSION` höjas – och aldrig efter att en vinnare är känd.

1. **Import:** storlek ≤ 20 MB, avkodat format JPEG/PNG/WebP, skydd mot dekompressionsbomb, EXIF-rotation, SHA-256 på originalet. Arbetskopia ≤ 2400 px + thumbnail; originalet sparas orört.
2. **Registrering:** fyra unika ArUco-markörer (`DICT_4X4_50`, id 0–3) → homografi från alla 16 markörhörn till mallens millimeterkoordinater. Med 3 markörer beräknas den ändå men flaggas. Utan markörer provas försiktig ramdetektion (den tryckta ramen, kontroll av proportioner) som **alltid** skickas till granskning. Annars: manuella fyra hörn.
3. **Utsnitt:** exakt ritytan (170 × 212,5 mm) → 512 × 640 px (warpas i 2× och areanedskalas så tunna blyertsstreck blir grå i stället för att försvinna). Den tryckta ramen ligger 2 mm utanför ritytan och de yttersta ~1,3 mm (4 px) nollställs för alla bidrag lika, så ram, markörer och text aldrig når pixeldatan.
4. **Bläckkarta** `I(x,y) ∈ [0,1]`: lokal pappersnivå skattas med morfologisk stängning (10 mm) med ett golv på 80 % av arkets pappersnivå (så att stora ifyllda ytor inte tolkas som skugga), `ratio = grå/papper`, `I = clip((0,90 − ratio)/0,55, 0, 1)`.
5. **Kvalitetsflaggor** (kräver manuellt beslut): tomt/nästan tomt, mycket svaga streck, suddigt, ovanligt mycket mörk yta, delar av ritytan utanför fotot.
6. **Medelbild:** `M(x,y) = (1/N) Σ I_i(x,y)` i float64 över godkända bidrag. `average_raw.png` är en direkt rendering av M; `average_display.png` är en separat kontraststräckt version enbart för visning.
7. **Avstånd:** `D_i = 0,20·MSE(G4(I_i), G4(M)) + 0,35·MSE(G16(I_i), G16(M)) + 0,45·MSE(G40(I_i), G40(M))`, Gaussisk oskärpa med σ i px vid 512 px bredd, kant = papper (0). Lägst D vinner, högst D = mest avvikande. Lika D (exakt float-likhet) delar rank; ordningen avgörs av bidrags-ID och markeras som delad i export och show.
8. **Reproducerbarhet:** showens kandidatordning och topp-5-blandning seedas av SHA-256 över algoritmversion + originalens hashar – samma indata ger exakt samma resultat (testat).

Resultatet (`data/<session>/analysis/results.json`) innehåller algoritmversion, konfiguration, seed, showordning,
råa distanser och σ-komponenter per bidrag, registreringsmetod, kvalitetsmått, hashar och uteslutna bidrag med anledning.

### Kända begränsningar (ärligt redovisade)

- **Bläckmängd väger tungt.** Måttet jämför pixlar; en tomte med stor ifylld mössa skiljer sig mycket från en ljus medelbild. I demodatan hamnar de ifyllda mössorna längst ner. Det är en egenskap hos V1-metoden, inte ett fel att rätta i efterhand.
- **Nästan tomma ark** kan ligga nära en ljus medelbild. De flaggas därför alltid som *Tomt* och kräver beslut.
- **Placering och storlek inom ritytan är en del av bidraget** – ingen individuell centrering görs (enligt spec).
- **Kvalitetströsklarna** (t.ex. skärpa) är kalibrerade på syntetiska foton. Testa med riktiga foton från eventets kamera före festen; falsklarm kostar bara ett klick (*Godkänn*).
- Ingen OCR av namnraden – etikett skrivs in manuellt vid behov.
- Inga UI-ljud implementerade (specen anger dem som valfria; inget spelas upp).

## Legacy-showen V1

V2 behåller faser/klocka men använder AI-rekonstruktion och godkänd referens i stället, se [V2](docs/V2.md).

Faser och standardtider (`SHOW_PHASES` i config): `ANALYZING` (verklig tid) → `COMPOSITE BUILD` 7 s → `SUBJECT SEARCH` 16 s
→ `NARROWING` 5 s → `MATCH FOUND` 9 s (≈3 s låsning) → `RESULTAT` (står kvar).

- **Läckskydd:** projektorn läser bara `GET /presentation`, som servern fasfiltrerar. Före `MATCH FOUND` innehåller svaret varken vinnare, rank eller distanser – inte heller vid omladdning eller i nätverksfliken. Under *Narrowing* skickas topp 5 i seedad slumpordning.
- **Composite** visar progressiva medelbilder som faktiskt beräknats på de första k bidragen i showordningen (visningsförstärkta, märkta så), sedan rå M och därefter den förstärkta.
- **Subject search** visar varje godkänd teckning minst en gång i ett avgränsat fönster och ett rullande filmband – inga helskärmsblinkningar. `prefers-reduced-motion` stänger av skanningslinje/glidning.
- Showstate (fas, tidsankare, paus) lagras i sessionsmanifestet och överlever omladdning och serveromstart. En analys som avbröts av omstart markeras *misslyckad* och kan köras om.
- Ändras ett bidrag efter analysen märks resultatet *inaktuellt* och showen kan inte startas förrän analysen körts om.

## Arkitektur

```text
backend/app/
  config.py                 versionerad konfiguration (mall, pipeline, scoring, showtider)
  main.py                   FastAPI-routes + servering av frontend/dist
  imaging/                  ren bildmatematik, inga HTTP-beroenden
    template.py             A4-mall (SVG för utskrift + raster för tester) från samma geometri
    registration.py         ArUco/ramdetektion/manuella hörn → homografi → utsnitt
    normalization.py        bläckkarta + kvalitetsmått
    average.py              medelbild + separat visningsförstärkning
    scoring.py              flerskaligt avstånd + deterministisk ranking
    synthetic.py            syntetiska tomtar för demo/tester
  services/
    sessions.py             manifest (atomära skrivningar), import, granskning, assets
    analysis_jobs.py        bakgrundsjobb (en tråd): medel, scoring, export
    presentation.py         showstate + fasfiltrerad publik vy
    ai_jobs.py              V2-jobb, checkpoint, godkännanden och exportdata
  ai/{models,providers}.py  providerprotokoll, scheman, prompts och verkliga REST-adaptrar
frontend/src/
  pages/{ControlPage,ShowPage,PrintPage}.tsx
  components/DrawingModal.tsx   original/normaliserad sida vid sida + hörneditor
  show/Phases.tsx               enbart presentation – läser sparade resultat
  api/client.ts
```

Val och avvikelser från spec:

- **Polling** (projektor 0,5 s, kontroll 0,6–2 s) i stället för SSE – enklast och robust för en användare.
- **Ingen router/animationsbiblioteket**; tre fasta sidor och CSS/React räcker.
- **Import bearbetas synkront per uppladdningsanrop** (i FastAPI:s trådpool, så projektor/API svarar under tiden); frontend laddar upp tre filer åt gången med progress. Analysen körs som bakgrundsjobb.
- `routes` ligger i `main.py` och modeller som JSON-dicts i manifestet i stället för separata `api/`- och `models/`-paket – mindre kod för samma kontrakt.
- `POST /api/sessions/{id}/demo-drawings` och `GET /api/sessions/{id}/export/{results.json|results.csv|gallery.zip}` är tillägg till API-förslaget. `GET /api/sessions` listar sessioner för återupptag.
- `opencv-python-headless` (ArUco ingår i huvudmodulen sedan 4.7).

## Data

Allt lagras lokalt i `data/<session-id>/` (gitignored): `manifest.json`, `drawings/dNNNN/{original.*, work.jpg,
thumb.jpg, preview.png, ink.npy}` och `analysis/`. Radera via *Radera session* i UI (med bekräftelse) eller ta bort
mappen. Annan plats: miljövariabeln `MEDELTOMTEN_DATA`.

## Utveckling och tester

```bash
.venv/bin/python -m pytest backend/tests          # Windows: .venv\Scripts\python -m pytest backend\tests
cd frontend && npm run typecheck && npm run lint && npm run build
```

Dev-läge med hot reload: backend `cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload` och
`cd frontend && npm run dev` (Vite proxar `/api` till port 8000).

V2:s 21 ytterligare tester och det valfria webbläsartestet beskrivs i [verifieringsrapporten](docs/VERIFIERING-V2.md).

V1-backendtesterna täcker exakt medelvärde på små matriser, lika score för identiska bilder och stabil tie-break,
kontrollerade avvikare, att visningsförstärkningen inte används i scoring (omräkning mot sparad rå M ger identiska
tal), ArUco-registrering mot roterade/perspektivförvrängda/sidledes foton, att malltext/ram/markörer inte läcker in,
tomma/suddiga/beskurna/trasiga filer, manuella hörn → ny normalisering → inaktuell analys, uppladdningsvalidering
(storlek, format, dubbletter, EXIF), path traversal, fasfiltrering av projektorn, paus/fortsätt/nästa/repris,
export, radering, omstart under analys, reproducerbarhet och röktest med 40, 75 och 100 syntetiska teckningar.
