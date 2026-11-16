# Implementační plán: formát nahrávky – jeden index a řidší tahy (E1, F1, část D2)

Datum: 16. 11. 2026. Verze plánu: 3. Stav: **P0 až P7 implementováno a commitnuto 16. 11. 2026; neověřené body jsou vyjmenované níže**.

Průběh realizace 16. 11. 2026: R1 až R9 potvrzeny uživatelem („Ano, implementuj“). P0: 458 dotčených testů prošlo před změnou. Převod testů (P5) udělal subagent Opus 5.5 (úsilí high) podle pomocníka `tests/unit/tick_fixtures.py`, kterého jsem mu připravil; jeho změny jsem prošel a celou sadu spustil znovu. Ostatní kroky jsem dělal v hlavní relaci.

Odchylky od plánu:

- **Text časové osy se změnil v jednom místě.** Řádek `DRAW` u tahu štětcem končil „(N points, path in the sidecar)“, nově „(N points, path in frames)“. Jinak je text osy stejný; očekávané texty ve stávajících testech zůstaly.
- **Myš se 125 Hz dává asi 62 bodů za sekundu, ne 50.** Pravidlo z R1 nahrazuje poslední bod, dokud je předposlední mladší než 20 ms; při hlášení po 8 ms se tak bod drží po 16 ms. U myši s 1000 Hz vychází 50 bodů za sekundu.
- **`frames_file` zapisuje jen příkaz `frames`,** ne nástroj MCP: hostitelé MCP soubory číst neumějí, tam zůstává zkrácený výsledek.
- **Snímek bez obrázku** (archivovaná nahrávka) se dál vede v seznamu snímků, nově z indexu; pozná se podle `FrameName.without_image` (dřív `is_sidecar`).
- **Seznam nahrávek v editoru index nečte** (`FrameIndex(..., with_ticks=False)`): potřebuje jen náhledy.
- **Editor odmítne nahrávku bez indexu** už při načtení (`NO_INDEX`), jen když není archivovaná; archivovaná stav tiků nepotřebuje.
- **Testy nezapisují index ručně.** Pomocník `IndexBuilder` přebírá stejné slovníky, jaké testy dřív ukládaly jako sidecary, takže se očekávané výsledky nemusely měnit.
- **Zkouška P6 byla bez kreslení.** Příkaz `record` nemá kreslicí vrstvu; tahy v indexu ověřuje uměle vyrobená dvouhodinová nahrávka a jednotkové testy.

Chyba nalezená zkouškou na skutečných obrazovkách: manifest po zastavení nahrávání četl počet tiků z objektu, který ho neměl (`RecordingSummary`), a nahrávání skončilo chybou. Jednotkové testy to nezachytily; opraveno, `test_recorder_index.py` teď počet tiků v manifestu kontroluje.

Ověření (P6, P7):

| Zkouška | Výsledek |
| --- | --- |
| `ruff check`, `ruff format --check`, celá sada jednotkových testů na Windows | čisté; 1308 testů prošlo |
| Skutečná nahrávka dvou obrazovek, 60 s (`record`) | `frames_info/` obsahuje jen `index.jsonl` (2,2 KiB, 121 tiků); 242 obrázků jako dřív. Sidecary 74sekundové nahrávky měly 424 KiB ve 296 souborech |
| `timeline`, `frames`, `describe` nad ní | fungují; `frames` nemá pole `sidecar`, kurzor je z tiku |
| Render téže nahrávky skutečným FFmpegem | 60,1 s videa, 24 fps, kontrola počtu snímků prošla |
| Editor (okno bez obrazovky) | nahrávka se načte, 121 snímků, kurzor z indexu, data okna Mouse se sestaví |
| Složka bez `index.jsonl` | `timeline` skončí kódem 1 a chybou `NO_INDEX` se srozumitelným textem |
| Uměle vyrobená dvouhodinová nahrávka (14 400 tiků, 150 tahů po 40 bodech, 28 800 obrázků) | index 1 125 KiB; `timeline` 0,77 s napoprvé, 0,72 s podruhé (samotný start příkazu 0,14 s); `frames` 0,35 s. Dřív dopočtených 100 s a 289 KiB kreseb v každém sidecaru |
| `scripts/frame_changes.py` nad skutečnou nahrávkou | běží; druhá obrazovka 50 % shodných snímků, hlavní 0 % |

Neověřeno: kreslení ve skutečném okně s ředěním tahu (jen testy bez obrazovky); editor na skutečné obrazovce; archivace nahrávky v novém formátu skutečným FFmpegem (zkušební nahrávka neměla zvuk, archivaci pokrývají jen jednotkové testy); nástroje MCP nad skutečnou nahrávkou; integrační testy (`WATCH_ME_INTEGRATION=1`), které subagent upravil jen čtením; Linux a macOS.

Řeší nálezy E1 a F1 z [revize ze 14. 11. 2026](watch-me-review-2026-11-14.md) a tu část D2, kterou způsobuje počet souborů. Nález B3 (plný snímek při každém tiku) zůstává otevřený, viz kapitola 6.

Historie verzí:

- **Verze 2** (zadání uživatele ze 16. 11.): bez zpětné kompatibility. Uživatel všechny nahrávky smazal a plugin není nikde nainstalovaný, takže čtení původních sidecarů z kódu zmizí celé.
- **Verze 3** (rozhodnutí uživatele ze 16. 11.): vynechávání nezměněných obrázků z plánu vypadlo. Měření v kapitole 2.2 mu dává nejvýš 13 až 43 % objemu a neslo velkou část rizika plánu. S ním odpadl i obdélník nahrávacího okna, vynucený obrázek po 15 s a pole `image_time_ms`.

## 1. Výsledek a hranice

Po realizaci platí:

1. **Jeden soubor místo sidecarů.** Nahrávka má `frames_info/index.jsonl`: jeden řádek na tik, v něm jen to, co se od minulého tiku změnilo. Soubory `frames_info/<čas>_<obrazovka>.json` už nevznikají.
2. **Tvar je zapsaný jednou.** Geometrie tvaru (i celá cesta tahu štětcem) je v indexu jen v tiku, kdy se tvar objevil. Další tiky nesou nejvýš seznam viditelných id, a to jen když se změnil.
3. **Tah štětcem má nejvýš jeden bod za 20 ms.** První a poslední bod tahu zůstávají vždy.
4. **Stavový řádek nahrávacího okna se mění jednou za vteřinu.**
5. **`timeline` čte jeden soubor.** Text časové osy se nemění.
6. **Obrázky se ukládají jako dnes:** každá obrazovka při každém tiku. Počet souborů nahrávky tím klesne na polovinu.
7. **Formát je jediný.** Všechno čtení stavu jde přes jedno rozhraní nad indexem. Kód, který četl sidecary, zmizí; složka bez indexu se ohlásí jednou jasnou chybou.

Mimo rozsah: vynechávání nezměněných obrázků a ukládání jen změněných částí obrazovky (B3, viz kapitola 6), sken seznamu nahrávek v pracovním vlákně a ukládání velikosti a prvního řádku přepisu (zbytek D2), mezipaměť textu osy v `agent/timeline.txt` a stránkování v MCP (zbytek F1), ředění překreslování při kreslení (E2).

## 2. Zjištění

### 2.1 Aktuální kód

Úplný soupis míst, která na dnešním rozložení závisí, udělal pomocný agent; klíčová místa jsem po něm ověřil.

- **Zápis:** `capture/recorder.py:908-935` (`_write_tick`) zakóduje a zapíše obrázek každé obrazovky a k němu sidecar. Běží ve fondu čtyř vláken (`ENCODE_WORKERS`, až 8 tiků rozpracovaných), takže tiky končí mimo pořadí. Stav tiku (kurzor, kresby, zoom, pozadí, mřížka, schránka) sbírá snímací vlákno v `_grab_tick` (`:856-906`).
- **Tvary:** každý tvar má `id`, `started_ms` a `finished_ms` (`ui/overlay.py:377-384`). Bod tahu se přidává při každé události pohybu myši na dvou místech (`ui/overlay.py:1169`, `:1212`).
- **Časová osa:** `host/events.py:249-271` bere seznam tiků ze jmen souborů a pro každý tik otevře jeden sidecar (první obrazovky, která v tiku soubor má). Z téhož seznamu jsou časy „frames before / after“ u řádků `DRAW` a u myši.
- **Kurzor:** render čte jednu polohu na plánovaný obrázek ze sidecaru (`export/plan.py:109-119`, `:137-167`), náhled editoru čte sidecar zobrazeného obrázku (`editor/recording.py:305-320`), `frames --screen cursor` bere kurzor z posledního souboru první obrazovky (`host/runner.py:580-583`).
- **Schránka:** zapisuje se do jediného tiku; okno Mouse v editoru kvůli ní čte jeden sidecar na tik (`editor/mouse_details.py:132-154`).
- **Mřížka** je v sidecaru zvlášť pro každou obrazovku; časová osa čte jen hodnotu první obrazovky (`host/events.py:634-638`).
- **Archivace:** maže `frames/`, `frames_info/` nechává; po archivaci se seznam snímků bere ze sidecarů (`host/runner.py:495-504`).
- **Obnova po pádu:** interval snímání a počet snímků odvozuje ze souborů (`host/recovery.py:144-150`, `:182-185`).
- **Nahrávací okno** obnovuje text každých 200 ms (`ui/control_window.py:87`, `:1122-1170`).
- **Co vidí agent:** `frames` vrací u každého snímku `image` a `sidecar` (cesty) a obsah sidecaru; skill na sidecar odkazuje na třech místech (`skills/watch-me/SKILL.md:200-202`, `:322`, `:332-335`). `describe`, `status` a `wait` vracejí `frames_dir` a `frames_info_dir`. `timeline` žádné cesty do `frames/` nevrací.
- **Testy:** nahrávky pro testy vyrábí pět pomocných funkcí `make_recording` (`tests/unit/test_editor.py`, `test_events.py`, `test_runner.py`, `test_mcp_server.py`, `test_export_ffmpeg.py`), které zapisují sidecary; používá je asi 25 dalších testovacích souborů.

### 2.2 Pokusy (Windows 11, tento stroj, 16. 11. 2026)

Tři skutečné nahrávky ve `Videos/WatchMe` (20 s, 74 s a 76 s, obrazovky 2560×1600 a 1920×1080, 500 ms, JPEG 70); uživatel je po měření smazal, takže čísla už nejde zopakovat na stejných datech:

| Měření | Hlavní obrazovka | Druhá obrazovka |
| --- | --- | --- |
| Snímky bajt po bajtu shodné s předchozím | 0 %, 0 %, 7 % | 38 %, 45 %, 49 % |
| Beze změny mimo místa, která se mění ve více než čtvrtině tiků | 8 %, 27 %, 37 % | 77 %, 80 %, 87 % |
| Podíl změněných dlaždic 32×32 na tik (medián) | 0,2 až 0,7 % | 0 až 0,05 % |

Místa, která se mění skoro pořád: nahrávací okno (v jedné nahrávce 37 z 39 tiků), roh hlavního panelu s hodinami a jednou pruh 576×64, který se měnil v každém tiku.

| Pokus | Výsledek |
| --- | --- |
| Velikost sidecarů 74sekundové nahrávky | 424 KiB ve 296 souborech |
| První volání `timeline` na téže nahrávce (z revize) | 1,56 s, opakované 0,43 s |
| Porovnání dvou shodných snímků 2560×1600 (16 MB) | 0,8 ms |
| Seznam pro concat, v němž jeden obrázek stojí 60 s, výstup 24 fps | 1 476 snímků z očekávaných 1 476; ve 30. s je správný obrázek |

Závěry:

- **Index řeší počet souborů se stavem a čtení osy úplně.**
- **Vynechávání celých shodných obrazovek by na těchto nahrávkách ubralo nejvýš 13 až 43 % objemu.** Hlavní obrazovka tvoří 70 až 87 % bajtů a skoro pořád se na ní mění něco malého. Proto z plánu vypadlo (verze 3).
- **Kdyby se k němu plán někdy vrátil,** dva poslední pokusy říkají, že porovnání je levné a že render s řídkými obrázky funguje bez změny cesty do FFmpegu.

## 3. Rozhodnutí

- **R1 – ředění tahu podle zadání.** Při pohybu myši: když od posledního bodu uplynulo nejvýš 20 ms a od předposledního také nejvýš 20 ms, poslední bod se nahradí aktuální polohou; jinak se bod přidá. První bod (stisk) se nenahrazuje, poslední poloha při puštění tlačítka se vždy zapíše. Časy bodů se drží jen v paměti, do JSONu nejdou.
- **R2 – index `frames_info/index.jsonl`.** JSON Lines, jen připisování. První řádek je hlavička (`v: 3`, interval, formát obrázků, obrazovky). Pak jeden řádek na každý uložený tik: vždy `t`, ostatní klíče jen při změně proti předchozímu tiku: `cursor`, `shapes` (plné definice nových nebo změněných tvarů), `visible` (seznam id na obrazovce), `drawing_now`, `zoom`, `background`, `grid` (mapa obrazovka → rozteč), `grid_source`, `clipboard` (jen v tiku, kdy vznikl), `failed` (obrazovky, které se nepodařilo sejmout). Řádek pro tik beze změny je `{"t": 12500}`.
- **R3 – index píše snímací vlákno.** Jen tak jsou řádky v pořadí tiků. Po každém řádku `flush`. Čtenář nedopsaný poslední řádek přeskočí.
- **R4 – obrázky se v indexu neevidují.** Který obrázek platí v čase T, se dál zjišťuje výpisem `frames/` (poslední soubor obrazovky s časem ≤ T). Index tak nezávisí na tom, kdy a jestli fond vláken obrázek dopsal, a vynechávání obrázků půjde později přidat bez změny formátu.
- **R5 – jedno rozhraní pro čtení stavu tiků.** Nový `core/tick_index.py` vrací pro čas nebo rozsah úplný stav tiku ve stejném tvaru, jaký dnes drží sidecar, takže se kód, který stav zpracovává, měnit nemusí. Všichni čtenáři přejdou na toto rozhraní; nikdo jiný soubory ve `frames_info/` neotevírá. Když `index.jsonl` chybí, rozhraní skončí chybou `NO_INDEX` („nahrávka nemá index; vznikla starší verzí nebo je poškozená“).
- **R6 – stavový řádek jednou za vteřinu.** Časovač 200 ms zůstává (hlídá chyby a konec nahrávání), ale text se přepíše jen při změně celé vteřiny nebo stavu (pauza, varování).
- **R7 – kurzor z tiků.** Render, náhled editoru i `frames --screen cursor` berou polohu kurzoru z indexu podle času, ne ze souboru vedle obrázku. Dnes je to totéž (obrázek je v každém tiku); čtení tím nezávisí na tom, jestli obrázek existuje.
- **R8 – výstup pro agenta.** Text `timeline` se nemění. Z položek ve `frames` zmizí pole `sidecar`; ostatní pole zůstávají. Když je výsledek zkrácený, celý se zapíše do `agent/frames.json` a výsledek na něj odkáže (`frames_file`), stejně jako to dělá `timeline`.
- **R9 – bez zpětné kompatibility.** Čtení sidecarů se odstraní: `sidecar_filename`, `sidecar_cursor_reader`, čtení kurzoru a schránky ze souborů a záložní seznam snímků archivované nahrávky ze sidecarů. Manifest dostane `frames.ticks` (počet uložených tiků) a `frames.info: "index"`; `SCHEMA_VERSION` 3. `frames.count` a „N frames“ v okně znamenají počet obrázků jako dnes.

## 4. Kroky realizace

Pořadí je závazné; každý krok končí zelenými testy a nahrávač po každém kroku vyrábí použitelnou nahrávku. Kroky označené *(subagent)* jsou mechanické a hlídané testy, ostatní dělám v hlavní relaci.

### P0 – výchozí stav

Spustit a zapsat: `tests/unit/test_recorder_sidecars.py`, `test_pause_mute.py`, `test_resilience.py`, `test_events.py`, `test_runner.py`, `test_mcp_server.py`, `test_export.py`, `test_export_ffmpeg.py`, `test_archive.py`, `test_editor.py`, `test_editor_mouse_details.py`, `test_editor_preview.py`, `test_ui.py`, `test_core.py`, testy kreslicí vrstvy (`test_overlay*.py`), `test_cli_agent_files.py`, `test_mouse_timeline.py`. Že se text osy nezměnil, hlídají očekávané texty ve stávajících testech, které P3 nechává beze změny.

### P1 – stavový řádek a ředění tahu (`ui/control_window.py`, nový `core/stroke.py`, `ui/overlay.py`) *(čistá funkce subagent, napojení já)*

1. `ControlWindow._tick`: text skládat jako dnes, ale `setText` volat jen při změně vteřiny nebo stavu.
2. `add_point(points, times, pos, now_ms, min_gap_ms=20)` podle R1 a `finish(points, times, pos, now_ms)` pro puštění tlačítka.
3. Obě místa, kde se bod přidává (`overlay.py:1169`, `:1212`), volají tyto funkce. Čas pro ředění je monotónní čas procesu, ne hodiny nahrávky: ty při pauze stojí a mimo nahrávání nejsou (`_now_ms` vrací `None`).
4. Testy funkce: myš se 125 Hz a s 1000 Hz po dobu 1 s dá nejvýš 51 bodů; první a poslední bod jsou přesně zadané polohy; pomalý tah (body po 50 ms) se neředí; dva body do 20 ms po stisku stisk nepřepíšou.
5. Test vrstvy: nakreslený tah má v `drawings()` zředěnou cestu.
6. Test okna: text se za vteřinu přepíše jednou; přechod do pauzy ho přepíše hned.

### P2 – index: zápis a čtení (nový `core/tick_index.py`)

1. `TickIndexWriter(path, header)`: `write(tick_state)` porovná s předchozím stavem a připíše řádek podle R2; tvary podle `id` a obsahu (změněný tvar se zapíše znovu celý).
2. `TickIndex.load(info_dir)`: přečte `index.jsonl` jedním průchodem, drží časy tiků a pro každý tik úplný stav (složený z rozdílů; tvary sdílené odkazem). Rozhraní: `times`, `state_at(t)` (poslední tik ≤ t), `states(first, last)`, `clipboard_changes()`, `failed(t)`.
3. Chybějící soubor dá `NO_INDEX` (R5).
4. Testy:
   - **zápis a čtení:** posloupnost tiků (kurzor, tvary přibývají a mizí, zoom, mřížka na dvou obrazovkách, schránka, pauza) zapsaná do indexu se přečte jako stejné úplné stavy, jaké šly do zápisu;
   - tvar se 400 body je v souboru jednou, i když je vidět 1 000 tiků;
   - nedopsaný poslední řádek se přeskočí, ostatní tiky zůstanou;
   - index dvouhodinové nahrávky (14 400 tiků) se načte do 0,5 s.

### P3 – nahrávač píše index, čtenáři čtou přes rozhraní

Obrázky se ukládají při každém tiku jako dnes. Mění se jen to, kde je stav.

1. `capture/recorder.py`: snímací vlákno po `_grab_tick` zapíše řádek indexu; `_write_tick` už sidecar nepíše. Schránka se dál bere jen v tiku, který se uloží. Obrazovky, které se nepodařilo sejmout, jdou do `failed`.
2. `host/events.py`: `_load_ticks` nahradí `TickIndex.load(...).states(...)`; časy tiků pro „frames before / after“ jsou z indexu. Hodnota mřížky zůstává z první obrazovky jako dnes, aby se text osy nezměnil.
3. `host/runner.py`: `FrameRef` dostane stav tiku místo cesty k sidecaru; `frames_at` bere kurzor a `cursor_screen` z tiku v čase `--at`; pole `sidecar` zmizí. `FrameIndex` zůstává jen pro obrázky a přestane vypisovat `frames_info/`; seznam časů archivované nahrávky je z indexu.
4. `host/mcp_server.py`: `_frame_from_path` a `tool_get_frame` berou stav z rozhraní.
5. `editor/recording.py`: `cursor_at` čte z rozhraní. `editor/mouse_details.py`: `read_clipboard_changes` přes `clipboard_changes()`.
6. `export/plan.py`, `export/ffmpeg_export.py`: `cursor_keyframes` dostane seznam (čas, kurzor) z tiků rozsahu; `sidecar_cursor_reader` a `PlannedFrame.sidecar` se odstraní.
7. `host/recovery.py`: interval z hlavičky indexu, počet tiků z jeho řádků.
8. `core/manifest.py`: `SCHEMA_VERSION = 3`, `frames.ticks`, `frames.info`, upravené poznámky `cursor`, `timeline` a `mouse_note`.
9. Smazat `write_sidecar_index` (mrtvá funkce) a `sidecar_filename` z `core/naming.py`; `parse_frame_filename` přestane přijímat `.json`.
10. Testy:
    - pomocné funkce `make_recording` zapisují index místo sidecarů; očekávané texty `timeline` a výsledky `frames` ve stávajících testech zůstávají, až na pole `sidecar`;
    - složka bez `index.jsonl`: `timeline`, `frames` i editor skončí chybou `NO_INDEX`, ne výjimkou;
    - skutečný `Recorder` s falešným snímačem: žádný soubor `*.json` ve `frames_info/`, jen index; schránka v indexu právě jednou; mřížka pro obě obrazovky.

### P4 – výstup pro agenta, skill a dokumentace

1. `host/runner.py`: `frames_file` při zkrácení (zápis přes `host/agent_output.py`), texty zkrácení bez slova sidecar, `ARCHIVED_NOTE`.
2. `skills/watch-me/SKILL.md`:
   - `:200-202` a `:234`: celá cesta tahu a `background` tvaru jsou ve `frames` bez `--no-drawings`, ne „v sidecaru“;
   - `:321-332`: pole `sidecar` vypadne; zkrácený výsledek odkazuje na `frames_file`;
   - `:334-335`: popis souborů (`frames_info/index.jsonl`);
   - `:343-350`: u archivované nahrávky „index a přepis zůstávají“.
3. `README.md` (řádky 15, 17, 42-61), `docs/installation.md:385-387`, `watch-me-spec.md` (řádky 102-106, 154-156, 183, 227, 270-271, 281), docstringy `host/mcp_server.py`, `core/session.py` a `core/manifest.py`.
4. `watch-me-review-2026-11-14.md`: řádky E1, F1, D2 a B3 v tabulce „Stav po opravách“ (B3 jako otevřený, s odkazem na měření).
5. Test: `tests/unit/test_cli_agent_files.py` pro `frames_file`.

### P5 – převod testů a úklid *(subagent)*

Projít testy, které zapisují nebo počítají sidecary (soupis v kapitole 2.1 a ve zprávě pomocného agenta), a upravit je na index. Žádná změna v `src/`.

### P6 – zkouška na skutečných obrazovkách

1. Nahrát příkazem `record` 3 minuty skutečných obrazovek s kreslením (několik tahů štětcem); zapsat velikost `frames_info/` a porovnat s dnešními 424 KiB ve 296 souborech za 74 s.
2. `timeline` a `frames` nad novou nahrávkou; doba prvního volání `timeline`.
3. Uměle vyrobený index dvouhodinové nahrávky se 150 tahy po 40 bodech: velikost souboru a doba `timeline` (dnes dopočtených 100 s).
4. Render a archivace nové nahrávky skutečným FFmpegem; kontrola počtu snímků a polohy kurzoru.
5. Editor (bez obrazovky): nahrávka se načte, náhled a kurzor sedí, okno Mouse ukáže schránku; po archivaci se nahrávka dál otevře.
6. Složka nahrávky, ze které se index smaže: `timeline` a editor ohlásí `NO_INDEX` srozumitelně.
7. Měřicí skript podílu shodných snímků uložit jako `scripts/frame_changes.py`, aby šlo měření pro B3 zopakovat na budoucích nahrávkách.

### P7 – ověření

`ruff check`, `ruff format --check`, celá sada `tests/unit`; do plánu zapsat výsledky P6 a co ověřeno není.

## 5. Kontrolní seznam

- [x] P0 výchozí stav testů
- [x] P1 stavový řádek a ředění tahu
- [x] P2 index: zápis a čtení
- [x] P3 nahrávač píše index, čtenáři čtou přes rozhraní
- [x] P4 výstup pro agenta, skill a dokumentace
- [x] P5 převod testů
- [x] P6 zkouška na skutečných obrazovkách
- [x] P7 ověření

## 6. Rizika a co plán neřeší

- **B3 zůstává otevřený.** Nahrávka dál zabírá kolem 2,3 GB za hodinu, dokud ji archivace nepřevede na MP4. Rozhodnutí o vynechávání obrázků nebo o ukládání jen změněných částí obrazovky se odkládá na měření skutečných delších nahrávek (`scripts/frame_changes.py`). Vynechávání půjde přidat bez změny formátu (R4); ukládání změněných částí by byl samostatný větší projekt.
- **D2 je vyřešený jen zpola.** Souborů bude polovina (7 200 obrázků na obrazovku a hodinu, žádné sidecary); sken seznamu nahrávek v GUI vlákně zůstává.
- **Rozsah.** Krok P3 mění zdroj stavu pro časovou osu, `frames`, editor, render, archivaci i obnovu po pádu najednou (asi 12 modulů) a P5 přepisuje pomocné funkce, na kterých stojí asi 25 testovacích souborů.
- **Nahrávky ze starší verze nepůjdou otevřít.** Podle uživatele žádné neexistují; kdyby se nějaká našla, skončí chybou `NO_INDEX`.
- **Tik bez obrázku po pádu.** Index může mít tik, k němuž se obrázek nestihl dopsat. Čtenáři berou poslední obrázek s časem ≤ T, takže platí starší.
- **Ředění tahu mění tvar o zlomek pixelu.** Při rychlém pohybu se roh nakreslený do 20 ms zkrátí o úsek mezi dvěma událostmi myši; P1 to hlídá jen počtem bodů, ne vzhledem.
