# Watch Me – revize pluginu (14. 11. 2026)

Větev `fix/editor-transcription-state`, commit `f2f63fd`. Prošel jsem celý plugin: oba skilly, spouštěče, instalaci, hostovou vrstvu (CLI, MCP), nahrávání, Windows háky, přepis, editor, export a archivaci. Hledal jsem jen zásadní chyby návrhu a implementace, výkonnostní potíže a budoucí potíže s kompatibilitou. Drobnosti a málo pravděpodobné okrajové případy vynechávám.

Hlavní měřítko je zadání: **plugin musí běžet v Claude Code, Codexu a Cursoru na Windows.** Nálezy, které to ohrožují, jsou v části A a mají přednost před vším ostatním. Linux a macOS jsou v části G.

Předchozí revize `watch-me-review-2026-11-13.md` je o den starší. Co z ní v kódu stále platí, uvádím znovu se značkou „přetrvává“ a s původním označením; co je opravené, neopakuju.

## Stav po opravách (15. 11. 2026)

Podle [plánu oprav spouštěčů](implementation-plan-launcher-fixes.md). Změny jsou v commitu `c688bbb`.

| Nález | Stav | Co se změnilo |
| --- | --- | --- |
| A4 | vyřešeno | Návod `agent-startup.md` leží v `references/` obou skillů (dvě shodné kopie, shodu i odkazy v `SKILL.md` hlídá test) a `docs/agent-startup.md` zanikl. Chyby `UV_MISSING`, `PYTHON_MISSING` a `ENVIRONMENT_INVALID` nesou pole `root` (kde spustit `uv sync`) a `help` (cesta k návodu). Na Windows je píše PowerShell v UTF-8, bez PowerShellu zůstává původní text bez cest. Pokus: přes junction na `skills\watch-me` soubor `references\agent-startup.md` existuje; kořen se jménem `space ž` se v odpovědi vrátil beze změny z `.bat` i z `.sh`. |
| A5 | vyřešeno | `uv` se hledá jen tehdy, když chybí interpret v `.venv`; pořadí chyb při chybějícím prostředí se nezměnilo. `launch.sh` v Git Bashi použije `.venv/Scripts/python.exe`. Pokus: `watch-me.bat version` i `watch-me.sh version` vracejí kód 0 s `uv` v `PATH` i bez něj. |
| A6 | vyřešeno | Všech sedm příkazů podřízeného Pythonu skládá `platform/process.py::python_command` a vždy přidá `-I`; test hlídá, že jinde v balíčku ručně složený příkaz není. Okna běží v domovské složce uživatele, cesta ke konfiguraci se předává absolutní a relativní cesty v `config.json` se vztahují ke složce toho souboru. Pokus se skutečným oknem: `run --detach` ze složky se zastiňujícím `argparse.py` a s relativním `--config` otevřel okno (`wait` vrátil `ready`), složku šlo při otevřeném okně smazat a okno se po zavření ukončilo stavem `cancelled`. |

Jednotkové testy na Windows: 1137 prošlo, lint čistý. Neověřeno: nahrávka s řečí, hák myši, UI Automation a přepis jako podřízené procesy s `-I` ve skutečné relaci (ruční zkouška L8 bod 4 v plánu), Codex, Cursor, Linux a macOS mimo CI. Ostatní nálezy jsou beze změny.

## Jak číst sloupec Ověření

| Označení | Význam |
| --- | --- |
| **pokus** | spustil jsem to na tomto stroji (Windows 11, uv 0.12.16, Python 3.13.7 z prostředí pluginu) a uvádím výsledek |
| **přečteno** | cesta kódem je přečtená od začátku do konce, nespouštěl jsem ji |
| **předpoklad** | plyne z dokumentace nebo hlášení třetích stran; tady to vyzkoušet nešlo |

Nic z toho jsem nespouštěl v Codexu ani v Cursoru a nenahrával jsem novou relaci; nahrávací okno ani editor jsem neotvíral.

Části C, D a E (přepis, editor s exportem, ovládací okno s kreslicí vrstvou) četli tři pomocní agenti souběžně. Jejich hlavní tvrzení jsem po nich zkontroloval na citovaných řádcích; měření, která dělali oni, jsou u nálezů označená.

## Shrnutí – co řešit nejdřív

| # | Nález | Závažnost | Ověření |
| --- | --- | --- | --- |
| A1 | Celý tok není ověřený v žádném hostiteli s výchozími oprávněními | vysoká | přečteno |
| A2 | Okno přežije jen tehdy, když hostitel nezabíjí strom procesů; žádný pokus o vystoupení z jobu ani kontrola | vysoká | pokus + předpoklad |
| A3 | Prostředí (370 MB) žije u kódu: každá kopie a každá aktualizace pluginu ho vytváří znovu, a to rukama agenta | vysoká pro distribuci | pokus |
| A4 | Návod na opravu prostředí je mimo složku skillu; přes junction neexistuje | vysoká | pokus |
| A5 | Spouštěče hlásí `UV_MISSING` a `PYTHON_MISSING` při zdravém prostředí | střední až vysoká | pokus |
| A6 | Okna a pomocné procesy běží bez `-I` s projektem agenta na `sys.path`; drží jeho složku zamčenou | střední až vysoká | pokus |
| B1 | Stopa mikrofonu není svázaná s hodinami nahrávky, přepis se rozchází se snímky | vysoká | přečteno |
| B2 | Výpadek zvukového zařízení se nepozná | vysoká | přečteno |
| C1 | `watch-me transcribe` začíná od nuly, do konce nic neuloží a přepíše ruční úpravy | vysoká | přečteno |
| D1 | Automatická archivace žije jen s oknem editoru, začíná od nuly a zamyká staré nahrávky | vysoká | přečteno |
| D3 | Export stojí na volbě FFmpeg, která se ruší; verze FFmpeg není pod kontrolou | vysoká (kompatibilita) | přečteno |
| D4 | `transcript.json` se zapisuje neatomicky při každém segmentu; roztržený soubor znamená tichý nový přepis | střední až vysoká | přečteno |
| E1 | Tahy štětcem se celé opakují v každém sidecaru: až megabajty JSON za sekundu | vysoká | přečteno + změřeno |
| B3 | Každý tik ukládá plný snímek každé obrazovky: 2,3 GB a 28 800 souborů za hodinu | střední až vysoká | pokus |
| D2 | Seznam nahrávek se sestavuje v GUI vlákně procházením všech souborů | vysoká při větším archivu | přečteno + změřeno |
| B6 | Schránka a obsah prvků pod myší jdou agentovi bez filtru, včetně hesel ze správce hesel | střední až vysoká | přečteno |

Ostatní nálezy jsou střední a jsou popsané v částech níže. Doporučené pořadí prací je na konci.

---

## A. Běh v hostitelích na Windows

### A1 · Celý tok není ověřený v žádném hostiteli s výchozími oprávněními

**Závažnost:** vysoká · **Ověření:** přečteno (záznam v `tests/manual/hosts.md`)

Podle `tests/manual/hosts.md` (stav 13. 11.) běžely všechny zkoušky s vypnutou ochranou: Cursor s `--trust --force --sandbox disabled`, Claude Code s obcházením oprávnění, Codex s `danger-full-access` a schvalováním `never`. U všech tří hostitelů zůstává ve sloupci „Still required“ nahrávka s mluveným slovem (Record → Stop → Process → agent jedná) a oprava prostředí řízená agentem. V Cursoru je cesta přes MCP označená „BLOCKED / NOT VERIFIED“. Instalace jako plugin (kopie v cache hostitele) není vyzkoušená nikde; na tomto stroji je položka `~/.claude/plugins/cache/watch-me-local/watch-me/0.1.0` odkaz na vývojový checkout, takže ani tady neběží skutečná kopie.

Ověřený je tedy start editoru, krátké čekání a zavření okna. Neověřené je právě to, v čem se hostitelé liší: sandbox, schvalování, životnost procesů po skončení příkazu a časové limity nástrojů. Nálezy A2 až A6 jsou konkrétní místa, kde to podle kódu selže nebo může selhat.

**Návrh:** než se bude pokračovat s funkcemi, projít v každém hostiteli s výchozím nastavením tři scénáře: nahrávka s řečí až po akci agenta, start po čisté instalaci pluginu (bez `.venv`) a start ze složky cizího projektu v Pythonu. Do `run --detach` přidat samokontrolu z A2, aby se selhání poznalo z výsledku, a ne až z okna, které zmizelo.

### A2 · Okno přežije jen tehdy, když hostitel nezabíjí strom procesů

**Závažnost:** vysoká · **Ověření:** struktura procesů pokusem, chování hostitelů předpoklad

`platform/process.py:73-78` spouští okno s příznaky `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW`. Chybí `CREATE_BREAKAWAY_FROM_JOB` a chybí jakákoli kontrola, jestli proces nezůstal v jobu hostitele. Příznaky „odpojení“ řeší jen konzoli a Ctrl+C. Pokud hostitel spouští příkazy v job objektu s `KILL_ON_JOB_CLOSE`, okno skončí s příkazem, který ho spustil.

K tomu `.venv\Scripts\python.exe` není interpret, ale 47kB zavaděč uv, který spustí skutečný Python jako podřízený proces (pokus: `sys.executable` je zavaděč, `sys._base_executable` je `%APPDATA%\uv\python\cpython-3.13-…\python.exe`, PID se liší). Každé okno jsou tedy dva procesy a okno je až vnuk příkazu. Ukončení zavaděče ukončí i okno.

Dokumentace to pro sandbox Codexu přiznává (`docs/installation.md:159-162`). Hlášení `openai/codex#14875` ale popisuje totéž i mimo sandbox: odpojený potomek jednorázového volání nástroje je ukončen, jakmile volání skončí. Agent pak z `wait` dostane `failed / WINDOW_EXITED` a uživatel vidí okno, které se objevilo a zmizelo.

**Návrh:**
1. Zkusit `CREATE_BREAKAWAY_FROM_JOB`; když ho job nedovolí (`ERROR_ACCESS_DENIED`), spustit znovu bez něj.
2. Po potvrzení připravenosti zjistit `IsProcessInJob` a limity jobu a vrátit to ve výsledku (`"survives_command": false`). Skill pak ví, že má přejít na MCP, a nečeká na `WINDOW_EXITED`.
3. Mít záložní cestu, která startuje mimo strom hostitele: `Win32_Process.Create` přes WMI, naplánovaná úloha na jedno spuštění nebo `explorer.exe` se zástupcem. Rodičem je pak systémová služba a job hostitele se na proces nevztahuje.

### A3 · Virtuální prostředí žije u kódu, takže ho každá kopie pluginu potřebuje znovu

**Závažnost:** vysoká pro distribuci · **Ověření:** pokus (velikost), přečteno

`scripts/launch.bat:9-12` vyžaduje `%WM_ROOT%\.venv\Scripts\python.exe`. Stav (config, model, FFmpeg) se po opravě H3 přestěhoval do `~/.watch-me`, prostředí ale zůstalo u kódu. Důsledky:

- Prostředí má 370 MB (změřeno). Každý hostitel má vlastní kopii pluginu (`~/.claude/plugins/cache/…/<verze>/`, `~/.codex/plugins/cache/…/local/`, `~/.cursor/plugins/local/`), takže tři hostitelé jsou přes 1 GB a tři stahování.
- Po každé aktualizaci pluginu vznikne nová složka bez `.venv`. První start skončí `PYTHON_MISSING` a agent má sám spustit `uv sync` ve složce mimo svůj pracovní prostor, se sítí a mimo sandbox (`docs/installation.md:242-244` to přiznává). To je nejkřehčí krok celého řetězce a provádí ho agent podle dokumentu, ke kterému se nemusí dostat (A4).
- Staré kopie prostředí v cache nikdo neuklízí.
- Instalace je editovatelná (`_editable_impl_watch_me.pth` s absolutní cestou) a `pyvenv.cfg` míří na Python spravovaný uv v `%APPDATA%\uv\python\cpython-3.13-windows-x86_64-none`. Přesun složky, `uv python uninstall` nebo aktualizace záplatové verze prostředí rozbije.

**Návrh:** jedno sdílené prostředí ve složce stavu, například `~/.watch-me/venv/<otisk uv.lock>`, instalované needitovatelně. Spouštěč nastaví `UV_PROJECT_ENVIRONMENT` a kód načte z kopie pluginu. Vytvoření prostředí patří do `setup` (jeden příkaz stejného spouštěče), ne do PowerShellu, který agent skládá podle návodu. Do budoucna stojí za zvážení samostatné sestavení bez uv (PyInstaller nebo Nuitka) aspoň pro Windows.

### A4 · Návod na opravu prostředí leží mimo složku skillu a přes junction je nedostupný

**Závažnost:** vysoká · **Ověření:** pokus

Oba skilly odkazují na `../../docs/agent-startup.md` (`skills/watch-me/SKILL.md:30` a `:53`, `skills/watch-me-editor/SKILL.md:30` a `:45`). Ten dokument obsahuje celý postup pro `UV_MISSING`, `PYTHON_MISSING`, `ENVIRONMENT_INVALID` a `SETUP_REQUIRED`.

Doporučená instalace jsou odkazy na skilly (`scripts/install-hosts.ps1`), a je to jediná cesta ověřená od začátku do konce. Windows ale `..` vyhodnocuje textově, ještě než dojde na junction. Z `~\.claude\skills\watch-me\..\..\docs` se stane `~\.claude\docs`, které neexistuje. Pokus s junctionem na `skills\watch-me`: `Test-Path` vrací `False`, `path.resolve` v Node (tak cesty počítají nástroje hostitelů) dává neexistující soubor. Při selhání startu tak agent nemá podle čeho postupovat a začne improvizovat.

Funguje to jen při instalaci jako plugin, kde se kopíruje celý repozitář.

**Návrh:** návod přesunout do `skills/<skill>/references/` (podle specifikace Agent Skills mají být odkazované soubory uvnitř složky skillu). Navíc do každé chybové odpovědi spouštěče přidat absolutní cestu k návodu, spouštěč `WM_ROOT` zná.

### A5 · Spouštěče hlásí chybějící součást, i když nic nechybí

**Závažnost:** střední až vysoká · **Ověření:** pokus

1. **`uv` se vyžaduje, i když se nepoužije.** `scripts/launch.bat:4-8` a `scripts/launch.sh:3-6` skončí s `UV_MISSING`, pokud `uv` není v `PATH`. Běžný start přitom `uv` nevolá, jen spustí Python z `.venv`. Pokus: s úplným prostředím a `PATH` bez `%USERPROFILE%\.local\bin` vrátí `watch-me.bat version` kód 20. Proces hostitele mívá jiný `PATH` než terminál uživatele (aplikace spuštěná před instalací uv, sandbox s omezeným prostředím). Agent pak podle návodu instaluje uv přes winget, tedy síť a schvalování kvůli ničemu.
2. **`.sh` na Windows nenajde Python.** `scripts/launch.sh:7` zná jen `.venv/bin/python`. Nástroj Bash v Claude Code na Windows je Git Bash a komentář ve `watch-me.sh` s Git Bashem počítá. Pokus: `sh skills/watch-me/scripts/watch-me.sh version` vrátí `PYTHON_MISSING`, kód 22, i když je prostředí v pořádku. Agent, který si v Bashi vybere `.sh`, pak „opravuje“ zdravé prostředí přes `uv sync`.

**Návrh:** `UV_MISSING` hlásit jen tehdy, když chybí `.venv` a uv je opravdu potřeba. V `launch.sh` zkusit i `.venv/Scripts/python.exe`.

### A6 · Izolace interpretu končí u spouštěče

**Závažnost:** střední až vysoká · **Ověření:** pokus

Spouštěč volá `python -I bootstrap.py`, takže příkazový proces je izolovaný. Okna a pomocné procesy se ale spouští jako `python -m watch_me …` bez `-I` a s pracovním adresářem volajícího: `host/runner.py:163-174` a `host/editor_launcher.py:142-148` (`cwd=Path.cwd()`), stejně `host/live_transcription.py:63`, `editor/transcription.py:93`, `editor/archiving.py:232`, `platform/windows_input.py:77` a `platform/windows_uia.py:54`.

S `-m` je první položka `sys.path` pracovní adresář, tedy projekt, ve kterém agent zrovna pracuje. Pokus: ve složce se souborem `argparse.py` skončí `python -m watch_me version` chybou z toho souboru, s `-I` projde. V pythonovém repozitáři, který má na nejvyšší úrovni modul se jménem ze standardní knihovny nebo ze závislostí (`logging.py`, `types.py`, `queue.py`, `secrets.py`, balík `mcp` nebo `numpy`), okno nenastartuje a v `ui.log` je nesouvisející traceback. V horším případě se kód projektu vykoná uvnitř nahrávače. Platí i `PYTHONPATH` z prostředí uživatele.

Druhý důsledek: běžící okno i editor drží pracovní adresář agenta otevřený. Na Windows nejde taková složka smazat ani přejmenovat, což se týká hlavně worktree, které hostitelé po práci uklízejí.

**Návrh:** jedna funkce, která skládá příkaz pro každý podřízený Python a vždy přidá `-I`. Pracovní adresář oken nastavit na složku stavu nebo na složku nahrávek.

### A7 · Relace nemá vlastníka

**Závažnost:** střední · **Ověření:** přečteno

Při `ALREADY_RUNNING` skill říká: použij id relace ze zprávy a pokračuj čekáním (`skills/watch-me/SKILL.md:44-45`; MCP v `host/mcp_server.py:209-215` id rovnou vrací). `wait` bez `--session` si vezme „aktivní“ relaci (`host/cli.py:98-100`).

Uživatel s více otevřenými chaty nebo dvěma hostiteli tak snadno dostane dva agenty čekající na tutéž relaci. Po stisku Process dostanou oba stav `processed` a oba provedou pokyny z nahrávky, každý ve svém projektu. Stejně si nový chat přivlastní okno, které zůstalo otevřené po starém.

**Návrh:** při startu zapsat vlastníka (náhodný token vrácený jen tomu, kdo okno spustil, plus hostitel a pracovní adresář). Při `ALREADY_RUNNING` vrátit, kdo relaci vlastní, a nechat agenta zeptat se uživatele. Stav `processed` vydat jen držiteli tokenu.

### A8 · `SKILL.md` má 27 kB a legenda časové osy je v kontextu třikrát

**Závažnost:** střední · **Ověření:** pokus (velikost), přečteno

`skills/watch-me/SKILL.md` má 26 908 bajtů, zhruba 7 tisíc tokenů při každém vyvolání skillu. Většinu tvoří popis řádků časové osy a ovládání kreslení (`:75-111` a `:150-282`). Tutéž legendu vrací každé volání `timeline` v poli `legend` (`host/events.py:799-801`) a MCP ji má v `INSTRUCTIONS` a v popisech nástrojů (`host/mcp_server.py:86-119`, `:741-766`).

Agent ten text potřebuje až ve chvíli, kdy čte časovou osu, a tam ho dostane s ní. Během čekání, které tvoří většinu relace, ho nese v kontextu zbytečně při každém kole.

**Návrh:** `SKILL.md` zkrátit na start, čekání, pořadí čtení a pravidlo „jednat jen po Process“ (do 150 řádků). Legendu ponechat v `legend`, podrobnosti dát do `references/` uvnitř složky skillu.

### A9 · Čekání je dotazování po 45 sekundách po celou dobu nahrávání i střihu

**Závažnost:** střední · **Ověření:** přečteno, režie volání pokusem

Půlhodinová relace znamená asi 40 volání `wait`, každé je jedno kolo modelu s celým kontextem (včetně A8). Samotné volání stojí 250 až 670 ms (změřeno), drahý je počet kol. Hostitel s limitem kroků na jeden tah nebo agent, který po několika `timed_out` usoudí, že má skončit, čekání přeruší a uživatel pak stiskne Process do prázdna. Limit kroků v Cursoru je předpoklad, nezkoušel jsem ho.

**Návrh:** delší čekání tam, kde ho hostitel snese (nástroj Bash v Claude Code dovolí až 10 minut, MCP má strop 240 s v `host/waiting.py`), a při `timed_out` vracet jen stav a nápovědu místo celého objektu relace. Chybějícího čekatele řeší i A7: relace, kterou nikdo nevyzvedl, má jít později bezpečně převzít.

### A10 · Živost relace je holé číslo procesu a čtenář zapisuje konečný stav (přetrvává E5)

**Závažnost:** střední · **Ověření:** přečteno

`platform/process.py:11-38` považuje za živý jakýkoli proces s daným PID (odepřený přístup také). `host/runner.py:205-223` při `status` a `wait` zapíše do `state.json` konečný stav `failed` nebo `cancelled`, když PID nenajde. Windows čísla procesů recykluje, takže relace po pádu okna může dlouho vypadat jako běžící a blokovat nový start přes `ALREADY_RUNNING`. Opačně může čtenář uzavřít relaci během předávání mezi oknem a editorem. Editor už používá zámek operačního systému (`host/editor_lock.py`), který tyhle potíže nemá.

**Návrh:** stejný zámek pro relaci nahrávače; `status` nemá stav měnit.

---

## B. Nahrávání

### B1 · Stopa mikrofonu není svázaná s hodinami nahrávky (přetrvává N1)

**Závažnost:** vysoká · **Ověření:** přečteno (důsledek změřila revize z 13. 11.: až 5 s za 26 minut)

`capture/audio_recorder.py:163-171`: blok, který se nevejde do fronty, se zahodí a nic ho nenahradí. Přetečení na straně PortAudio se jen zaloguje na úrovni DEBUG. Stopa je pak kratší než časová osa a všechny pozdější časy přepisu ukazují dřív, než se věc na obrazovce stala. Stopa zvuku počítače to má vyřešené (`capture/computer_audio.py:257-273`: chybějící čas doplní tichem, přebytek zahodí).

Rozchází se tím přesně to, na čem plugin stojí: věta „tohle tlačítko“ ukáže na jiný snímek a jinou polohu kurzoru. Chyba roste s délkou nahrávky a se zátěží procesoru.

**Návrh:** mikrofon vést stejně jako stopu počítače, tedy podle hodin nahrávky, a počet ztracených bloků uložit do manifestu.

### B2 · Výpadek zvukového zařízení se nepozná (přetrvává N2)

**Závažnost:** vysoká · **Ověření:** přečteno

Nic nehlídá, jestli ze vstupu chodí vzorky. Když se během nahrávání odpojí sluchátka s mikrofonem nebo se notebook vyjme z doku, proud přestane dodávat data a zbytek komentáře chybí. Uživatel to zjistí až v editoru. Smyčka zvuku počítače je svázaná s výstupem, který byl výchozí při startu (`capture/computer_audio.py:190-191`).

**Návrh:** hlídač: dvě sekundy bez vzorků znamenají pokus o znovuotevření výchozího zařízení, doplnění ticha a viditelné varování v ovládacím okně.

### B3 · Každý tik ukládá plný snímek každé obrazovky, i když se nic nezměnilo

**Závažnost:** střední až vysoká (disk a výkon všeho, co následuje) · **Ověření:** pokus

`capture/recorder.py:894-921` při každém tiku zakóduje a zapíše obrázek každé obrazovky a k němu sidecar. Sidecar opakuje celý seznam `drawings` včetně cest tahů štětcem, a to pro každou obrazovku a po celou dobu, co je tvar na obrazovce.

Na dvou zdejších nahrávkách (2560×1600 a 1920×1080, 500 ms, JPEG 70) to dělá 2,3 a 2,4 GB za hodinu. Dvouhodinová nahrávka je kolem 5 GB a 57 600 souborů. Počet souborů pak určuje cenu všeho dalšího: výpis složky při každém volání `frames`, čtení časové osy (F1), náhledy v editoru, kódování archivu, mazání, antivirus.

Při komentované práci se obraz většinu času nemění, takže velká část snímků je shodná s předchozím.

**Návrh:** porovnat surový snímek s předchozím (stačí rychlý otisk) a shodný neukládat. Stav kurzoru a kreslení zapisovat jen při změně do jednoho souboru `frames_info/index.jsonl`.

### B4 · Rozložení obrazovek se čte jen při startu (přetrvává N3)

**Závažnost:** střední · **Ověření:** přečteno

`capture/recorder.py:542` načte obrazovky jednou. Připojení projektoru, vyjmutí z doku nebo změna měřítka během nahrávání znamená snímání špatných oblastí nebo trvalé `failed_grabs` a posunuté souřadnice kurzoru i tvarů.

**Návrh:** při změně rozložení (signály Qt `screenAdded`, `screenRemoved`, `geometryChanged`) nahrávání s hláškou zastavit a uložit, nebo změnu zapsat do manifestu a snímat dál podle nového rozložení.

### B5 · Hák myši: priorita se neuplatní a zápis do roury blokuje zpětné volání

**Závažnost:** střední · **Ověření:** priorita pokusem, zápis přečten (přetrvává N6)

1. `platform/windows_input.py:274` spouští pomocný proces s `ABOVE_NORMAL_PRIORITY_CLASS`. Příznak dostane zavaděč uv (viz A2), ne interpret: Windows dědí jen třídy pod normálem. Pokus: přes zavaděč vrátí `GetPriorityClass` uvnitř procesu `0x20` (normální), při přímém spuštění interpretu `0x8000`. Proces, na kterém závisí plynulost ukazatele celého systému, tedy běží s běžnou prioritou.
2. `platform/windows_mouse_hook.py:168-176` a `:221`: zpětné volání háku `WH_MOUSE_LL` samo zapisuje do roury. Anonymní roura má výchozí vyrovnávací paměť 4 kB, tedy asi sto událostí. Když čtecí vlákno v procesu okna nestíhá (čeká na GIL při kódování snímků nebo kreslení), zápis se zablokuje a s ním ukazatel myši v celém systému. Po vypršení limitu Windows hák tiše odebere, proto existuje hlídač s restarty.

Obojí se projeví při vytíženém procesoru, tedy hlavně při přepisu během nahrávání.

**Návrh:** prioritu nastavit uvnitř pomocného procesu (`SetPriorityClass` na sebe). Zpětné volání jen přidá událost do fronty, zapisuje jiné vlákno.

### B6 · Schránka a obsah prvků pod myší se ukládají bez filtru a putují k agentovi

**Závažnost:** střední až vysoká (soukromí) · **Ověření:** přečteno

`ui/clipboard.py:57-70` uloží jakýkoli text zkopírovaný během nahrávání, až 65 535 znaků, do sidecaru. Odtud jde do řádku `CLIPBOARD` časové osy a celý do výsledku `frames --at`. Kód nekontroluje formáty schránky `ExcludeClipboardContentFromMonitorProcessing` a `CanIncludeInClipboardHistory`, kterými správci hesel na Windows říkají „tohle neukládat“. Heslo zkopírované ze správce hesel během nahrávání tak skončí v čitelné podobě na disku a v kontextu modelu.

Totéž platí pro `mouse_actions` (výchozí zapnuto): hodnota pole, odstavec nebo výběr u každého kliknutí, až 4 096 znaků. Vynechává se jen prvek, který UI Automation označí jako heslo (`platform/windows_uia_helper.py:117`, `:145`).

**Návrh:** respektovat vylučovací formáty schránky, přidat vypínač zachytávání schránky do Settings a v ovládacím okně ukázat, že byl text zachycen. V časové ose uvádět u schránky jen délku a začátek, celý text až na vyžádání.

### B7 · Výchozí složka nahrávek je `Videos`, která bývá synchronizovaná přes OneDrive

**Závažnost:** střední · **Ověření:** předpoklad (na stroji se zálohou složky Videa jsem to nezkoušel)

`core/config.py:167-172` bere výchozí složku z `user_videos_dir()` a pracovní složka `.work` leží uvnitř ní. Tam, kde OneDrive zálohuje i Videa (firemní počítače), se během nahrávání zapisují desítky tisíc snímků a rostoucí WAV do synchronizované složky: zátěž disku a procesoru při snímání, zamčené soubory při přejmenování v `finalize()` (`core/session.py:335-339`, deset pokusů po 0,3 s, pak `PROCESSING_FAILED`) a záznamy obrazovky nahrané do cloudu, aniž si to uživatel vybral.

**Návrh:** cestu pod OneDrive rozpoznat (proměnné `OneDrive`, `OneDriveCommercial`) a varovat v `doctor` a v Settings, nebo dát výchozí složku mimo synchronizované místo.

---

## C. Přepis

Soubory `transcribe/**`, `core/**` a související části `host/**` četl pomocný agent; citovaná místa jsem po něm zkontroloval v kódu. Neatomický zápis přepisu je popsaný v D4.

### C1 · `watch-me transcribe`, tedy náprava, kterou plugin agentovi sám doporučuje, začíná od nuly a přepíše ruční úpravy

**Závažnost:** vysoká · **Ověření:** přečteno

Když přepis není úplný, `describe` i `timeline` agentovi řeknou, ať spustí `watch-me transcribe` (`host/runner.py:693-696`, `host/events.py:807-811`, `skills/watch-me/SKILL.md:381-384`). Ten příkaz (`host/cli.py:401-434` → `transcribe/pipeline.py:298-322`):

- ignoruje uložené `transcribed_ms` a přepisuje celý zvuk znovu, i když přepis během nahrávání pokryl většinu záznamu,
- nezapíše nic, dokud neskončí. Dvě hodiny zvuku jsou podle měření v plánu asi 30 minut na 32vláknovém stroji a na běžném notebooku výrazně víc. Časový limit nástroje hostitele tak pokaždé zahodí všechnu práci,
- nahradí celý přepis včetně titulků, které uživatel v editoru opravil,
- běží na všech logických procesorech s běžnou prioritou (C2),
- pokud tutéž nahrávku právě přepisuje editor, oba procesy si přepisují `transcript.json` i `audio/audio16k.wav`.

Varianta, která navazuje a ukládá po segmentech, už existuje pro archivační proces (`host/cli.py:559-580`).

**Návrh:** `transcribe` vést stejnou cestou: navázat od `transcribed_ms`, ukládat po segmentech atomicky, snížit prioritu a odmítnout, když nahrávku drží editor.

### C2 · Přepis po nahrávání bere všechny logické procesory při běžné prioritě a může běžet přes nové nahrávání

**Závažnost:** střední · **Ověření:** přečteno; dopad na čtyřjádrových a hybridních procesorech je předpoklad

Výchozí `whisper_threads` je `min(32, počet logických CPU)` (`core/config.py:191-193`) a použije se v `transcribe/pipeline.py:246`. Prioritu si snižuje jen archivační proces a přepis během nahrávání (`host/cli.py:534`, `transcribe/live_worker.py:103`); `transcribe-stream` z editoru ani `transcribe` ne.

Přepis během nahrávání je ošetřený dobře: čtvrtina až polovina procesorů a snížená priorita. Slabé místo je editor. `active_session` relace ve stavu `editing` záměrně přeskakuje (`host/runner.py:103-104`), takže nové nahrávání může začít, zatímco editor přepisuje to předchozí. Proces s běžnou prioritou na všech jádrech pak soupeří se snímáním a s hákem myši (B5) a v paměti je druhá kopie modelu. Údaj „32 vláken je 1,6× rychlejší než 8“ pochází z jednoho stroje. Výchozí hodnota se navíc při prvním uložení zapíše do `config.json`, takže se nezmění ani po přenesení konfigurace na jiný počítač.

**Návrh:** výchozí počet podle fyzických nebo výkonných jader, `transcribe-stream` pouštět pod normální prioritou a přibrzdit ho, když je některá relace ve stavu `recording`. Výchozí hodnoty do konfigurace neukládat.

### C3 · Přepis po nahrávání načte celý zbytek zvuku do paměti a jde jinou cestou než přepis během nahrávání

**Závažnost:** střední · **Ověření:** přečteno; paměť je spočítaná, ne změřená

`transcribe/whisper_backend.py:81-82` přečte celý WAV a převede ho na `float32`. Dvě hodiny při 16 kHz jsou přechodně asi 1,15 GB a trvale kolem 1,8 až 2 GB na proces (zvuk, spektrogram celého souboru, model). Každé spuštění pracovního procesu, tedy i každé přepnutí mezi nedokončenými nahrávkami v editoru, navíc prožene celý zvuk přes FFmpeg.

Během nahrávání se přitom přepisuje po oknech s bránou ticha a zámkem jazyka, po nahrávání jedním průchodem bez obojího. Tatáž nahrávka je tak segmentovaná a filtrovaná různě podle toho, kde živý přepis skončil.

**Návrh:** hotové nahrávky přepisovat stejným oknovým mechanismem (`LiveCore`, `GrowingMix`). Omezí to paměť, navázání bude přesné na okno a platí jedna sada pravidel.

### C4 · Brána ticha při živém přepisu se řídí jen mixem a přeskočené okno se už nezkontroluje

**Závažnost:** střední · **Ověření:** přečteno; četnost je předpoklad

`transcribe/live.py:384-388`: okno, které podle prahu neobsahuje řeč, se označí za hotové a `transcribed_ms` se posune. Práh je desátý percentil hlasitosti mixu plus 12 dB (`:121-129`). Když z počítače trvale něco hraje (hudba, video, hovor), komentář uživatele tu hranici překročit nemusí. Editor naváže až za tím místem, takže řeč v přepisu označeném jako úplný chybí. Hladina samotného mikrofonu se už sleduje (`_mic_floor`), jen se pro tohle rozhodnutí nepoužije.

**Návrh:** okno brát jako řeč, když práh překročí mix nebo samotný mikrofon, případně přeskočená okna evidovat a nechat je editor znovu projít.

### C5 · Jazyk nejde nastavit; určí se z první řeči a při navázání se přebírá

**Závažnost:** střední · **Ověření:** přečteno

V konfiguraci žádná položka pro jazyk není. Živý přepis se zamkne na jazyk prvního okna s aspoň 20 znaky (`transcribe/live.py:400-407`), navázání ho převezme a průchod po nahrávání rozhoduje jednou ze začátku zvuku. Když je první řeč zvuk počítače v jiném jazyce nebo se krátký český úvod rozpozná jako slovenština, celá nahrávka se přepíše v tom jazyce. Nový přepis rozhodne stejně, takže cesta ven není.

**Návrh:** nastavení `whisper_language` (výchozí automaticky) a přepsání pro jednu nahrávku v editoru.

### C6 · Nativní knihovna omezuje procesory a platformy a její pád se projeví jen kódem ukončení

**Závažnost:** střední · **Ověření:** seznam kol a příznaky procesoru zjištěny, chování na nepodporovaném procesoru je předpoklad

- Kolo `pywhispercpp` pro Windows je sestavené s AVX2, FMA a F16C v jediné knihovně bez výběru za běhu. Procesor bez AVX2 (řada Pentií, Celeronů a Atomů) skončí na neplatné instrukci. `doctor` ani kontrola připravenosti (`host/readiness.py:31-56`) procesor nezkoušejí; živý přepis se dvakrát restartuje a vzdá to jen se záznamem v logu, editor ukáže číslo.
- Kola existují jen pro cp312 a cp313 na Windows x86/x64, Linuxu x86_64 a aarch64 a macOS arm64. Chybí Windows ARM64 a Intel macOS, tam je potřeba sestavení ze zdroje.
- `pywhispercpp` vrátí normálně vypadající objekt i pro model, který se nepodařilo otevřít. Kód kontroluje jen `is_file()` (`transcribe/whisper_backend.py:128-143`), takže špatný nebo zamčený vlastní model spadne nativně.

**Návrh:** do `doctor` a kontroly připravenosti přidat test AVX2 a kontrolu hlavičky modelu. Kódy ukončení pro neplatnou instrukci a porušení přístupu přeložit na srozumitelnou zprávu. `whisper-cli` držet jako plnohodnotnou záložní cestu.

### C7 · Stahování v `setup` nepřežije přerušené spojení a FFmpeg má jediný zdroj

**Závažnost:** střední · **Ověření:** přečteno; limit GitHub API je předpoklad

- Spojení ukončené uprostřed stahování vyvolá `DownloadError("incomplete download …")` (`host/downloads.py:275-276`). Ta dědí z `RuntimeError`, kterou `_retryable` (`:124-127`) nepovažuje za opakovatelnou. `setup` tedy selže při prvním výpadku během 548 MB modelu, přestože navázání přes `Range` umí; pomůže až druhé spuštění. Pro agenta v hostiteli to znamená další kolo oprav.
- FFmpeg pro Windows se hledá přes neautentizované GitHub API (limit 60 dotazů za hodinu na adresu, bez záložní přímé adresy) a bere se nejnovější verze bez horní meze (souvisí s D3). Pro macOS zdroj není.

**Návrh:** neúplné tělo brát jako opakovatelnou chybu, přidat přímou adresu jako zálohu a strop na ověřenou verzi.

---

## D. Editor, export a archivace

Soubory `editor/**` a `export/**` četl pomocný agent; citovaná místa jsem po něm zkontroloval v kódu. Časy změřil na syntetických datech na tomto stroji (32 logických procesorů, NVMe, teplá cache), na běžném notebooku budou horší. Samotné mazání při archivaci je v pořádku: kopie se před smazáním čtou zpět a stav se zapisuje atomicky.

### D1 · Automatická archivace běží jen po dobu otevřeného editoru, začíná každou obrazovku od nuly a zamyká všechny staré nahrávky najednou

**Závažnost:** vysoká · **Ověření:** přečteno, doby kódování změřeny na syntetických snímcích

- Při každém startu editoru se všechny nahrávky starší než `archive_after_days` (výchozí 30) v jedné smyčce označí jako zařazené (`editor/window.py:1231-1241`).
- Zařazenou nahrávku už nejde otevřít, editor místo ní ukáže oznámení (`editor/window.py:1782-1789`).
- Frontu zpracovává po jedné podřízený proces, který žije jen s oknem. Zavření okna, tedy i Process a Auto process pár vteřin po otevření, volá `archiver.shutdown()` a FFmpeg se zruší (`editor/window.py:3494`, `editor/archiving.py:265-278`).
- Pokrok se pamatuje jen po celých obrazovkách. Při pokračování se rozpracovaný výstup smaže (`export/archive.py:471-472`).

Jedna obrazovka dvouhodinové nahrávky v 1440p se tu kódovala asi 11 minut, se čtyřmi vlákny kodéru asi 29 minut (D6). Při obvyklém použití (Stop → editor → Process během minuty) se dlouhá nahrávka nedokóduje nikdy: při každém otevření začne od nuly, zůstane zamčená a blokuje všechno, co je ve frontě za ní. Uživatel přitom při každém otevření editoru platí plným vytížením procesoru.

**Návrh:** archivační proces oddělit od okna (vlastní zámek, doběhne i po zavření editoru) a nahrávku zamknout až ve chvíli, kdy ji proces skutečně začne zpracovávat. Obrazovku kódovat po úsecích, aby šlo navázat.

### D2 · Seznam nahrávek se sestavuje v GUI vlákně procházením všech souborů všech nahrávek (přetrvává E3)

**Závažnost:** vysoká při větším archivu · **Ověření:** přečteno, cena jedné nahrávky změřena

`scan_recordings()` (`editor/recordings_model.py:240-273`) běží v konstruktoru okna a při každém `refresh()`: po archivaci, po dokončení přepisu, po smazání, přesunu i po připojení agenta. Pro každou nahrávku dvakrát přečte celý přepis a zavolá `folder_size()` (`:71-89`, voláno z `:269`), tedy rekurzivní výpis všech snímků a sidecarů. Každý refresh také zahodí cache snímků v seznamu, takže další vykreslení staví `FrameIndex` pro každý viditelný řádek, opět v GUI vlákně.

Archivace maže `frames/` a `audio/`, ale `frames_info/` nechává: 14 400 souborů na hodinu záznamu se dvěma obrazovkami, napořád. Cena skenu tedy roste s celou historií, ne s posledními 30 dny. Změřeno pro jednu dvouhodinovou nahrávku (57 600 souborů, teplá cache): `folder_size` 80 až 110 ms, `FrameIndex` 140 až 195 ms. Sto hodin historie je asi 1,4 milionu sidecarů a kolem 2,4 s na každý refresh tady, na notebooku se studenou cache několikanásobně víc.

Editor musí potvrdit připravenost do 30 s (`host/startup.py:19`). U velké knihovny se z pomalého startu může stát `START_FAILED` pro čekajícího agenta. To je předpoklad, 30 s jsem nedosáhl.

**Návrh:** skenovat v pracovním vlákně a měnit jednotlivé řádky. Velikost a první řádek přepisu uložit k nahrávce. Sidecary při uložení nebo archivaci sloučit do jednoho souboru (stejné opatření jako u B3, E1 a F1).

### D3 · Export stojí na volbě `-filter_complex_script`, kterou FFmpeg ruší, a verze FFmpeg není pod kontrolou

**Závažnost:** vysoká (kompatibilita) · **Ověření:** přečteno; odstranění z vývojové větve FFmpeg ověřil pomocný agent proti zdrojovému kódu, sám jsem to nekontroloval

Graf filtrů delší než 12 000 znaků se předává souborem přes `-filter_complex_script` (`export/ffmpeg_export.py:67`, `:144-145`, `:560-562`). S kresleným kurzorem (výchozí) stojí každá poloha kurzoru asi 38 znaků, takže na tuhle cestu se dostane každý render i archiv s více než zhruba 300 polohami, tedy asi 2,5 minuty pohybu myši.

FFmpeg 7.1 u té volby vypisuje, že je zastaralá a má se použít `-/filter_complex`. Větve 8.0 a 8.1 ji ještě mají, vývojová větev už ne. `find_ffmpeg` přitom dává přednost tomu, co je v `PATH` (na tomto stroji `…\WinGet\Links\ffmpeg.EXE`, tedy verze, kterou mění `winget upgrade`), a `setup` stahuje „nejnovější stabilní“ sestavení. Po příští hlavní verzi selže každý netriviální Render a každá archivace na neznámé volbě. Nic se nesmaže, ale archivy skončí ve stavu `failed` a po třech pokusech se přestanou zkoušet.

**Návrh:** podle zjištěné verze použít `-/filter_complex <soubor>` (FFmpeg 7.0 a novější) a starou volbu nechat jako zálohu. Stahované sestavení připnout na ověřenou verzi a u FFmpeg z `PATH` kontrolovat rozsah verzí.

### D4 · `transcript.json` se přepisuje celý, neatomicky a v GUI vlákně při každém segmentu

**Závažnost:** střední až vysoká (ztráta ručních úprav) · **Ověření:** přečteno; roztržený zápis jsem nevyvolal

`write_transcript` (`core/transcript.py:159-163`) jsou dvě prostá `write_text`, bez dočasného souboru a přejmenování. Všechny ostatní sdílené soubory JSON v projektu jdou přes `atomic_write_text`. Volá se pro každý segment z Whisperu (`editor/transcription.py:233-239` → `editor/recording.py:343-350`), takže dvouhodinová nahrávka znamená asi 3 000 úplných přepsání obou souborů v GUI vlákně. Stejná funkce ukládá ruční úpravy titulků.

Nečitelný soubor čte `transcript_status` jako „přepis od 0 ms“ (`core/transcript.py:196-198`). Pád, ukončení procesu nebo výpadek během těch tisíců zápisů tedy znamená, že editor nahrávku potichu přepíše znovu a ruční opravy textu, časování i spodní stopa jsou pryč.

**Návrh:** oba soubory zapisovat přes `atomic_write_text` a segmenty ukládat po dávkách (při události průběhu nebo jednou za pár sekund).

### D5 · Mazání nahrávek a výpočet průběhu zvuku zamrazí okno nebo zamknou soubory

**Závažnost:** střední · **Ověření:** přečteno, mazání změřeno

- **Mazání v GUI vlákně.** `delete_recording` volá `shutil.rmtree` přímo ve slotu (`editor/window.py:1476-1481`, `host/retention.py:61-72`). Smazání jedné syntetické dvouhodinové nahrávky trvalo 6,1 s; smazání složky nebo výběru to násobí a okno po tu dobu stojí.
- **Průběh zvuku bez cache a bez zrušení.** `editor/timeline/waveform.py:80-132` čte při každém načtení nahrávky celé soubory WAV (dvě hodiny jsou asi 0,7 GB na stopu). Nahrazená úloha doběhne do konce a drží soubor otevřený, výsledek se nikam neukládá. Na Windows pak smazání nebo přesun právě prohlížené dlouhé nahrávky selže s hláškou o otevřeném souboru.

**Návrh:** při mazání složku nejdřív přejmenovat (okamžité) a mazat v pracovním vlákně. Špičky průběhu uložit vedle zvuku, úloze dát příznak zrušení a před mazáním na ni počkat.

### D6 · Render a archivace ženou dvousnímkový obsah linkou na 24 snímků za sekundu v plném rozlišení

**Závažnost:** střední · **Ověření:** změřeno na syntetickém vstupu

Graf je `fps=24, scale, overlay, format=yuv420p` a kóduje se libx264 `medium`, CRF 18 (`export/ffmpeg_export.py:87-91`, `:163-171`). Každý zdrojový snímek se před překrytím kurzoru a převodem barev dvanáctkrát zopakuje, i když se kurzor mění jen se zdrojovým snímkem. 120 s vstupu 2560×1440 při 2 snímcích za sekundu: 10,6 s na všech jádrech, 28,8 s se čtyřmi vlákny. Přesun `fps` za překrytí a převod dal 18,6 s, o 35 % méně.

**Návrh:** překrytí a převod barev dělat v rytmu zdroje, `fps` dát na konec, pro archivy rychlejší předvolbu. S ukládáním jen změněných snímků (B3) klesne i vstup.

### D7 · Dlouhé nahrávky v editoru: celé překreslení osy při každém tiku a dekódování bez zrušení

**Závažnost:** střední · **Ověření:** vykreslení změřeno mimo okno, fronta dekódování přečtena

Každý tik přehrávání (33 ms) i každý pohyb při tažení překreslí celou časovou osu se všemi titulky (`editor/timeline/view.py:337-353`): 7,8 ms pro 15 minut, 17 ms pro hodinu, 28 ms pro dvě hodiny na tomto stroji. Na pomalejším notebooku to přesáhne tik a přehrávání zvuku soupeří o GIL. Náhled při tažení spouští dekódování plného rozlišení pro každý snímek, přes který hlava projde, bez kontroly, jestli je ještě potřeba (`editor/preview.py:480-488`). Snímek pod myší přijde na řadu poslední.

**Návrh:** neměnné vrstvy osy držet v pixmapě. Úlohy dekódování, o které už nikdo nestojí, zahazovat (jak to dělá `ThumbnailCache`).

### D8 · `EditorWindow` je zároveň okno i řídicí logika

**Závažnost:** střední (architektura) · **Ověření:** přečteno

`editor/window.py` má 3 533 řádků a obsahuje pravidla archivační fronty, protokol relace s agentem, stavový automat přepisu, složky, hledání i podmínky renderu. Stav drží ve slovnících podle id relace (`_transcription_failed`, `_transcription_fraction`, `_archive_exempt` a další) a tentýž údaj se čte ze tří míst: ze snímku posledního skenu, ze živých správců a z `archive.json`. Odtud pocházejí chyby typu „přepis doběhl na nahrávce, která není zobrazená, a její řádek se neobnoví“. Aktuální větev se jmenuje `fix/editor-transcription-state`, což je oprava téhož druhu.

**Návrh:** stav přesunout do modelu nahrávky bez závislosti na Qt, se signály změn; okno má být jen jeho zobrazení. Každá další funkce editoru bude jinak dražší než ta předchozí.

---

## E. Ovládací okno a kreslicí vrstva

Soubory `ui/**` četl pomocný agent; citovaná místa jsem po něm zkontroloval v kódu. Časy a velikosti v tabulkách změřil mimo okno (jen `QImage`, bez skutečné vrstvy na obrazovce), takže jsou to dolní odhady.

### E1 · Tah štětcem se ukládá bod po bodu a celý se opakuje v každém sidecaru

**Závažnost:** vysoká · **Ověření:** přečteno, velikosti změřeny mimo okno

`ui/overlay.py:1168-1169` přidá do tahu bod při každé události pohybu myši, bez ředění. `shape_to_json` (`ui/overlay.py:387-393`) zapíše každý bod jako objekt `{screen, x, y}` a vynechá jen dva stejné body po sobě. Nahrávač pak celý seznam vloží do sidecaru každé obrazovky při každém tiku, dokud tvar zůstává na obrazovce (`capture/recorder.py:908`).

| Kresba na obrazovce | Velikost `drawings` v jednom sidecaru |
| --- | --- |
| 150 tahů po 40 bodech (rukopis na plátně Sketch) | 289 KiB |
| 30 tahů po 400 bodech | 533 KiB |
| 100 tahů po 300 bodech | 1,3 MiB |

Při 500 ms a dvou obrazovkách je to 1 až 5 MB JSON za sekundu. Deset minut s popsaným plátnem dá 0,7 až 3 GB sidecarů, tedy víc než samotné snímky (B3). Každé čtení časové osy (F1) se zpomalí stejným poměrem.

**Návrh:** body ředit už při kreslení (minimální vzdálenost nebo Douglas–Peucker). Geometrii zapsat jednou na tvar, do `drawings.jsonl` nebo jen do tiku, kde se změnila, a v sidecarech nechat jen id tvarů.

### E2 · Každý pohyb myši překreslí celé obrazovky a guma obtahuje všechny tvary (přetrvává N5)

**Závažnost:** střední · **Ověření:** přečteno, změřeno mimo okno

`update()` se volá bez obdélníku (`ui/overlay.py:1174`) a `paintEvent` kreslí všechny tvary znovu s vyhlazováním. `erase_hits` při každém pohybu sestaví obrys každého tvaru, bez předběžného testu ohraničujícího obdélníku a bez cache.

| Kresba na ploše 3840×2160 | Celé vykreslení | `erase_hits` na pohyb |
| --- | --- | --- |
| prázdná | 3 ms | – |
| 150 tahů po 40 bodech | 20 ms | 14 ms |
| 30 tahů po 400 bodech | 45 ms | 29 ms |
| 100 tahů po 300 bodech | 99 ms | 72 ms |

Běží to v GUI vlákně téhož procesu, který snímá a kóduje, takže hustá kresba zpomalí kreslení a přidá zahozené tiky.

**Návrh:** hotové tvary držet v pixmapě pro každé okno a kreslit jen rozpracovaný tvar přes `update(oblast)`. Obrysy pro gumu ukládat a nejdřív testovat ohraničující obdélník.

### E3 · Pauza během kreslení zamkne myš na celé ploše

**Závažnost:** střední · **Ověření:** přečteno

Při pauze zůstává kreslicí vrstva nad všemi obrazovkami a každé kliknutí mimo ovládací okno a nástrojovou lištu vyvolá dotaz na pokračování (`ui/overlay.py:1041-1052`). Z kreslení nejde odejít žádnou cestou: tlačítko Draw je při pauze vypnuté (`ui/control_window.py:502`), Esc, křížek i zkratka končí v `_user_close`, které při zmrazení jen znovu zavolá `_blocked()` (`ui/overlay.py:2615-2620`).

Uživatel, který nahrávání pozastaví právě proto, aby udělal něco mimo záznam, nemůže kliknout nikam, dokud nepokračuje. Zbývá klávesnice a Alt+Tab.

**Návrh:** zmrazená vrstva má kliknutí propouštět (`WS_EX_TRANSPARENT` po dobu pauzy), nebo ji při pauze schovat a tvary zachovat.

### E4 · Stop při chybě a Discard blokují GUI vlákno

**Závažnost:** střední · **Ověření:** přečteno (doby jsou odhad)

Uložení po Stop běží v pracovním vlákně. Dvě jiné cesty ale ne:

- `_discard` (`ui/control_window.py:746-752`) volá `controller.discard()`, které zastaví nahrávač a pak maže snímky přes `shutil.rmtree`. U dvouhodinové nahrávky je to přes 57 tisíc souborů.
- `_halt_recording` (`ui/control_window.py:793-811`: málo místa, chyba zápisu nebo snímání) volá `controller.stop_recording()`. To čeká na snímací vlákno (až 60 s), na start myši (až 30 s), na zapisovač zvuku (až 30 s) a na frontu kódování (`capture/recorder.py:578-609`).

Okno, které je vždy navrchu, po tu dobu neodpovídá. `closeEvent` navíc při ukládání a zastavování každé zavření odmítne, takže když se zastavení zasekne, zbývá jen ukončit proces.

**Návrh:** zastavení i zahození pustit do pracovního vlákna jako `process()`, ukázat průběh a po časovém limitu nabídnout vynucené ukončení.

### E5 · Globální zkratky jsou napevno a berou běžné kombinace

**Závažnost:** střední · **Ověření:** přečteno

`ui/control_window.py:87-93` registruje přes `RegisterHotKey` po celou dobu nahrávání Ctrl+Space, Ctrl+Alt+S, Ctrl+Alt+K, Ctrl+Alt+P, Ctrl+Alt+M a Ctrl+Alt+L. Aplikace, kterou uživatel předvádí, tyto klávesy nedostane: Ctrl+Space je doplňování kódu ve většině editorů a přepínání vstupu pro čínštinu a japonštinu, Ctrl+Alt+S, L a M jsou v produktech JetBrains Settings, Reformat Code a Extract Method. Nástroj určený k předvádění práce ve vývojovém prostředí tak bere zkratky právě tomuto prostředí. V konfiguraci žádné nastavení zkratek není. Neúspěšná registrace se pozná jen z logu a zkratka pak platí jen při fokusu okna.

**Návrh:** zkratky do konfigurace a do Settings, výchozí Draw bez Ctrl+Space, neúspěšnou registraci ukázat v okně.

### E6 · Lupa ukazuje obraz zmrazený při vstupu do kreslení

**Závažnost:** střední · **Ověření:** přečteno

Obrazovka se sejme jednou při zobrazení vrstvy (`ui/overlay.py:1845-1853`). Při 100 % je vidět živá plocha, první otočení kolečkem ji ale nahradí snímkem starým třeba několik minut, a ten se nahraje. Agent pak ve snímku vidí stav, který už neplatil, když o něm uživatel mluvil. Snímek navíc obsahuje ovládací okno, takže pod skutečným oknem je jeho zvětšená stará kopie.

**Návrh:** sejmout obrazovku znovu ve chvíli, kdy lupa opouští 100 %, a vlastní okna z toho snímku vyloučit. `exclude_window_from_capture` v `platform/windows.py:139` už existuje a nikdo ji nevolá.

### E7 · Ovládací okno je uprostřed hlavní obrazovky v každém snímku

**Závažnost:** nízká až střední · **Ověření:** přečteno

`ui/control_window.py:348-355` umístí okno do středu hlavní obrazovky a poloha se nepamatuje. Okna Watch Me se snímají záměrně, takže dokud uživatel okno neodsune, zakrývá ve snímcích střed obsahu, který má agent vidět.

**Návrh:** otevírat v rohu a pamatovat si poslední polohu.

---

## F. Výstup pro agenta

### F1 · `timeline` čte jeden soubor na každý tik a MCP to opakuje pro každou stránku (přetrvává E2)

**Závažnost:** střední · **Ověření:** pokus

`host/events.py:203-225` otevře a rozebere sidecar každého tiku v rozsahu. Na zdejší 74sekundové nahrávce (148 tiků) trvalo první volání 1,56 s a opakované 0,43 s. Rozdíl, asi 7 ms na soubor, je studené čtení malých souborů. Dvouhodinová nahrávka má 14 400 tiků, tedy řádově 100 s při prvním volání. Revize z 13. 11. naměřila 30 s na 26 minutách.

MCP stránkuje po řádcích, ale `tool_timeline` (`host/mcp_server.py:358-367`) pro každou stránku sestaví celou osu znovu. Hodinová nahrávka o pěti stránkách přečte všechny sidecary pětkrát a první stránka může překročit limit nástroje hostitele (Codex má v návodu 60 s).

**Návrh:** při uložení nahrávky zapsat `frames_info/index.jsonl` jen se změnami stavu (souvisí s B3). Hotový text osy ukládat do `agent/timeline.txt` s klíčem (rozsah, čas změny přepisu a ořezu) a stránky brát z něj.

---

## G. Budoucí kompatibilita

### G1 · Závislosti drží jen `uv.lock`

**Závažnost:** střední · **Ověření:** přečteno, zdroj varování pokusem

- `pyproject.toml:7` omezuje Python na `>=3.12,<3.14`. Python 3.14 je venku od října 2025. Dnes to nevadí, protože uv stáhne vlastní 3.12 nebo 3.13, ale je to další důvod, proč start závisí na uv a na síti (A3). `uv.lock` má pro `pywhispercpp` kola jen pro cp312 a cp313.
- `mcp>=2.0` je nová hlavní řada s jiným rozhraním (`mcp.server.mcpserver.MCPServer`), bez horní meze.
- `numpy>=2.0` je bez horní meze a `pyproject.toml:46` v testech potlačuje varování „Setting the shape on a NumPy array has been deprecated“. Pochází ze `sounddevice.py:2795`, tedy z cesty, kterou jde každý blok mikrofonu. Až to NumPy odstraní, přestane fungovat nahrávání zvuku. Chrání před tím jen `uv sync --locked`.
- `soundcard` (zvuk počítače) je málo udržovaná knihovna.

**Návrh:** horní meze u `numpy` a `mcp`, v CI pravidelná úloha s `uv lock --upgrade` a testy, aby se rozbití zjistilo dřív než u uživatele. Varování v testech nepotlačovat, ale sledovat.

### G2 · Linux a macOS: co dnes chybí nebo se bude chovat jinak (přetrvává P1)

**Závažnost:** střední dnes, vysoká při portaci · **Ověření:** přečteno; chování na těch systémech je předpoklad

Jádro (snímání, mikrofon, přepis, editor, export, zámky, protokol pracovních procesů) je přenositelné a CI na všech třech systémech běží. Chybí nebo se bude lišit:

- **Akce myši, prvky pod myší a gesta touchpadu** existují jen pro Windows (`platform/base.py:160-170` vrací jinde `None`). Časová osa pak nemá řádky `CLICK`, `DRAG` ani `over …` u řeči, tedy to, podle čeho agent pozná, co „tohle“ znamená.
- **Zvuk počítače** jen přes WASAPI (`capture/computer_audio.py:82-85`).
- **Globální zkratky** jen přes `RegisterHotKey` (`ui/hotkeys.py:58`). Jinde platí zkratky jen při fokusu okna, takže Stop z klávesnice během práce v jiné aplikaci nefunguje.
- **Kreslicí vrstva.** Zachytávání kliknutí stojí na výplni s průhledností 1, tedy na tom, jak Windows testuje zásah u vrstvených oken; na macOS skoro průhledné pixely kliknutí nejspíš propustí. Na X11 dělá `X11BypassWindowManagerHint` z vrstvy okno mimo správce oken: nedostane fokus klávesnice (Esc a jednoklávesové zkratky nebudou fungovat) a leží nad ovládacím oknem i lištou.
- **Wayland** není podporovaný vůbec (snímání, lupa, schránka bez fokusu) a je výchozí na většině dnešních distribucí.
- **macOS:** FFmpeg se nestahuje, oprávnění k nahrávání obrazovky a mikrofonu se váže na hostitelskou aplikaci, která příkaz spustila, a Retina není vyzkoušená.
- **Spouštěče a instalace:** `launch.sh` má stejnou potíž s `uv` jako A5 a odkaz na návod (A4) se přes symbolický odkaz rozbije stejně.

**Návrh:** před portací rozhodnout, které funkce jsou na Linuxu a macOS povinné. U chybějících to říct v manifestu a ve výsledku `timeline` (pole `mouse.recorded` už existuje) a opravit větu v `SKILL.md`, že systémy „are supported“. Pro Linux počítat s portálem (PipeWire ScreenCast, GlobalShortcuts), ne s X11.

---

## Co je v pořádku

- Rozhraní pro agenta: jeden JSON na příkaz, chyby s kódem, výstup omezený délkou, MCP stránkuje a synchronní nástroje běží mimo smyčku událostí (ověřeno v `mcp` 2.3.0).
- Kořenový `plugin.json` ve formátu Agent Plugins Codex i Cursor podle své dokumentace čtou; `.claude-plugin/marketplace.json` čte Codex jako starší umístění.
- Start přes spouštěč stojí asi 250 ms; potvrzení připravenosti okna přes `startup.json` je navržené dobře.
- Stav, model a FFmpeg jsou ve složce `~/.watch-me` a přežijí aktualizaci pluginu.
- Sdílené soubory JSON kromě přepisu se zapisují atomicky s opakováním; čtení opakuje také.
- Zámek editoru je zámek operačního systému, odolný proti pádu.
- Hák myši a UI Automation běží v pomocných procesech, dotazy na prvky mají vlastní frontu a neblokují čtení událostí.
- Archivace před smazáním ověří video i zvuk a stav zapisuje atomicky; cestu ke ztrátě dat jsem v ní nenašel.
- Model se načítá jednou na proces; cesta k modelu s diakritikou nebo jinými písmy funguje (vyzkoušel pomocný agent přes junction).
- Živý přepis: samostatný proces se sníženou prioritou, restart nejvýš dvakrát, zapisuje jen rodič a atomicky.
- Stahování: soubor `.part`, navázání mezi spuštěními, kontrola SHA-256.
- Kódování textu je všude výslovně UTF-8.

## Doporučené pořadí

1. **Zprovoznit a ověřit tři hostitele na Windows (A1 až A6).** Nejdřív levné opravy s jistým přínosem: `-I` a pracovní adresář u podřízených procesů (A6), `uv` jen když je potřeba a `.sh` na Windows (A5), návod do složky skillu (A4). Pak samokontrola přežití okna a pokus o vystoupení z jobu (A2). Potom skutečná zkouška s výchozími oprávněními (A1). Prostředí ve složce stavu (A3) je větší změna, ale bez ní bude každá aktualizace pluginu znamenat opravu řízenou agentem.
2. **Zabránit tiché ztrátě a rozejití dat:** atomický zápis přepisu (D4), `transcribe` s navázáním (C1), mikrofon podle hodin nahrávky (B1), hlídač zvukového zařízení (B2).
3. **Jeden indexový soubor místo sidecaru na snímek** a ukládání jen změněných snímků (B3, E1, F1, D2). Je to jedna změna formátu, která řeší čtyři nálezy najednou: velikost na disku, rychlost časové osy, start editoru a cenu archivace.
4. **Archivace oddělená od okna editoru** (D1) a volba filtru podle verze FFmpeg (D3).
5. **Soukromí:** filtr schránky a vypínač (B6). Malá změna, velký dopad na důvěru.
6. **Použitelnost při nahrávání:** nastavitelné zkratky (E5), pauza při kreslení (E3), lupa (E6), priorita přepisu a háku (C2, B5).
7. Zbytek podle potřeby; G2 až před portací.

## Zdroje k hostitelům

- Codex, balení pluginu: <https://developers.openai.com/codex/plugins/build>
- Cursor, tvorba pluginů: <https://cursor.com/docs/plugins/building>
- Hlášení o ukončení odpojeného potomka po skončení volání nástroje v Codex CLI na Windows: `openai/codex#14875` (z vyhledávání, samotné hlášení jsem nečetl celé)
