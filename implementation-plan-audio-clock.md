# Implementační plán: mikrofon na hodinách nahrávky a hlídání zvukových zařízení (B1, B2)

Datum: 15. 11. 2026. Verze plánu: 1. Stav: **Z0 až Z9 implementováno 15. 11. 2026; ze Z10 zbývají ruční zkoušky zařízení, desetiminutová nahrávka a CI**.

Průběh realizace 15. 11. 2026: R1 až R7 potvrzeny uživatelem („Ano, implementuj“). Z2, Z7 a Z9 provedli subagenti Opus 5.5 (úsilí high), jejich diffy jsem přečetl a testy spustil znovu. Ostatní kroky jsem dělal v hlavní relaci.

Měření (20 s, skutečný mikrofon, `tests/integration/test_audio_clock.py`):

| Stav | Bez zátěže: mikrofon − osa | Čtyři vlákna držící GIL: mikrofon − osa | Doplněno ticha při zátěži |
| --- | --- | --- | --- |
| před změnou (Z0) | +190 ms | −8 424 ms | – |
| po změně | 0 ms | 0 ms | 55 ms samostatně, 347 ms při souběžném běhu celé sady testů |

Z10 bod 1: `ruff check` čistý, celá sada jednotkových testů na Windows prošla (1172 testů). CI na Linuxu a macOS ještě neběželo.

Skutečná bezokenní nahrávka 20 s (dvě obrazovky, přepis během nahrávání): mikrofon − osa 0 ms, zvuk počítače − osa +64 ms (stejně jako před změnou), žádné výpadky.

Odchylky od plánu:

- Z1, Z4 a Z5 vznikly společně jako jeden přepis `capture/audio_recorder.py`, protože se týkají téhož zapisovače.
- `AudioRecorder` bez předaných hodin si vede vlastní (od `start()` do `stop()`), aby šel použít a testovat samostatně.
- Po úspěšném otevření náhradního zařízení se další pokus odkládá na 6 s místo 2 s, aby zařízení s pomalým rozjezdem (Bluetooth) dostalo čas dodat první blok.
- Bloky se značkou před nulou osy se zahazují celé a nepočítají se do `dropped_ms`; to pole tak ukazuje jen oříznutí prvního bloku a skutečný přebytek.
- Výstraha se v okně hlásí i pro stopu počítače (`Recorder.audio_warning` bere mikrofon první).
- Záložní cesta s přepočtem frekvence (R5) přepočítává každý blok zvlášť, bez návaznosti fáze mezi bloky; na Windows se nepoužije, tam systém převádí sám.
- Do `SKILL.md` se podle R7 nic nepřidalo. Subagent Z7 upozornil, že seznam typů řádků v `skills/watch-me/SKILL.md` (kolem ř. 255) nové řádky nezná; agent je dostane vysvětlené v poli `legend`.

Zdroj: nálezy B1 a B2 v [revizi z 14. 11. 2026](watch-me-review-2026-11-14.md) (v revizi z 13. 11. jako N1 a N2). Před sepsáním jsem na tomto stroji (Windows 11, WASAPI, PortAudio 19.7, sounddevice 0.5.6, mikrofon Realtek 48 kHz) udělal tři měření; plán z nich vychází a jsou v oddílu 2. Při měření jsem vzorky z mikrofonu jen počítal, nic se neukládalo.

## 1. Výsledek a hranice

Po změně:

- **B1:** `audio/audio.wav` má stejnou délku jako časová osa nahrávky (odchylka do 150 ms při jakékoli délce a zátěži) a vzorek *i* odpovídá času *i / frekvence* na ose. Časy přepisu tedy sedí se snímky, kurzorem a akcemi myši. Vzorky se při vytíženém procesoru přestanou ztrácet; co se přesto ztratí, se doplní tichem na správném místě a zapíše do manifestu.
- **B2:** když mikrofon přestane dodávat zvuk, nahrávání to do 2 s pozná, ukáže to v ovládacím okně, stopu dál doplňuje tichem a zkouší zařízení otevřít znovu (stejné, nebo nové výchozí). Výpadek je v manifestu a v časové ose pro agenta. Stopa zvuku počítače přejde na nový výchozí výstup, když se změní.

Mimo rozsah (záměrně):

| Co | Proč |
| --- | --- |
| Oprava starých nahrávek | Kde se vzorky ztratily, zpětně zjistit nejde. |
| Přesun snímání mikrofonu do pomocného procesu | Měření ukazuje, že větší vyrovnávací paměť ztrátu odstraní i při tvrdé zátěži. Pomocný proces je záloha, kdyby se to na jiných zařízeních nepotvrdilo (riziko v oddílu 7). |
| Sjednocení zápisu obou stop do jedné třídy | Stopa počítače drží do 80 ms a má vlastní testy. Mění se jen to, co potřebuje B2 (krok Z9). |
| Rozložení obrazovek za běhu (B4), priorita přepisu (C2), hák myši (B5) | Jiné nálezy. |
| Linux a macOS | Kód zůstává přenositelný a CI běží; chování zařízení tam vyzkoušené nebude. |

## 2. Zjištění

### 2.1 Měření

**Dvě zdejší nahrávky (75 s a 74 s, přepis během nahrávání zapnutý):**

| Nahrávka | Mikrofon běžel před nulou osy | Mikrofon − osa na konci | Ztraceno vzorků | Zvuk počítače − osa |
| --- | --- | --- | --- | --- |
| 20261114-205313 | asi 290 ms | −526 ms | asi 820 ms (1,1 %) | +47 ms |
| 20261114-210704 | asi 150 ms | −178 ms | asi 330 ms (0,4 %) | +47 ms |

Stopa mikrofonu má tedy dvě chyby s opačným znaménkem. Na začátku je řeč v přepisu o 150 až 290 ms **později** než na ose, protože proud mikrofonu startuje před `clock.start()` a mezi tím se otevírá zvuk počítače (`capture/recorder.py:551-569`; časy z `recording.log`). Pak se vzorky ztrácejí a ke konci je řeč **dřív**. Počítadlo `dropped_blocks` ukazuje u obou nahrávek nulu.

**PortAudio při zátěži (6 s, čtyři vlákna držící GIL):**

| Nastavení vstupního proudu | Chybí zvuku | Příznak přetečení |
| --- | --- | --- |
| dnešní (výchozí latence 22 ms), bez zátěže | 49 ms | 0 |
| dnešní, se zátěží | **2 489 ms** | **0** |
| `latency=0.2`, se zátěží | 23 ms | 0 |
| `latency=0.5`, se zátěží | 33 ms | 0 |
| `latency=1.0`, se zátěží | 83 ms | 0 |
| `blocksize=4800`, se zátěží | 74 ms | 0 |
| blokující čtení, výchozí latence, se zátěží | 2 708 ms | 0 |

Dva závěry. Příčina ztrát je potvrzená: zpětné volání čeká na GIL a WASAPI mezitím zahazuje data. A PortAudio to na WASAPI **nehlásí**, takže návrh z revize „logovat přetečení“ by nic nenašel; ztrátu jde poznat jen porovnáním s hodinami. S vyrovnávací pamětí od 200 ms ztráta mizí (zbylých 23 až 83 ms je rozjezd a dojezd proudu, stejně jako bez zátěže).

**Znovuotevření zařízení:** `sd.WasapiSettings(auto_convert=True)` otevře vstup na jiné než nativní frekvenci (16 kHz na zařízení 48 kHz), bez něj otevření selže s `Invalid sample rate`. `sd._terminate()` a `sd._initialize()` existují a nový výčet zařízení trvá 28 ms.

### 2.2 Aktuální kód

| Místo | Stav dnes | Důsledek pro realizaci |
| --- | --- | --- |
| `capture/audio_recorder.py:204-211` | `sd.InputStream` s výchozí latencí a polem NumPy | Vyšší latence, `RawInputStream` (bajty) |
| `capture/audio_recorder.py:163-171` | Zpětné volání řadí bloky bez času; pauza je příznak `paused` | Každý blok dostane `perf_counter_ns`; pauzu určí hodiny |
| `capture/audio_recorder.py:173-190` | Zapisovač píše, co přijde | Zarovnání podle hodin, doplnění ticha, hlídač |
| `capture/recorder.py:546-569` | Mikrofon startuje před `clock.start()`, mezi tím se otevírá zvuk počítače | Bloky před nulou osy se zahodí |
| `capture/recorder.py:337-376` | `pause()` nastaví `_audio.paused` a až potom zastaví hodiny | Příznak zmizí, rozhodují hodiny |
| `capture/recorder.py:578-609` | `stop()`: hodiny se zastaví dřív než mikrofon | Bloky po zastavení se zahodí, konec se dorovná |
| `core/timeline.py:121-139` | `ms_at()` vrací čas i pro značku po `stop()` | Po zastavení vracet `None` |
| `capture/computer_audio.py:187-224` | Smyčka svázaná s výstupem výchozím při startu; chyba ukončí stopu | Sledovat výchozí výstup a otevírat znovu |
| `capture/recorder.py:468-472`, `ui/control_window.py:1102-1130` | `recorder.error` nahrávání zastaví | Výpadek zařízení je varování, ne chyba: nová vlastnost |
| `host/controller.py:121` | `Recorder` se vytváří bez `on_event`; okno stav čte v `_tick` každých 200 ms | Varování číst stejně, žádné nové propojení vláken |
| `core/manifest.py:31-55` | `AudioInfo`: zařízení, frekvence, kanály, délka | Přidat doplněné a zahozené ms a výpadky |
| `host/events.py:120-148` | Řádky `MUTE` / `UNMUTE` z manifestu | Stejným vzorem řádky o výpadku |
| `transcribe/growing_wav.py:28-31` | Živý přepis čte rostoucí WAV podle velikosti souboru; stopu zaostalou o 5 s bere jako mrtvou | Při výpadku doplňovat ticho průběžně, ne až na konci |
| `sounddevice.py:2791-2796` | `InputStream` jde přes přiřazení `data.shape`, které NumPy označilo za zastaralé | `RawInputStream` tuhle cestu obejde (nález G1) |
| `tests/unit/test_pause_mute.py:77`, `tests/unit/test_resilience.py:190` | Testy volají `_callback` a zapisovač přímo | Přepsat na nové rozhraní |

## 3. Rozhodnutí

**R1 – vstupní proud s latencí 0,5 s.** Měření ukazuje nulovou ztrátu už od 0,2 s; 0,5 s dává rezervu pro delší zadržení GIL (kódování PNG, start přepisu). Pro nahrávání zpoždění nevadí. Hodnota bude konstanta v `audio_recorder.py`.

**R2 – čas bloku je okamžik zpětného volání, ztráta se odhaduje minimem za 2 s.** S větší vyrovnávací pamětí přijdou po zadržení bloky ve shluku. Kdyby zapisovač doplnil ticho hned, jak blok „mešká“, nahradil by tichem skutečný zvuk, který dorazí o chvíli později. Zpoždění doručení umí odchylku jen zvětšit, nikdy zmenšit, takže skutečný stav je nejmenší odchylka za poslední 2 s. Ticho se doplní, až když toto minimum přesáhne 100 ms; stejně se zahodí přebytek, když hodiny zařízení běží rychleji.

**R3 – při výpadku mikrofonu nahrávání pokračuje.** Obraz, kurzor a zvuk počítače mají cenu i bez komentáře a uživatel může mikrofon vrátit. Okno ukáže varování, dokud se zvuk nevrátí. Alternativa: nahrávání zastavit a otevřít editor, jako při plném disku. Doporučuji pokračovat.

**R4 – po výpadku se otevře nastavené zařízení, a když není, výchozí vstup.** Zpátky na původní zařízení se za běhu nepřepíná; jednou otevřené fungující zařízení zůstává do konce nahrávky.

**R5 – soubor zůstává jeden a na původní frekvenci.** Nové zařízení se otevírá na frekvenci souboru (na Windows s `auto_convert`, vyzkoušeno). Když to systém odmítne, přepočítá se blok v zapisovači (lineární interpolace; jde o záložní cestu při výpadku, ne o běžný provoz).

**R6 – nový výčet zařízení přes `sd._terminate()` a `sd._initialize()`.** Veřejné rozhraní pro to sounddevice nemá a bez nového výčtu PortAudio nově připojené zařízení nevidí. V procesu nahrávače je mikrofon jediný proud PortAudio (zvuk počítače jde přes `soundcard`, přehrávač editoru běží v jiném procesu). Když ty funkce v budoucí verzi zmizí, zkusí se jen stejné zařízení znovu a varování zůstane.

**R7 – výpadek se zapíše do manifestu jako `audio.gaps` a do časové osy jako `MIC LOST` / `MIC BACK`** (a `PC AUDIO LOST` / `PC AUDIO BACK`). Agent tak ví, že chybějící řeč není ticho uživatele. Do `SKILL.md` se nic nepřidává, stačí pole `legend` ve výsledku `timeline`.

## 4. Návrh

### 4.1 Zarovnání mikrofonu

Nový modul `capture/audio_align.py` bez vláken a bez zvukového zařízení, aby šel celý otestovat jednotkově:

```python
@dataclass
class Placement:
    pad: int   # samples of silence to write before the block
    skip: int  # samples to drop from the start of the block

class TrackAligner:
    """Keeps a track written block by block on the recording clock."""
    def __init__(self, sample_rate: int, tolerance_ms: int = 100, window_ms: int = 2000): ...
    def place(self, end_ms: int, frames: int) -> Placement: ...   # a block ending at end_ms
    def idle(self, now_ms: int) -> int: ...                       # silence to write when nothing arrives
    def finish(self, duration_ms: int) -> int: ...                # silence to reach the end
    written: int      # samples in the file
    padded: int       # samples of silence added for lost sound
    dropped: int      # samples dropped as surplus
```

Pravidla:

1. **První blok** se ořízne přesně: do souboru jde jen jeho konec dlouhý `end_ms × frekvence` (blok začal před nulou osy).
2. **Běžný blok:** odchylka je `end_ms × frekvence − (written + frames)`. Uloží se do okna posledních 2 s. Je-li minimum okna větší než tolerance, doplní se před blok ticho o velikosti minima a okno se vyprázdní. Je-li menší než záporná tolerance, zahodí se z bloku přebytek.
3. **Nic nepřichází** (`idle`, voláno zapisovačem každých 250 ms): dokud je poslední blok mladší než 2 s, nic. Potom se doplňuje ticho až po aktuální čas osy, aby soubor rostl a živý přepis stopu nepovažoval za mrtvou.
4. **Konec** (`finish`): ticho do délky osy. Bloky se značkou po zastavení hodin se zahodí, takže stopa osu nepřesáhne o víc než toleranci.

Čas bloku: `clock.ms_at(perf_counter_ns)` značky ze zpětného volání. `None` (před startem, v pauze, po zastavení) znamená blok zahodit. Blok přes hranici pauzy se zahodí celý; chyba je nejvýš 10 ms na pauzu a pravidlo 2 ji hlídá.

### 4.2 Zapisovač a hlídač

Zpětné volání zůstává krátké: značka času, kopie bajtů, příznak ztlumení, vložení do fronty. Vlákno zapisovače:

```text
opakuj:
    položka = fronta.get(timeout 0,25 s)
    blok      -> čas z hodin -> aligner.place -> zapsat ticho, blok (nebo nuly při Mute)
    nic       -> aligner.idle -> zapsat ticho
              -> hodiny běží, není pauza a 2 s nepřišel blok: stav LOST, zkusit znovu otevřít
    konec     -> aligner.finish -> zavřít soubor
```

Stav zařízení: `ok` → `lost` (2 s bez bloku nebo `finished_callback` proudu) → `ok` (první blok z nově otevřeného proudu). Každý přechod zapíše do `gaps` čas osy a důvod. Pokus o otevření jednou za 2 s: zavřít starý proud, nový výčet zařízení (R6), vybrat zařízení (R4), otevřít na frekvenci souboru (R5). Zavření mrtvého proudu běží ve vlastním vlákně s limitem 3 s, aby zaseknuté `Pa_CloseStream` nezastavilo zapisovač.

### 4.3 Co uvidí uživatel a agent

- `Recorder.audio_warning`: text nebo `None`. `ControlWindow._tick` ho ukáže ve stavovém řádku výraznou barvou; při prvním výskytu navíc `QApplication.alert()` (blikne tlačítko na hlavním panelu) a zpráva z ikony v oznamovací oblasti, pokud je okno schované tam.
- Manifest: `audio.padded_ms`, `audio.dropped_ms`, `audio.gaps: [{from_ms, to_ms, reason, device}]`; totéž u `computer_audio`.
- Časová osa: `66000 MIC LOST (no sound from "Headset"; silence until 78000)` a `78000 MIC BACK ("Pole mikrofonu")`; legenda o jednu větu delší.

## 5. Kroky realizace

Každý krok má vlastní testy a nechává sadu zelenou. Z1 až Z4 jsou B1, Z5 až Z9 jsou B2.

### Z0 – výchozí měření

Přidat `tests/integration/test_audio_clock.py` (jen s `WATCH_ME_INTEGRATION=1`, potřebuje mikrofon): bezokenní `Recorder` 60 s se čtyřmi vlákny držícími GIL, výsledek je rozdíl délky `audio.wav` a osy. Spustit před změnou a číslo zapsat sem. Očekávání podle oddílu 2.1: řádově sekundy.

### Z1 – přestat ztrácet vzorky

`AudioRecorder.start`: `sd.RawInputStream(..., latency=INPUT_LATENCY_S)` s `INPUT_LATENCY_S = 0.5`. Zpětné volání vkládá do fronty `(perf_counter_ns, bytes(indata), muted)`. Zapisovač zatím píše jako dnes. Kapacitu fronty počítat ze skutečné velikosti bloku, ne z konstanty 1024.

Test: zpětné volání s připraveným bufferem vloží správnou trojici. Měření Z0 zopakovat: ztráta má klesnout pod 100 ms; počáteční náskok mikrofonu ještě zůstává.

### Z2 – hodiny po zastavení

`RecordingClock.ms_at` vrátí `None` pro značku po `stop()`. Test v `tests/unit/test_pause_mute.py` vedle stávajících testů hodin. Ověřit, že to nevadí `capture/input_recorder.py` (události myši po zastavení se mají zahodit také).

### Z3 – `TrackAligner`

Modul podle 4.1 a `tests/unit/test_audio_align.py`:

| Případ | Očekávání |
| --- | --- |
| rovnoměrné bloky 10 minut | `padded == dropped == 0` |
| první blok končí 3 ms po nule | do souboru jdou 3 ms |
| po 5 s chybí 300 ms | jedno doplnění 300 ms ± 1 blok, nejpozději 2 s po ztrátě |
| zadržení 400 ms a potom shluk bloků, nic neztraceno | nic se nedoplní |
| zařízení o 0,1 % rychlejší, 10 minut | zahozeno 600 ms ± tolerance, délka sedí |
| 5 s bez bloků | `idle` po 2 s doplňuje ticho až do času osy |
| konec | `finish` dorovná na délku osy ± 1 vzorek |

### Z4 – mikrofon na hodinách nahrávky

- `AudioRecorder(path, device_name, clock)`; `Recorder.start` předá `self.clock`.
- Zapisovač podle 4.2 (zatím bez znovuotevření).
- Zrušit `AudioRecorder.paused` a jeho nastavování v `Recorder.pause` a `_resume_tracks`.
- `AudioResult` dostane `padded_ms`, `dropped_ms` a `gaps`; `AudioInfo` totéž s tolerantním čtením starých manifestů.
- Log: jedna řádka WARNING při každém doplnění nebo zahození, souhrn při zastavení.

Testy: přepsat `test_microphone_drops_paused_blocks_and_writes_silence_while_muted` a `test_audio_writer_that_cannot_write_reports_it_and_stop_returns` na nové rozhraní. Nový test se skutečným `Recorder`, falešným proudem a posouvanými hodinami: nahrávka s pauzou a ztlumením má stopu dlouhou jako osa. Měření Z0 zopakovat: rozdíl do 150 ms, `padded_ms` do 100.

### Z5 – hlídač a znovuotevření mikrofonu

Stavy a pokusy podle 4.2, pravidla R4 až R6. Výčet zařízení i znovuotevření pod jedním zámkem modulu (Settings volá `list_input_devices()` z GUI vlákna).

Testy s falešným modulem `sd`: proud přestane volat → do 2 s stav `lost`, ticho přibývá, `gaps` má začátek; falešný výčet vrátí nové výchozí zařízení → proud se otevře, `gaps` má konec; otevření na frekvenci souboru selže → otevře se nativní a blok se přepočítá; zavření starého proudu se zasekne → zapisovač běží dál.

### Z6 – varování v ovládacím okně

`Recorder.audio_warning` a zobrazení podle 4.3. `recorder.error` (zastaví nahrávání) se nemění. Test s `qtbot`: text se objeví a zmizí, nahrávání se nezastaví.

### Z7 – manifest a časová osa

`host/events.py`: funkce vedle `_mute_events` čte `audio.gaps` a `computer_audio.gaps`; věta do `LEGEND`. Testy podle `test_timeline_lines_for_pauses_and_mutes`: výpadek uvnitř rozsahu, začínající před rozsahem a trvající do konce.

### Z8 – zvuk počítače sleduje výchozí výstup

`ComputerAudioRecorder._run`: jednou za 2 s porovnat `default_speaker().id` s otevřeným zařízením. Při změně nebo při chybě čtení smyčku zavřít a otevřít na novém výstupu, mezitím doplňovat ticho průběžně (dnes se doplní až při dalším bloku nebo na konci). Chyba už stopu neukončuje, zkouší se dál jednou za 2 s. Výpadky do `gaps`.

Testy s falešným `soundcard`: změna výchozího výstupu → nové zařízení, souvislá stopa; chyba čtení → ticho a nový pokus; stávající `test_computer_audio_stays_on_the_recording_clock` a `test_computer_audio_leaves_out_the_pause_and_writes_silence_while_muted` beze změny.

### Z9 – dokumentace

`docs/installation.md` (řešení potíží: co znamená varování o mikrofonu), `watch-me-spec.md` (tabulka chyb), tabulka „Stav po opravách“ v revizi, stav tohoto plánu.

### Z10 – ověření

1. `ruff check`, celá sada jednotkových testů na Windows, CI na třech systémech.
2. Měření z Z0 po všech krocích, čísla zapsat.
3. Skutečná nahrávka 10 minut s přepisem během nahrávání a běžnou prací: `padded_ms` blízko nuly, rozdíl mikrofonu a osy do 150 ms. Porovnat větu `SAY` s okamžikem kliknutí, o kterém se mluví.
4. Ruční zkoušky zařízení, které musí udělat člověk:

| Zkouška | Očekávání |
| --- | --- |
| USB náhlavní souprava: odpojit během nahrávání | varování do 2 s, pokračuje vestavěný mikrofon, v ose `MIC LOST` a `MIC BACK` |
| totéž a soupravu vrátit | fungující zařízení zůstává (R4), žádné další přepnutí |
| Bluetooth sluchátka: vypnout | jako USB |
| jediný mikrofon zakázat v nastavení zvuku a zase povolit | varování trvá, po povolení `MIC BACK` |
| změnit výchozí výstup během přehrávání videa | `computer.wav` pokračuje z nového výstupu |
| notebook vyjmout z doku se zvukem přes dok | obě stopy přejdou na vestavěná zařízení |

## 6. Rozdělení práce

Podle trvalého pokynu: jednotlivé úkoly na subagenta Opus 5.5 s úsilím high, kde na ně stačí, a nic, kde hrozí chybné provedení.

| Krok | Kdo | Důvod |
| --- | --- | --- |
| Z0, Z1 | hlavní relace | Měření na skutečném zařízení; výsledek rozhoduje o R1. |
| Z2 | **subagent Opus 5.5, high** | Jedna podmínka a test, přesně zadané. |
| Z3 | hlavní relace | Jádro změny; pravidlo s minimem okna se snadno napíše skoro správně. |
| Z4, Z5 | hlavní relace | Vlákna, pořadí startu a zastavení, soukromé rozhraní sounddevice. |
| Z6 | hlavní relace | Malé, ale v okně, které má vlastní stavový automat. |
| Z7 | **subagent Opus 5.5, high** | Kopie vzoru `_mute_events` s testy; vstupem je hotový tvar `gaps` ze Z4. |
| Z8 | hlavní relace | Vlákno s COM a knihovnou `soundcard`; chyba se projeví až na skutečném zařízení. |
| Z9 | **subagent Opus 5.5, high** | Vyjmenované odstavce dokumentace. |
| Z10 | hlavní relace a uživatel | Ruční zkoušky potřebují člověka u zařízení. |

Po každém kroku subagenta přečíst diff a spustit testy v hlavní relaci. Z2 může běžet souběžně se Z1; Z7 až po Z4.

## 7. Rizika

| Riziko | Ošetření |
| --- | --- |
| Latence 0,5 s se na jiném zařízení (USB, Bluetooth, jiný ovladač) chová jinak než na zdejším Realteku | Zarovnání podle hodin (Z3, Z4) ztrátu doplní tichem a zapíše `padded_ms`, takže osa sedí i tak. Když bude `padded_ms` na některém zařízení trvale vysoké, přijde na řadu pomocný proces pro mikrofon. |
| Chování PortAudio při odpojení zařízení neznám (jestli zavolá `finished_callback`, jestli zavření proudu neuvízne) | Hlídač se řídí jen tím, že nepřicházejí bloky. Zavírání má limit. Rozhodnou ruční zkoušky Z10. |
| `sd._terminate()` zavře i jiný proud téhož procesu | V procesu nahrávače jiný není (ověřeno hledáním v `src`); v testu hlídat, že se volá jen ze zapisovače mikrofonu. |
| Doplnění ticha uprostřed slova zhorší přepis | Stane se jen při skutečné ztrátě, kdy slovo chybí tak jako tak; po Z1 má jít o výjimku. |
| Ticho při výpadku svádí Whisper k vymyšleným titulkům | Živý přepis má bránu ticha, filtr vymyšlených titulků zůstává; řádky `MIC LOST` agentovi řeknou, že tam řeč není. |
| Změna rozhraní `AudioRecorder` rozbije testy, které ho volají přímo | Dva vyjmenované testy se přepisují v Z4. |
| Staré manifesty bez nových polí | `AudioInfo.from_dict` čte tolerantně; test se starým manifestem. |

## 8. Podmínky dokončení

- [x] R1 až R7 potvrzeny nebo upraveny.
- [x] Z0: výchozí číslo ze zátěžového měření zapsáno.
- [x] Z1: zátěžové měření ukazuje ztrátu pod 100 ms.
- [x] Z2, Z3: testy hodin a `TrackAligner` procházejí.
- [ ] Z4: délka `audio.wav` se od osy liší nejvýš o 150 ms v zátěžovém měření i na desetiminutové nahrávce; mikrofon nezačíná před nulou osy. *(Zátěžové měření a dvacetisekundová nahrávka splněny; desetiminutová nahrávka čeká na ruční zkoušku.)*
- [x] Z5, Z6: výpadek falešného zařízení dá varování, ticho a nový pokus; nahrávání se nezastaví.
- [x] Z7: `MIC LOST` a `MIC BACK` v časové ose, legenda doplněna.
- [x] Z8: stopa počítače přejde na nový výchozí výstup.
- [ ] Z10: celá sada, CI a ruční zkoušky zařízení mají zapsaný výsledek.
- [x] Revize z 14. 11. má B1 a B2 v tabulce „Stav po opravách“.
