# Implementační plán: okno přežije příkaz, který ho spustil (A2)

Datum: 15. 11. 2026. Verze plánu: 1. Stav: **P0 až P8 implementováno a commitnuto 15. 11. 2026; z P9 zbývá zkouška v Codexu a Cursoru (uživatel) a nahrávání v okně spuštěném mimo strom**.

Průběh realizace 15. 11. 2026: R1 až R6 potvrzeny uživatelem („Ano, implementuj“). P0: 87 dotčených testů prošlo před změnou. P1 a část P6 (`doctor`) udělali dva subagenti Opus 5.5 (úsilí high); oba diffy jsem přečetl a testy spustil znovu. P2 až P5, volbu `--start`, P7 a P8 jsem dělal v hlavní relaci (P8 proti plánu také: zkouška vyšla z pokusu, který jsem už měl hotový).

Odchylky od plánu:

- **Diagnóza platí jen pro start z jednorázového příkazu.** Požadavek na start nese `owner` (`command` pro `--detach`, `process` pro server MCP a pro okno, které otevírá editor) a `start`. Okno spuštěné serverem MCP značku nikdy nedostane, protože server žije dál; jeho pozdější pád nebo restart počítače by se jinak vyhodnotil jako ukončení hostitelem. Našel jsem to při kontrole vlastní logiky, v plánu to chybělo.
- **Kontrola tracebacku v logu odpadla.** Zalogovaná, ale neškodná výjimka by diagnózu potlačila a agent by druhý start nezkusil. Opačný omyl (okno spadne samo do 3 s) stojí jen jeden start mimo strom.
- **Okno spuštěné mimo strom se neposílá mimo strom znovu.** Když skončí bez značky, je to `WINDOW_EXITED`, ne výzva k dalšímu startu.
- **Když start mimo strom nejde a okno se spustí přímo, spouštěč to zapíše do požadavku** (`record_start`), aby se jeho konec posuzoval jako konec potomka.
- **Editor: důkaz zůstává.** Po `closed` s `reason` se startovní soubory neuklízejí, takže opakovaný `wait --editor` vrátí totéž.
- `--log-file` přesměruje i popisovače 1 a 2 (výstup nativního kódu), nejen `sys.stdout` a `sys.stderr`.
- Čtení jobu je v novém `platform/windows_jobs.py`; `doctor` bere řetěz předků do 12 úrovní (spouštěcí skripty a shelly jdou první).

Ověření (P9):

| Zkouška | Výsledek |
| --- | --- |
| `ruff check`, `ruff format --check`, celá sada jednotkových testů na Windows | čisté; 1235 testů prošlo |
| Skutečný nahrávač a editor, `--start direct` i `outside` | `ready`, log se plní, po zavření `cancelled` / `closed`. U `outside`: rodič `WmiPrvSE.exe`, `WATCH_ME_HOME` volajícího došel až k oknu, editor spustil pracovní proces přepisu |
| Skutečný nahrávač v náhradním hostiteli (job s `KILL_ON_JOB_CLOSE`), dvě kola | 1. kolo: `start: direct`, okno skončilo s jobem, `wait` vrátil `WINDOW_ENDED_WITH_COMMAND` a `next`, vznikl `window-start.json`. 2. kolo (`auto`): `start: outside`, okno zavření jobu přežilo a zapsalo `outlived_launcher` |
| Totéž jako automatický test se zástupným oknem (`tests/unit/test_host_job_standin.py`) | prochází, 3 s |
| Doba celého příkazu, 10 startů, medián: `run --detach` | přímo 874 ms, mimo strom 976 ms (+102 ms) |
| Doba celého příkazu, 10 startů, medián: `edit --detach` | přímo 902 ms, mimo strom 1 046 ms (+144 ms) |
| `doctor` z Claude Code | `host_job`: v jobu, limity `0x0`; `explorer.exe` v jobu není |

Neověřeno: Codex a Cursor (P9 bod 5); nahrávání v okně spuštěném mimo strom (hák myši, UI Automation a živý přepis startují až po stisku Record, který jsem nemačkal; pracovní proces editoru v takovém okně běžel); stroj s blokovaným WMI nebo PowerShellem.

**Nález mimo rozsah, platí i pro commit `8375e67`:** když se garbage collector spustí v pracovním vlákně ovládacího okna (ukládání nahrávky, otevírání editoru) a uklidí objekty Qt, proces skončí voláním `abort`. V testech to nastane, když po testech editoru běží testy okna a úklid vyjde do pracovního vlákna; na čistém `8375e67` to vyvolá vynucený `gc.collect()` v `ProcessingWorker.run` po `test_editor_process.py`. Celá sada v běžném pořadí prochází. Nové testy z tohoto plánu jen posunuly okamžik úklidu, takže to v jedné kombinaci souborů spadlo samo. Příčinu našla a opravila samostatná relace, oprava je ve stejném commitu jako tento plán: sedm tlačítek `ControlWindow` se přidávalo do rozvržení, které ještě nepatřilo oknu, takže je vlastnil Python i okno a při úklidu mimo vlákno GUI se smazala dvakrát. Rozvržení se teď připojí k oknu dřív, pracovní vlákna nahrávače mají automatický úklid vypnutý (`editor/workers.py`, jako editor) a testy uklízejí po každém testu na hlavním vlákně. Podle té relace skutečnému oknu při ukládání pád nehrozil. Stejný vzor měl i editor (hlavní okno, náhled, dialog instrukcí, okno Mouse, dialog Render) a dialog Settings nahrávače; opraveno následným commitem stejným přeskládáním. Test vlastnictví z první opravy nic nehlídal, protože `findChildren` předá vše, co vrátí, do vlastnictví C++; nový test (`tests/unit/test_widget_ownership.py`) hledá objekty přes seznam garbage collectoru.

Zdroj: nález A2 v [revizi z 14. 11. 2026](watch-me-review-2026-11-14.md). Plán navazuje na [opravy spouštěčů](implementation-plan-launcher-fixes.md) (A4 až A6), které A2 záměrně vynechaly. Chování Claude Code jsem změřil na tomto stroji; hostitele, který okno zabíjí, jsem nahradil job objektem s `KILL_ON_JOB_CLOSE` (oddíl 2.2). V Codexu ani v Cursoru jsem nic nespouštěl.

## 1. Výsledek a hranice

Po změně:

- Když hostitel ukončí okno spolu s příkazem, agent to pozná z odpovědi `wait` (nový kód `WINDOW_ENDED_WITH_COMMAND` místo obecného `WINDOW_EXITED`) a dostane v ní přesný další příkaz.
- Druhý start otevře okno mimo strom procesů hostitele (přes WMI). Takové okno zavření jobu hostitele přežije.
- Plugin si výsledek pamatuje, takže další relace v tom hostiteli už startují rovnou druhým způsobem a okno uživateli neproblikne.
- V hostiteli, který okno nezabíjí (dnes ověřeně Claude Code), se nemění nic a start není pomalejší.
- `doctor` vypíše, v jakém jobu příkazy hostitele běží. Je to podklad pro zkoušku A1, ne součást běžného startu.

Mimo rozsah (záměrně):

| Co | Proč |
| --- | --- |
| Zkouška ve třech hostitelích s výchozími oprávněními (A1) | Musí ji udělat uživatel; tento plán jí dává čitelné výsledky (krok P9). |
| Sandbox Codexu (soukromá plocha, zákaz zápisu mimo pracovní prostor) | Okno v něm nejde zobrazit vůbec; řeší to schválení běhu mimo sandbox, jak už popisuje `docs/installation.md:159-162`. |
| Okno ukončené později než s příkazem (konec tahu, zavření hostitele) | Start mimo strom to řeší jako vedlejší účinek, ale rozpoznání takového konce plán nepřidává. |
| Job zavaděče uv (ukončení zavaděče ukončí okno) | Souvisí s prostředím (A3) a s prioritou háku (B5). |
| Vlastník relace (A7), zámek místo čísla procesu (A10) | Jiné nálezy; plán na ně jen upozorňuje u rizik. |
| Linux a macOS | `start_new_session=True` zůstává; obdoba startu mimo strom (`systemd-run`, `launchctl`) patří k portaci (G2). |

## 2. Zjištění

### 2.1 Aktuální kód

| Místo | Stav dnes | Důsledek pro realizaci |
| --- | --- | --- |
| `platform/process.py:85-108` (`spawn_detached`) | Příznaky `CREATE_NEW_PROCESS_GROUP \| DETACHED_PROCESS \| CREATE_NO_WINDOW`; log se předává jako zděděný popisovač | Přidat pokus o vystoupení z jobu. Start přes WMI popisovače nedědí, okno si log musí otevřít samo. |
| `host/runner.py:163-193`, `host/editor_launcher.py:141-164` | Dvě místa, která okno spouštějí a pak čekají na `ready` | Obě přejdou na jednu funkci, která vybere způsob startu. |
| `host/startup.py:61-75` (`create_request`) | Požadavek nese `owner_pid`, tedy číslo procesu spouštěče | Okno podle něj pozná, že spouštěč skončil. Nic nového se předávat nemusí. |
| `host/startup.py:94-98`, `:158-201` | Okno píše `startup.result.json` (`phase`, `pid`); zapisuje jen okno | Sem přijde značka, že okno spouštěč přežilo. Stejný soubor má nahrávač i editor. |
| `host/runner.py:206-224` (`session_status`) | Mrtvé okno v nekonečném stavu → `failed / WINDOW_EXITED` | Tady se rozliší konec spolu s příkazem. |
| `host/editor_session.py:97-109` (`read_editor_event`) | Mrtvý editor → `closed` se zprávou | Totéž pro editor; `closed` dostane pole `reason`. |
| `host/cli.py:66-72` (`setup_logging`) | Log jde na `sys.stderr`; ten je u `pythonw.exe` bez zděděných popisovačů `None` | Volba `--log-file` pro okno spuštěné mimo strom. |
| `ui/control_window.py:148` | Nahrávací okno samo spouští editor (tlačítko Video Editor) | Tady zůstane přímý start; okno už je tam, kde má být. |
| `host/mcp_server.py:204`, `:634` | Server MCP spouští okna stejnou cestou | Platí pro něj stejný výběr způsobu startu. |
| `tests/manual/hosts.md` | Start nahrávače medián 409 ms, editoru 842 ms (měření z 13. 11., nezopakoval jsem ho) | Měřítko pro cenu startu přes WMI. |

### 2.2 Pokusy (Windows 11, tento stroj, 15. 11. 2026)

| Pokus | Výsledek |
| --- | --- |
| Řetěz předků příkazu spuštěného z Claude Code | `claude.exe`, všechny shelly i Python jsou v jobu; `explorer.exe` není. |
| Limity jobu hostitele (čtené procesem mimo job zavaděče uv) | `0x0`: bez `KILL_ON_JOB_CLOSE`, vystoupení z jobu nepovoleno. Sedí s tím, že tu okno příkaz přežilo. |
| Limity jobu, jak je vidí Python z `.venv` | `0x3000`: to je job zavaděče uv (`KILL_ON_JOB_CLOSE`, tiché vystoupení potomků). `IsProcessInJob` je proto pravda vždy a o hostiteli nic neříká. |
| `CREATE_BREAKAWAY_FROM_JOB` z procesu v jobu zavaděče i hostitele (tak běží příkaz `run`) | Spuštění projde, proces v jobu hostitele zůstane. |
| Totéž z procesu, který je jen v jobu hostitele | Odmítnuto, `ERROR_ACCESS_DENIED` (5). |
| Cena: dotaz na job, `CreateProcess` s příznakem a bez něj | 2 µs; 1,3 ms a 1,3 ms. |
| Cena: pomocný proces, který přečte limity jobu hostitele | 37 ms. |
| Start přes WMI (`Invoke-CimMethod Win32_Process Create` z PowerShellu 5.1), 9 běhů | 196 až 452 ms, návratová hodnota 0. |
| Proces spuštěný přes WMI | Rodič `WmiPrvSE.exe`, zavaděč není v žádném jobu, relace 1, `WinSta0\Default`, Qt vidí obě obrazovky, pracovní adresář podle parametru, argumenty s mezerou a s `ž` beze změny. |
| Prostředí procesu z WMI bez dalšího nastavení | Čerstvé prostředí uživatele (45 proměnných); proměnné volajícího chybí. |
| Prostředí předané v `Win32_ProcessStartup.EnvironmentVariables` | **Nahradí celé prostředí.** S jednou proměnnou nemá proces ani `PATH`. Se všemi 104 proměnnými volajícího (5 754 znaků) je prostředí shodné s volajícím včetně diakritiky. |
| `pythonw.exe` spuštěný přes WMI | `sys.stdout` je `None`. `python.exe` by otevřel viditelné okno konzole. |
| **Náhrada zabíjejícího hostitele:** spouštěč v jobu s `KILL_ON_JOB_CLOSE` spustí jeden proces dnešním způsobem (s pokusem o vystoupení) a jeden přes WMI; pak se job zavře | Vystoupení odmítnuto (5), start bez něj. Po zavření jobu: **dnešní způsob mrtvý, WMI živý.** |

Co z toho plyne:

1. Předpověď z limitů jobu je slabá. `KILL_ON_JOB_CLOSE` na jobu, který žije s celou aplikací, oknu nevadí; a hostitel bez toho příznaku může procesy ukončit výslovně. Spolehlivý je jen pozorovaný fakt, jestli okno příkaz přežilo.
2. Pokus o vystoupení z jobu je zadarmo, ale v Claude Code nic nedělá a nikde jinde jsem jeho přínos neověřil.
3. Start přes WMI funguje a přežije i zavření jobu. Stojí 0,2 až 0,45 s, proto má být jen tam, kde je potřeba.

## 3. Rozhodnutí

**R1 – rozhoduje pozorování, ne předpověď.** Okno si po startu hlídá proces spouštěče. Když spouštěč skončí a okno žije ještě 3 s, zapíše do `startup.result.json` značku `outlived_launcher`. Najde-li později `wait` nebo `status` okno mrtvé, spouštěč mrtvý a značku nikde, je to konec spolu s příkazem. Revize navrhovala vracet `"survives_command": false` už z `run --detach`; od toho ustupuji, protože by to byl odhad (bod 1 výše). Limity jobu ukáže jen `doctor`.

**R2 – výchozí je dnešní přímý start; start mimo strom až po prokázaném ukončení.** Alternativa je spouštět přes WMI vždy: jedna cesta pro všechny hostitele, okno nikdy nezávisí na hostiteli. Nedoporučuji ji jako výchozí ze tří důvodů: přidá 0,2 až 0,45 s ke každému startu (nahrávač dnes 0,4 s), závisí na PowerShellu a WMI, které může firemní politika blokovat (oddíl 6), a přímý start by stejně musel zůstat jako záloha.

**R3 – plugin si ukončení pamatuje pro celý stroj, ne pro hostitele.** Po prvním prokázaném ukončení zapíše `window-start.json` do složky stavu a další starty v režimu `auto` jdou mimo strom ve všech hostitelích. Rozpoznávat hostitele podle jmen procesů by bylo křehké a start mimo strom funguje i tam, kde není nutný. Soubor jde smazat; `--start direct` ho přebije.

**R4 – druhý start dělá agent, ne `wait`.** `wait` vrátí `WINDOW_ENDED_WITH_COMMAND` a v poli `next` celý příkaz (`run --detach --start outside`). Agent ho spustí jednou. Automatický restart uvnitř `wait` by znamenal, že čtecí příkaz zakládá relaci s novým id; A10 už dnes vytýká, že čtenář mění stav.

**R5 – okno spuštěné mimo strom dostane prostředí volajícího, ne čerstvé prostředí uživatele.** PowerShell předá celé své prostředí do `Win32_ProcessStartup` (vyzkoušeno). Okno se tak chová stejně jako při přímém startu: platí `WATCH_ME_HOME`, `WATCH_ME_CONFIG`, `WATCH_ME_NO_TOUCHPAD` i `PATH` hostitele a v okně není potřeba žádný nový kód.

**R6 – pokus o vystoupení z jobu se přidá, i když je jeho přínos neověřený.** Stojí nulu a při odmítnutí se start zopakuje bez příznaku. Pomůže jen u hostitele, jehož job vystoupení dovoluje; jestli takový existuje, ukáže až A1. Pokud ho nechceš v kódu bez důkazu, krok P1 se dá vypustit a zbytek plánu na něm nezávisí.

## 4. Kroky realizace

Po každém kroku spustit jeho cílené testy. P1, P6 a P8 jsou přesně zadané a kryté testy, hodí se pro subagenta Opus 5.5 (úsilí high). P2 až P5 a P7 nechávám v hlavní relaci: jde o pořadí zápisů mezi procesy a o text, podle kterého jedná agent.

### P0 – výchozí stav

Spustit dotčené testy před změnou: `test_startup.py`, `test_runner.py`, `test_editor_launcher.py`, `test_editor_process.py`, `test_process_commands.py`, `test_mcp_server.py`, `test_host_packaging.py`.

### P1 – pokus o vystoupení z jobu (`platform/process.py`)

- `spawn_detached` na Windows přidá `CREATE_BREAKAWAY_FROM_JOB` (`0x01000000`).
- Při `OSError` s `winerror == 5` zopakuje `Popen` bez příznaku. Jiná chyba se šíří jako dnes.
- Test: náhradní `Popen`, který poprvé vyhodí `PermissionError(winerror=5)`; druhé volání příznak nemá a vrácené číslo procesu je z něj.

### P2 – start mimo strom hostitele (nový `platform/outside_start.py`)

- `start_outside(args, cwd) -> int` (jen Windows) spustí `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -NonInteractive -Command <skript>`; když tam soubor není, hledá `powershell` v `PATH`.
- Příkazový řádek (`subprocess.list2cmdline(args)`) a pracovní adresář jdou PowerShellu v proměnných prostředí, takže se v jeho skriptu nic neuvozuje. Skript je konstanta modulu: sestaví `EnvironmentVariables` z vlastního prostředí bez obou pomocných proměnných a bez jmen začínajících `=`, zavolá `Invoke-CimMethod -ClassName Win32_Process -MethodName Create` a vypíše `ReturnValue ProcessId`.
- PowerShell se pouští s `CREATE_NO_WINDOW` a s limitem 15 s.
- Chyby (`OutsideStartError` s polem `reason`): PowerShell chybí, limit vypršel, nenulová návratová hodnota (2 přístup odepřen, 8 neznámá chyba, 9 cesta nenalezena, 21 neplatný parametr), nečitelný výstup.
- Volba `--log-file <cesta>` (skrytá, globální jako `--config`) v `host/cli.py`: před `setup_logging` otevře soubor pro připisování, nastaví `sys.stdout` a `sys.stderr` a zapne `faulthandler` do téhož souboru. Okno spuštěné mimo strom ji dostane vždy; přímý start zůstává u zděděného popisovače.
- Testy: skript dostane správné proměnné a argumenty (náhradní `subprocess.run`); `0 1234` → 1234; `2 0`, prázdný výstup, limit a chybějící PowerShell → `OutsideStartError`; `--log-file` přesměruje log i traceback.

### P3 – výběr způsobu startu (nový `host/window_start.py`)

- `start_window(config, args, log, start="auto") -> WindowStart(pid, start, note)`.
  - `direct`: `spawn_detached`.
  - `outside`: `start_outside`; při `OutsideStartError` přímý start a `note` s důvodem.
  - `auto`: `outside`, když existuje `window-start.json` se záznamem o ukončení, jinak `direct`. Mimo Windows vždy `direct`.
- `remember_ended_with_command(evidence)` a `remembered()` čtou a píšou `<složka stavu>/window-start.json` (`{"start": "outside", "since": …, "evidence": {…}}`). Selhání zápisu se jen zaloguje; druhý start řídí pole `next` z R4, paměť je pohodlí pro další relace.
- `runner._launch_control_window_ready` a `editor_launcher._launch_editor_ready` volají `start_window`; do výsledku `run --detach` a `edit --detach` přibude `"start": "direct" | "outside"` a případně `"start_note"`.
- `control_window.py:148` předá `start="direct"`.
- `.gitignore`: `window-start.json` (ve vývojovém režimu je složka stavu checkout).
- Testy: tři režimy, paměť, pád na přímý start s poznámkou, jiný systém než Windows.

### P4 – okno zapíše, že spouštěč přežilo (`host/startup.py`)

- Jádro bez Qt: `LauncherWatch(owner_pid, grace_s=OUTLIVED_AFTER_S)` s metodou `tick(now) -> bool`; vrátí pravdu jednou, když je spouštěč `grace_s` sekund pryč. `OUTLIVED_AFTER_S = 3.0`.
- `watch_window` po `ready` nechá běžet časovač po 1 s; když `tick` vrátí pravdu, zavolá `acknowledge(request, "ready", session_id=…, outlived_launcher=True)` a časovač zastaví. Dokud spouštěč žije (server MCP), jen se dál ptá.
- `ended_with_command(request, log) -> bool`: výsledek má `phase == "ready"`, nemá `outlived_launcher`, `owner_pid` nežije a konec logu neobsahuje `Traceback`.
- Testy: značka se zapíše až po prodlevě, ne dřív a ne za živého spouštěče; `ended_with_command` ve čtyřech kombinacích; `cleanup_completed` dál uklízí i výsledek se značkou.

### P5 – rozpoznání v `wait` a `status`

- `runner.session_status` (ř. 220-223): když `startup.ended_with_command(…)`, zapíše `error_code = "WINDOW_ENDED_WITH_COMMAND"`, zprávu a zavolá `remember_ended_with_command`. Jinak dnešní `WINDOW_EXITED`. Do výsledku přidá `next` s příkazem pro druhý start.
- `editor_session.read_editor_event`: mrtvý editor, který skončil s příkazem, vrátí `closed` s `reason: "ended_with_command"`, se zprávou a s `next` (`edit --detach --start outside --session …`). `wait_for_editor` pole `reason` a `next` propustí.
- MCP: stejná pole ve výsledcích nástrojů čekání; žádný nový nástroj.
- Testy: obě cesty, zápis paměti, beze změny pro okno se značkou a pro okno s tracebackem v logu.

### P6 – CLI a `doctor`

- `run` a `edit`: volba `--start {auto,direct,outside}`, výchozí `auto`.
- `doctor`: oddíl `process` (jen Windows): řetěz předků se jménem a příznakem „v jobu“, limity jobu hostitele přečtené pomocným procesem základního interpretu (`sys._base_executable`, 37 ms) a obsah `window-start.json`. Na výsledek `doctor` (ok / chyba) nemá vliv.
- Testy: rozbor voleb; tvar oddílu; `doctor` nespadne, když pomocný proces selže.

### P7 – skilly a dokumentace

- `skills/*/SKILL.md`: nejvýš tři řádky do části o chybách startu: při `WINDOW_ENDED_WITH_COMMAND` (nebo `closed` s `reason: "ended_with_command"`) spusť jednou příkaz z pole `next`; když skončí stejně, použij MCP, jinak to řekni uživateli. `closed` s tímto důvodem **neznamená**, že uživatel editor zavřel. SKILL.md je už teď dlouhý (A8), proto nic dalšího.
- `skills/*/references/agent-startup.md` (dvě shodné kopie, shodu hlídá test): oddíl s vysvětlením a s tím, co znamená `start` a `start_note` ve výsledku.
- `docs/installation.md:150-172`: nahradit větu „use the MCP server“ popisem nového chování; zmínit `window-start.json` a `--start`.
- `watch-me-spec.md`: řádek v tabulce chyb, pole `start` u `run --detach`.
- `tests/manual/hosts.md`: nové sloupce pozorování (hodnota `start`, výskyt `WINDOW_ENDED_WITH_COMMAND`, oddíl `process` z `doctor`).
- Revize: řádek A2 v tabulce „Stav po opravách“.

### P8 – zkouška s náhradním hostitelem (Windows, bez okna)

Jednotkový test, který opakuje pokus z oddílu 2.2 proti skutečnému kódu, s malým zástupným „oknem“ (skript, který potvrdí `ready` a točí `LauncherWatch` ve smyčce):

1. Spouštěč v jobu s `KILL_ON_JOB_CLOSE`, start `direct`; job se zavře → `session_status` vrátí `WINDOW_ENDED_WITH_COMMAND` a paměť je zapsaná.
2. Totéž se `start="outside"` → zástupné okno žije i po zavření jobu a zapíše `outlived_launcher`.

Test se přeskočí, když WMI start vrátí chybu (blokovaný stroj), a řekne proč. Trvá několik sekund kvůli prodlevě z P4; prodleva se v testu zkrátí.

### P9 – ověření

1. `ruff check`, celá sada jednotkových testů na Windows.
2. Skutečná okna na tomto stroji: `run --detach` a `edit --detach` s `--start direct` i `--start outside`; u obou `wait` vrátí `ready`, log se plní, okno jde zavřít a relace skončí jako `cancelled`. U `outside` navíc: hák myši, UI Automation a živý přepis běží (jsou to potomci okna, ne spouštěče).
3. Skutečné okno v jobu náhradního hostitele (ručně, skript z P8 se skutečným `run --detach`).
4. Změřit start nahrávače a editoru oběma způsoby (deset startů) a zapsat medián do tohoto plánu.
5. **Uživatel:** `doctor` a `Start Watch Me` v Codexu a v Cursoru s výchozími oprávněními; zapsat do `tests/manual/hosts.md`. Teprve tohle řekne, jestli některý hostitel okno opravdu zabíjí a jestli je prodleva 3 s správně.

## 5. Kontrolní seznam

- [x] P0 výchozí stav testů
- [x] P1 pokus o vystoupení z jobu
- [x] P2 start mimo strom a `--log-file`
- [x] P3 výběr způsobu startu a paměť
- [x] P4 značka `outlived_launcher`
- [x] P5 `WINDOW_ENDED_WITH_COMMAND` v `wait` a `status`
- [x] P6 `--start` a `doctor`
- [x] P7 skilly a dokumentace
- [x] P8 zkouška s náhradním hostitelem
- [x] P9 ověření (body 1 až 4); nahrávání v okně spuštěném mimo strom nevyzkoušeno
- [ ] P9 bod 5: Codex a Cursor s výchozími oprávněními (uživatel)

## 6. Rizika a co plán neřeší

| Riziko | Dopad | Co s tím |
| --- | --- | --- |
| Firemní politika blokuje vytváření procesů přes WMI (pravidlo Defenderu „Block process creations originating from PSExec and WMI commands“) nebo omezuje PowerShell | Start mimo strom selže | Pád na přímý start s `start_note`; pak zbývá MCP. Na tomto stroji blokováno není, jinde nevyzkoušeno. |
| Start PowerShellu přes WMI vypadá pro bezpečnostní nástroje podezřele | Záznam nebo upozornění u správce | Používá se až po prokázaném ukončení, ne při každém startu (R2). |
| Hostitel ukončuje procesy později než 3 s po konci příkazu | Okno zapíše značku a pozdější konec se ohlásí jako `WINDOW_EXITED` | Prodleva je konstanta; správnou hodnotu ukáže P9 bod 5. |
| Okno spadne samo do 3 s po konci spouštěče bez tracebacku (pád v nativním kódu) | Chybná diagnóza a zbytečný přechod na start mimo strom | Start mimo strom funguje i tady, stojí jen čas; `window-start.json` jde smazat. |
| Číslo procesu spouštěče dostane jiný proces | Značka se nezapíše, diagnóza spadne na `WINDOW_EXITED` | Zhorší se jen hlášení; souvisí s A10. |
| Okno spuštěné mimo strom žije dál i po zavření hostitele | Záměr; uživatel ho zavře sám | Popsat v `docs/installation.md`. |
| Dva agenti po `WINDOW_ENDED_WITH_COMMAND` spustí druhý start současně | Druhý dostane `ALREADY_RUNNING` | Dnešní chování, souvisí s A7. |
| V sandboxu Codexu WMI nejspíš nebude dostupné | Start mimo strom selže stejně jako přímý | Mimo rozsah; platí schválení běhu mimo sandbox. |
