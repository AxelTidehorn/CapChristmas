# Uppdrag till Claude — Bygg MEDELTOMTEN

Du ska **implementera en fullt fungerande webbapp**, inte bara ge förslag, skriva en plan, skapa issues eller producera en mockup.

**Primär kravspecifikation:** Läs den bifogade filen `PRODUKTSPEC.md` i sin helhet och använd den som produktens source of truth. Detta meddelande anger implementationens arbetssätt och prioriteringar. Om det finns en teknisk detalj som är oklar, gör ett rimligt val som uppfyller syftet och dokumentera valet i README/ADR. Stanna inte vid en fråga om mindre designbeslut.

## Vad du bygger

En lokalt körbar, svenskspråkig webbapp kallad **MEDELTOMTEN** för en julfest med ungefär 40–75 personer. Alla ritar varsin jultomte på papper. En arrangör laddar upp fotografier av teckningarna. Appen rätar upp bilderna med en utskrivbar A4-mall med referensmarkörer (samt manuell fallback), beräknar en **äkta pixelbaserad genomsnittstomte**, rangordnar varje teckning efter reproducerbart flerskaligt avstånd till medelbilden och avslöjar vinnaren i en snygg, överdriven CSI-inspirerad liveshow för projektor.

Uppgiftstext på svenska:
> **Rita en genomsnittstomte.**  
> Du har fem minuter på dig att rita en så genomsnittlig jultomte som möjligt. Din teckning kommer att analyseras. Bedömningskriterierna offentliggörs efter avslutad uppgift.

Det ska vara en riktig app med riktig analys. **Använd inte generativ AI för att skapa medelbilden. Fejka inte matchningsresultat, score eller framsteg.** Visa det matematiskt beräknade resultatet. Under showen är teatrala animationer och snabb bildväxling tillåtna; de får aldrig påverka rankningen.

## Teknik och grundkrav

- React, TypeScript och Vite i frontend.
- Python 3.11+, FastAPI, NumPy, OpenCV (ArUco) och Pillow i backend. Lägg bara till beroenden som behövs.
- En lokal server kör analysen; appen fungerar offline efter installation och bygge. Inga externa API:er/CDN/modeller/fonts/analytics i runtime.
- Separat `/control` för arrangör, `/show` för projektor och `/print` för A4-mall.
- Lokala sessionsfiler; enkel manifestbaserad persistence är tillräcklig. Filer ska vara gitignored och möjliga att radera via UI.
- Backend-jobb eller bakgrundsarbete utan att blockera HTTP/UI; faktisk status/progress till frontend.
- Separat projektorfönster synkat med adminens kommandon via serverlagrat state och polling/SSE (välj den enklaste pålitliga lösningen).
- Körbar och dokumenterad på Windows, gärna även macOS/Linux. Ge scripts för start och tydlig instruktion för offlinekörning.

## Funktioner som måste vara verkligt färdiga

1. **Ritmall:** Utskrivbar svartvit A4-mall med stor, definierad rityta och fyra tydliga unika ArUco-markörer utanför ytan. Mallens markeringskoordinater finns i kod och används konsekvent vid bildregistrering.
2. **Uppladdning:** Flera bilder samtidigt (JPG, PNG, WebP), thumbnails, ID/etikett, totalsumma, kvalitetsstatus, avvisning med felmeddelande, batchar som kan fyllas på.
3. **Bildregistrering:** EXIF-rotation, detektion av 4 markörer, homografi, exakt utskärning av rityta. Tydlig `needs_review` och UI där arrangören manuellt drar fyra hörn/markerade referenspunkter när markörer saknas. Granskade bilder får granskas i original och normaliserat skick.
4. **Normalisering:** Fast upplösning/koordinatsystem för alla. Mild bakgrunds-/ljuskorrigering. Skapa kontinuerliga grayscale ink maps med bevarade linjer. Maskera bort all malltext och alla markörer. Flagga uppenbart tomma eller felaktiga bidrag för granskning, utan att tyst kassera dem.
5. **Verkligt genomsnitt:** `M = mean(I_i)` över giltiga bilder. Exportera oförvanskad medelbild plus separat förstärkt presentationsversion. Beräkna inte genomsnittet från förminskade HTML-thumbnails.
6. **Ranking:** Deterministiskt flerskaligt avstånd till M enligt produktspecen, med fasta dokumenterade parametrar och tie-break. Spara rå distance per bidrag, topp 5 och mest avvikande. Inga osakliga AI-confidence-percent.
7. **Show:** Fullskärm med två olika visuella personligheter: torr svensk uppgiftsintroduktion, följt av mörk retrokriminalteknisk analys. Direkt när `Beräkna och starta show` klickas måste projektorn gå till analysläge. När analysen är klar byggs medeltomten successivt fram ur faktiska bilder (progressiva medel eller crossfades; ingen falsk genererad tomte), därefter flashar/korsjämförs riktiga kandidatteckningar i en CSI-liknande sekvens, sedan toppkandidater och **MATCH FOUND** på rätt vinnare.
8. **Presentationstyrning:** Start, pausa, fortsätt, hoppa fram, spela om och återställ. Projektorvyn får aldrig visa slutligt resultat före reveal, inklusive vid reload. Mjuk bildväxling utan stroboskop; stöd för `prefers-reduced-motion`. Ljud är valfritt och avstängt som standard.
9. **Resultat och export:** Äkta medeltomte bredvid vinnaren, topp 5, mest avvikande, galleri, begriplig metodförklaring, bildexport och JSON/CSV med ranking, metodversion och exkluderingar.
10. **Robusthet:** Sessionen går att återuppta efter omladdning; dokumentera hur data tas bort; felaktigt foto kan rättas utan att allt måste importeras igen. Undvik att läsa alla högupplösta original till RAM samtidigt.
11. **Demo/test:** Lägg in ett tydligt separat demo/testläge med syntetiskt genererade tomtliknande teckningar och/eller medföljande fixtures. Demonstrationen får aldrig påstå att dessa är riktiga deltagare.

## Visuell ambitionsnivå

Gör gränssnittet attraktivt och genomarbetat, inte ett generiskt dashboard-UI. Projektorläget ska kännas som ett nischat kriminaltekniskt instrument från sent 90-tal/tidigt 00-tal. Typografin, grid, indikatorer och skanningsanimationer ska kännas avsiktliga. Stor läsbar text, tydliga originalteckningar och fin 16:9-komposition. Minimera onödig chrome i showvyn. Behåll svensk text för uppgift och slutresultat; använd gärna korta engelska systemtermer som `COMPOSITE BUILD`, `SUBJECT SEARCH`, `MATCH FOUND` i analyssekvensen.

**Det som är roligt är kontrasten:** det löjligt enkla uppdraget `Rita en genomsnittstomte` behandlas med gravallvarlig, överteknisk precision.

## Arbetssätt — mycket viktigt

1. Inspektera aktuell arbetskatalog/repo först: läs README, AGENTS.md, eventuell befintlig arkitektur och relevant kod. **Anta inte att appen redan finns.** Om det är ett tomt projekt, skapa en tydlig `medeltomten/`-struktur eller använd aktiv projektrot. Respektera befintlig arkitektur om den finns.
2. Skriv en kort konkret implementationplan utifrån produktspecen, men **fortsätt sedan direkt med att implementera**. Stanna inte vid en spec eller TODO-lista.
3. Bygg först ett vertikalt fungerande flöde: mall -> bild -> normaliserad ink map -> medelbild -> rankad vinnare. Lägg sedan på admin, projector, show och export. Prioritera riktig funktion över kosmetik om något måste förenklas.
4. Ha en tydlig modulgräns mellan matematik/bildbehandling och presentationsanimation. Showen får endast läsa beräknade resultat, aldrig skapa egna vinnare eller rankingtal.
5. Implementera en manual fallback och realistisk felhantering; markera oimplementerade utökningar öppet i README istället för att gömma dem bakom låtsasfunktioner.
6. Kör tester, typkontroll, lint och produktionsbygge. Lägg automatiserade tester för average/ranking/registrering, integration av control/show och gärna ett röktest av 75 syntetiska bilder. Kontrollera att frontend och backend verkligen kommunicerar.
7. Dokumentera install/build/run för Windows och hur appen körs utan internet på eventdagen. Ge särskilt checklista: printa mall, testa kamera, kontrollera HDMI/utökad skärm, stäng av uppdateringar, testa show med demo, radera demodata före skarpt läge.
8. Avsluta med en konkret leveransrapport: vad som byggts, vad som testats (med faktiska testkommandon/resultat), vad som inte kunde verifieras, kända risker och exakt hur jag startar och använder appen.

**Git-disciplin:** Gör arbetet i den aktuella arbetskatalogen. Om du befinner dig i ett befintligt repo, skapa en separat arbetsbranch och följ dess instruktioner. Ändra inte orelaterade filer. **Pusha, merga eller skapa inte en PR utan uttrycklig instruktion.** Skapa inga issues istället för implementation.

## Acceptanskriterier

- Jag kan från tomt tillstånd importera 75 riktiga eller syntetiska teckningar, granska dem, analysera och få fram en kontrollerbar `average_raw` och ett deterministiskt vinnande bidrag.
- Det finns en fungerande `Skriv ut ritmall`-funktion och minst en testad automatisk markörregistrering samt manuell korrigering.
- Admin på min laptops skärm kan styra en separat 16:9-projektorvy som genomför hela CSI-showen och aldrig råkar avslöja vinnaren för tidigt.
- Jag kan exportera resultat och spela om showen utan ny analys.
- En fullt dokumenterad lokal körning fungerar utan internet efter installation.
- Tester och build passerar; om inte, rapportera exakt vilka moment som misslyckades. Ingen demodata får presenteras som riktig analys.

**Börja nu med att inspektera arbetskatalogen, läs produktspecen och implementera appen.**