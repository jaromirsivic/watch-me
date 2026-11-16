# Implementační plán: přepis, který se neztratí a jde dokončit příkazem (D4, C1)

Datum: 16. 11. 2026. Verze plánu: 1. Stav: **P0 až P8 implementováno 16. 11. 2026; neověřené body jsou vyjmenované níže**.

Průběh realizace 16. 11. 2026: R1 až R8 potvrzeny uživatelem („pokračuj s implementací“). P0: 210 dotčených testů prošlo před změnou. P1 udělal subagent Opus 5.5 (úsilí high); diff jsem přečetl a testy spustil znovu. P2 až P8 jsem dělal v hlavní relaci.

Odchylky od plánu:

- **Poškozený soubor se odkládá až při prvním zápisu, ne při načtení.** Pouhé zobrazení nahrávky v editoru nebo `describe` tak na disku nic nemění.
- **Editor si přepis z disku načte před každým startem svého pracovního procesu,** nejen po čekání na cizí zámek. Pokrývá to i případ, kdy přepis v editoru selhal, příkaz ho mezitím dokončil a uživatel stiskne Retry.
- **Archivační fronta se na zámek dívá sama, než pracovní proces spustí,** a obsazené nahrávky zkouší znovu po 5 s. Kód `TRANSCRIPTION_BUSY` z pracovního procesu (souběh mezi oběma pohledy na zámek) nahrávku vrátí do fronty a nepočítá se jako neúspěch. Omezení „nejvýš jednou za běh editoru“ odpadlo: fronta se netočí, protože čeká na časovač.
- **Stav „přepisuje jiný proces“ je ve stavovém řádku editoru trvale,** ne jen jako dočasná hláška.
- **Výstup příkazu** nemá pole `transcribed_ms` (po dokončení nedává smysl); má navíc `previous_transcript` (záloha při `--again`) a `damaged_transcript`.
- **`describe` a `timeline`** přidávají vedle `transcript_note` pole `transcription_running`, respektive `transcript_unreadable`.
- `transcribe_recording` v `pipeline.py` zůstal: volají ho jednotkové a integrační testy.
- Poslední řádky výstupu pracovního procesu editor nově zpracuje i při jeho ukončení (dřív je po uvolnění nahrávky zahazoval).
- `transcript_status` počítá jako nečitelný i platný JSON, který není objekt (`[]`, `null`); dřív na něm spadl.

Ověření (P7, P8):

| Zkouška | Výsledek |
| --- | --- |
| `ruff check`, `ruff format --check`, celá sada jednotkových testů na Windows | čisté; 1286 testů prošlo (38 nových) |
| Skutečný model, 6 min 48 s syntetické anglické řeči: `transcribe` zabit po 47 s | na disku čitelný neúplný přepis, 41 segmentů do 126,6 s; žádný `.tmp`, zámek volný |
| Dva běhy `transcribe` současně | druhý skončil kódem 1 a `TRANSCRIPTION_BUSY` |
| Další běh po zabití | `resumed_from_ms: 126640`, hotový přepis, 123 segmentů, 90 s |
| `transcribe` nad hotovým přepisem s ručně opraveným titulkem | `already_complete: true`, soubor bajt po bajtu stejný |
| `transcribe --again` | záloha `transcript.before-again.json` se shoduje s předchozím přepisem |
| Editor (okno bez obrazovky) otevřený na téže nahrávce během běhu příkazu | stav „transcribed by another process“, Process zakázaný; po skončení příkazu hotový přepis se 123 titulky, Process povolený; editor nespustil žádný pracovní proces a do souborů nezapsal |
| Rychlost na nezatíženém stroji: `transcribe` se sníženou prioritou proti `transcribe-stream` s běžnou | 128,4 s proti 128,3 s |

Neověřeno: editor ve skutečném okně na obrazovce (zkouška i testy běží bez obrazovky); archivační fronta proti zámku drženému jiným procesem (testy drží zámek v témže procesu); dvouhodinová nahrávka se skutečným modelem; výpadek napájení; síťová nebo synchronizovaná složka; Linux a macOS.

Co zůstává: zabitý běh nechá v `audio/` převedený zvuk `audio16k.wav`, další běh ho přepíše a po sobě uklidí. Přerušený běh neuloží jazyk (Whisper ho hlásí až na konci), takže navazující běh jazyk zjišťuje znovu; stejně se dosud chová i editor.

Řeší nálezy D4 a C1 z [revize ze 14. 11. 2026](watch-me-review-2026-11-14.md). Oba se týkají téhož souboru (`transcript.json`) a téže cesty kódu, proto jdou spolu: C1 potřebuje bezpečný zápis z D4 a D4 potřebuje pravidlo „jeden zapisovatel“, které zavádí C1.

## 1. Výsledek a hranice

Po realizaci platí:

1. **`transcript.json` a `transcript.txt` se nikdy neroztrhnou.** Zapisují se přes dočasný soubor a přejmenování, s vynuceným zápisem na disk. Čtenář vidí vždy celý starý, nebo celý nový soubor.
2. **Nečitelný přepis se nikdy potichu nepřepíše.** Čtení se při chvilkové chybě opakuje. Soubor, který je opravdu poškozený, se před novým přepisem odloží stranou a `describe`, `timeline` i editor to řeknou.
3. **Editor během přepisu nezapisuje při každém segmentu.** Titulek se na obrazovce objeví hned, na disk se ukládá nejvýš jednou za 5 s a vždy na konci, při zastavení, při přepnutí nahrávky a při zavření okna.
4. **`watch-me transcribe` dokončí přepis, místo aby ho dělal znovu.** Naváže na uložené `transcribed_ms`, ukládá průběžně a běží se sníženou prioritou. Přerušený běh ztratí nejvýš 5 s práce a další spuštění pokračuje.
5. **`watch-me transcribe` nad hotovým přepisem nic nezmění.** Přepsat znovu od nuly jde jen s `--again`, a předchozí přepis přitom zůstane v záloze.
6. **Jednu nahrávku přepisuje vždy jen jeden proces.** Příkaz, editor a archivační proces si ji předávají zámkem; kdo přijde druhý, počká nebo skončí s jasnou zprávou.

Mimo rozsah: výchozí počet vláken a přibrzdění při nahrávání (C2), paměť a jednotná cesta přepisu (C3), sken seznamu nahrávek (D2), čisté přerušení Whisperu uprostřed běhu.

## 2. Zjištění

### 2.1 Aktuální kód

- `core/transcript.py:159-163` `write_transcript`: dvě prostá `write_text`. Volá ho editor při každém segmentu (`editor/transcription.py:236` → `editor/recording.py:343-350`), při každé ruční úpravě titulku (`recording.py:513`, `:527`) a příkaz `transcribe` na konci (`transcribe/pipeline.py:317`).
- `core/transcript.py:184-197` `transcript_status`: nečitelný soubor znamená „přepis od 0 ms“. `LoadedRecording.load` (`recording.py:170-174`) v tom případě načte nahrávku bez přepisu, editor ji začne přepisovat od nuly a první segment původní soubor přepíše.
- Titulky jde v editoru upravovat až po dokončení přepisu (`editor/window.py:3013-3016`). Ruční úpravy tedy existují jen v hotových přepisech.
- `host/cli.py:426-459` `cmd_transcribe`: volá `transcribe_recording`, který přepíše celý zvuk a zapíše až na konci, vždy jako hotový přepis. Uložené `transcribed_ms` nečte.
- Navazující varianta existuje: `cmd_archive_stream` (`host/cli.py:584-605`) načte nahrávku, pustí `stream_transcription` od `transcribed_ms` a segmenty ukládá přes `LoadedRecording.add_segments`.
- `core/fileio.py:42-60` `atomic_write_text`: dočasný soubor a `os.replace`, při obsazeném cíli opakuje až 3 s. Na disk zápis nevynucuje. Živý přepis při nahrávání ho už používá (`host/live_transcription.py:343-344`).
- `host/editor_lock.py:49-104` `EditorLock`: zámek operačního systému nad souborem, který se uvolní sám, když proces skončí jakkoli. Používá ho editor (jedna instance) a start oken.
- Editor přepisuje jen nahrávku, kterou ukazuje (`editor/transcription.py:13-15`). Archivační proces žije jen s oknem editoru a nedokončený přepis si dodělává sám.
- Převedený zvuk má pevné jméno `audio/audio16k.wav` (`transcribe/pipeline.py:181`). Dva přepisy téže nahrávky si ho přepisují pod rukama.
- Whisper v procesu nemá háček pro přerušení (`transcribe/whisper_backend.py:211`, jen zpětné volání pro nový segment). Běh jde ukončit jen zabitím procesu.
- `describe` a `timeline` u neúplného přepisu radí `watch-me transcribe` (`host/runner.py:742-745`, `host/events.py:853-857`), stejně jako skill (`skills/watch-me/SKILL.md:287-288`, `:387-390`).

### 2.2 Pokusy (Windows 11, tento stroj, 16. 11. 2026)

| Pokus | Výsledek |
| --- | --- |
| Přepis dvouhodinové nahrávky (3 000 segmentů): velikost `transcript.json` | 402 KiB |
| Jeden zápis obou souborů dnešním způsobem | medián 8,8 ms, nejvýš 13,6 ms |
| Totéž přes dočasný soubor a přejmenování | medián 9,4 ms |
| Totéž s vynuceným zápisem na disk (`fsync`) | medián 11,1 ms, nejvýš 20,5 ms |
| Všech 3 000 zápisů po segmentech za celý přepis (dopočteno z každého desátého) | asi 20 s práce v GUI vlákně |
| Proces, který přepis zapisuje ve smyčce, zabit v náhodný okamžik, 40× | 2× zůstal `transcript.json` o velikosti 0 bajtů |

Závěry: roztržený soubor je skutečný (5 % zabití zapisujícího procesu ve smyčce; v běžném provozu je okno užší, protože se nezapisuje nepřetržitě). Atomický zápis s `fsync` stojí o 2 ms víc. Dávkování po 5 s sníží počet zápisů za třicetiminutový přepis z 3 000 na asi 360; na rychlém disku je to úspora v řádu sekund, na pomalém nebo hlídaném antivirem víc.

## 3. Rozhodnutí

- **R1 – atomický zápis s `fsync`.** `write_transcript` zapíše nejdřív `transcript.json` (zdroj pravdy), pak `transcript.txt`, oba přes `atomic_write_text` s novým parametrem `durable=True`. Důvod pro `fsync`: bez něj může po výpadku napájení zůstat přejmenovaný soubor s nulami.
- **R2 – nečitelný přepis se nepřepisuje.** Čtení přepisu jde přes `read_json_with_retry` (krátké opakování při sdílení souboru). `transcript_status` nově rozliší `unreadable`. Než kdokoli začne nad nečitelným souborem nový přepis, přejmenuje ho na `transcript.damaged.json`. Obnovu segmentů z `transcript.txt` plán nedělá: po R1 má poškození vzniknout jen vadou disku.
- **R3 – ukládání po dávkách, 5 s.** Segment se přidá do paměti hned, na disk nejvýš jednou za 5 s. Zápis průběhu při obsazeném cíli nečeká 3 s v GUI vlákně: zkusí to 0,2 s a jinak počká na další interval (data jsou v paměti). Ruční úprava titulku se zapisuje hned a s plným opakováním, jako dnes.
- **R4 – `transcribe` dokončuje.** Neúplný přepis: naváže od `transcribed_ms`. Hotový přepis: nic nezmění a vrátí `already_complete: true` s kódem 0. `--again`: začne od nuly, předchozí `transcript.json` uloží jako `transcript.before-again.json` (jedna záloha, další `--again` ji přepíše) a odmítne běžet, když je otevřený editor (`EDITOR_OPEN`), protože uživatel v něm může hotový přepis právě upravovat.
- **R5 – zámek přepisu nahrávky.** `<recording_folder>/.work/transcribe-<session_id>.lock`, třída `EditorLock`. Drží ho ten, kdo právě přepis vyrábí: příkaz `transcribe`, editor po dobu běhu svého pracovního procesu a archivační proces ve fázi přepisu. Leží v `.work`, ne ve složce nahrávky, aby nepřekážel přesunu nahrávky mezi složkami.
- **R6 – co dělá ten druhý.** Příkaz skončí s `TRANSCRIPTION_BUSY` (kdo zámek drží, pid). Editor ukáže stav „čeká“, každé 2 s zámek zkusí a po uvolnění si přepis znovu načte z disku. Archivační proces nahrávku odloží na konec fronty a nepočítá to jako neúspěch.
- **R7 – snížená priorita, vlákna beze změny.** `transcribe` si sníží prioritu stejně jako archivační proces (`lower_own_priority("faster")`). Počet vláken zůstává podle konfigurace; ten řeší C2.
- **R8 – žádný časový rozpočet.** Whisper nejde čistě přerušit, takže volba typu `--max-seconds` by znamenala zabíjet vlastní proces. Místo toho: příkaz je bezpečné zabít a pustit znovu, a skill to agentovi řekne. Průběh jde na stderr (procenta, odhad zbývajícího času).

Příkaz `transcribe` nově odmítne relaci, která se právě nahrává nebo ukládá (`SESSION_ACTIVE`): její přepis patří živému přepisu v ovládacím okně.

## 4. Kroky realizace

Pořadí je závazné; každý krok končí zelenými testy. Kroky označené *(subagent)* jsou mechanické a hlídané testy, ostatní dělám v hlavní relaci.

### P0 – výchozí stav

Spustit a zapsat výsledek: `tests/unit/test_transcript_flags.py`, `test_transcribe.py`, `test_pipeline_resume.py`, `test_editor_transcription.py`, `test_editor_archive.py`, `test_archive.py`, `test_events.py`, `test_resilience.py`, `test_narration_tracks.py`.

### P1 – bezpečný zápis a čtení (`core/fileio.py`, `core/transcript.py`) *(subagent)*

1. `atomic_write_text(..., durable=False, attempts=REPLACE_ATTEMPTS)`: s `durable` před přejmenováním `flush` a `os.fsync`.
2. `write_transcript(txt, json, transcript, attempts=...)`: JSON první, oba atomicky a `durable`.
3. `read_transcript` přes `read_json_with_retry`.
4. `TranscriptStatus.unreadable`; `transcript_status` ho nastaví až po opakovaném čtení.
5. `host/live_transcription.py:343-344` přejde na `write_transcript`.
6. Testy: po zápisu nezůstane `.tmp`; selhání přejmenování nechá původní soubor celý; nečitelný soubor dá `unreadable`, ne „od 0 ms“.

### P2 – úložiště přepisu (nový `core/transcript_store.py`)

Třída `TranscriptStore` bez Qt, jen nad dvěma cestami:

- `load()`: přečte přepis; nečitelný soubor odloží jako `transcript.damaged.json` a zapamatuje si to (`damaged`).
- `add_segments(segments, transcribed_ms)`: sloučí do paměti (`merge_segments`), označí „neuloženo“.
- `save_if_due(now, interval_s=5.0)` a `save()`: zápis; `save_if_due` s krátkým opakováním, `save` s plným.
- `finish(language, model, backend)`, `reset()`, `replace(transcript)` (ruční úprava): zapisují hned.

`LoadedRecording` si úložiště drží a jeho veřejné metody (`add_segments`, `finish_transcript`, `reset_transcript`, `apply_segment_edit`, `replace_segment`) zůstanou; přibude `flush_transcript()` a `reload_transcript()`. `add_segments` dostane parametr `save` (výchozí „hned“, aby se stávající volání nezměnila).

Testy: neuložený segment je vidět v paměti a po `save()` na disku; ruční úprava zapíše i dosud neuložené segmenty; poškozený soubor skončí stranou a nový přepis začne prázdný.

### P3 – dávkování v editoru (`editor/transcription.py`, `editor/window.py`)

1. `TranscriptionManager._handle_line`: segment přidá s odloženým zápisem a zavolá `save_if_due`.
2. Zápis navíc: jednorázový `QTimer` 5 s po prvním neuloženém segmentu (kdyby další segment dlouho nepřišel), dále v `stop()`, `shutdown()`, `adopt()`, při selhání pracovního procesu a v `closeEvent` okna.
3. `finish_transcript` zapisuje vždy (beze změny).
4. Testy s falešným pracovním procesem (`tests/unit/test_editor_transcription.py`): 20 segmentů rychle za sebou znamená nejvýš 2 zápisy; po `stop()` je na disku všech 20; po dokončení je přepis hotový.

### P4 – zámek přepisu (nový `host/transcription_lock.py`, editor, archiv)

1. `transcription_lock(paths) -> EditorLock`, `transcription_holder(paths) -> int | None`.
2. Editor: `_launch` zámek vezme a před startem zavolá `recording.reload_transcript()` (na disku může být víc, než má v paměti). Když zámek nedostane, nahrávka je „pending“ s hláškou ve stavovém řádku a zkouší se znovu po 2 s. Zámek se uvolní v `_on_finished`, `_on_error` a `shutdown`.
3. Editor: „Transcribe again“ (ikona pera, přepnutí stopy) se při cizím zámku odmítne se zprávou.
4. `cmd_archive_stream`: fáze přepisu si zámek vezme; při obsazení skončí kódem `TRANSCRIPTION_BUSY`. `ArchiveManager._on_finished` ten kód nepočítá jako neúspěch a nahrávku zařadí na konec fronty (nejvýš jednou za běh editoru, aby se netočil).
5. `describe` a `timeline`: když zámek někdo drží, poznámka zní „přepis právě běží (pid N), zkus to za chvíli“ místo rady spustit `transcribe`.
6. Testy: druhý držitel zámek nedostane; po ukončení držitele ano; editor s obsazeným zámkem nespustí pracovní proces a po uvolnění ho spustí od stavu na disku.

### P5 – příkaz `transcribe` (`host/cli.py`, `transcribe/pipeline.py`)

1. Kontroly: zvuk existuje, relace není `recording` ani `processing`, zámek je volný.
2. `TranscriptStore.load()` nad `paths.current_dir`. Hotový přepis bez `--again`: vrátit `already_complete`.
3. `--again`: odmítnout při běžícím editoru, uložit zálohu, `reset()`.
4. `lower_own_priority("faster")`, `stream_transcription(start_ms=..., language=...)` s `resume_context`; segmenty do úložiště, `save_if_due` při každém segmentu a při události průběhu; `finally: save()`.
5. Po `done`: `finish(...)`, zápis do `manifest.json` jako dnes.
6. Výstup JSON: dosavadní pole a navíc `complete`, `already_complete`, `resumed_from_ms`, `transcribed_ms`, `damaged` (cesta k odloženému souboru, když vznikl).
7. `transcribe_recording` v `pipeline.py` zůstane jen pro testy a integrační test, nebo se odstraní, když ho po změně nic nevolá.
8. Testy s falešným backendem: navázání od `transcribed_ms` (backend dostane jen zbytek zvuku); hotový přepis s ručně upraveným titulkem zůstane bajt po bajtu stejný; `--again` vytvoří zálohu; obsazený zámek dá `TRANSCRIPTION_BUSY`; výjimka uprostřed běhu nechá na disku neúplný přepis se segmenty, které už přišly.

### P6 – texty pro agenta a dokumentace

- `host/runner.py`, `host/events.py`: poznámka u neúplného přepisu říká, že `transcribe` naváže, kolik zvuku zbývá, a u poškozeného souboru, kam se odložil.
- `skills/watch-me/SKILL.md`: `transcribe` dokončuje; dlouhý běh pouštět na pozadí nebo s dlouhým limitem; po přerušení pustit znovu; `--again` jen na výslovnou žádost uživatele; `TRANSCRIPTION_BUSY` znamená počkat.
- `README.md`, `watch-me-spec.md`, `docs/installation.md` (Troubleshooting): totéž krátce.
- `watch-me-review-2026-11-14.md`: řádky D4 a C1 v tabulce „Stav po opravách“.

### P7 – zkouška se skutečným modelem

Na skutečné nahrávce (několik minut řeči), mimo `~/.watch-me`:

1. `transcribe` zabít po zhruba třetině; na disku je neúplný přepis; druhý běh hlásí `resumed_from_ms` větší než 0 a skončí hotovým přepisem.
2. Dva běhy současně: druhý skončí `TRANSCRIPTION_BUSY`.
3. Během běhu příkazu otevřít editor na téže nahrávce: čeká, po skončení příkazu ukáže hotový přepis a nic nepřepisuje.
4. Hotový přepis s ručně upraveným titulkem: `transcribe` ho nezmění; `--again` vytvoří zálohu.
5. Změřit dobu přepisu se sníženou prioritou proti běžné na nezatíženém stroji.

### P8 – ověření

`ruff check`, `ruff format --check`, celá sada `tests/unit`; do plánu zapsat výsledky P7 a co ověřeno není.

## 5. Kontrolní seznam

- [x] P0 výchozí stav testů
- [x] P1 bezpečný zápis a čtení
- [x] P2 úložiště přepisu
- [x] P3 dávkování v editoru
- [x] P4 zámek přepisu
- [x] P5 příkaz `transcribe`
- [x] P6 texty pro agenta a dokumentace
- [x] P7 zkouška se skutečným modelem
- [x] P8 ověření

## 6. Rizika a co plán neřeší

- **Síťová nebo synchronizovaná složka nahrávek.** Zámek souboru a `fsync` se tam mohou chovat jinak (OneDrive, SMB). Plán to nezkouší.
- **Archivační fronta.** Krok P4 bod 4 sahá do chování, které dnes funguje; je to nejrizikovější část a dostane vlastní testy v `test_editor_archive.py`.
- **Starý roztržený soubor.** Nahrávka, kterou roztrhla dnešní verze, bude po změně hlášená jako poškozená a soubor se odloží; obsah se neobnoví.
- **Zabití uprostřed zápisu po R1.** Může zůstat `transcript.json.tmp`; další zápis ho přepíše. Rozdíl mezi novějším `transcript.json` a starším `transcript.txt` je možný a neškodný, při dalším zápisu se srovná.
- **Čas v GUI vlákně.** Sloučení segmentu a přepočet titulků (asi 0,4 ms na segment u 3 000 segmentů) zůstávají v GUI vlákně; plán je nepřesouvá.
- **Druhá kopie modelu v paměti a plné vytížení procesoru** při běhu `transcribe` vedle nahrávání zůstávají (C2, C3).
