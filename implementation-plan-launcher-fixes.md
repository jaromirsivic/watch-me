# Implementační plán: opravy spouštěčů a izolace procesů (A4, A5, A6)

Datum: 14. 11. 2026. Verze plánu: 1. Stav: **L0 až L7 implementováno 15. 11. 2026 (commit `c688bbb`); z L8 zbývá ruční zkouška oken s nahrávkou, průchod v hostiteli a CI**.

Průběh realizace 15. 11. 2026: R1 až R5 potvrzeny uživatelem („Ano, implementuj“). L0: 186 dotčených testů prošlo před změnou. L1 a L5 provedli dva subagenti Opus 5.5 (úsilí high), diff obou jsem přečetl a testy spustil znovu. Subagent L1 se zastavil u třetího testu: regulární výraz ze zadání by zachytil i nová volání `python_command`; pojistný test proto hlídá výběr interpretu (`gui_python(`, `console_python(`, `sys.executable,`) mimo `platform/process.py`. L2, L3, L4 a L6 jsem dělal v hlavní relaci. Odchylky od plánu: L3, L4 a L6 vznikly najednou, protože mění tytéž dva skripty; pole `root` dostala i chyba `ENVIRONMENT_INVALID` z `host/readiness.py` a z `host/cli.py`, nejen z bootstrapu; `launch.sh` v Git Bashi vypisuje cesty ve tvaru `D:/…` (přes `cygpath -m`), který berou Bash i nástroje Windows. L8 body 1 a 3: `ruff check` čistý, celá sada jednotkových testů na Windows prošla (1137 testů); všechny čtyři pokusy z revize prošly proti opraveným skriptům, navíc pomocné procesy háku myši a UI Automation nastartovaly s `-I`. Výsledky jsou v tabulce „Stav po opravách“ v [revizi](watch-me-review-2026-11-14.md).

Zdroj: nálezy A4, A5 a A6 v [revizi z 14. 11. 2026](watch-me-review-2026-11-14.md). Plán navazuje na [H5](implementation-plan-h5-startup-and-wait.md) a jedno jeho rozhodnutí mění (R1 níže). Všechny tři nálezy jsou ověřené pokusem na Windows 11; dva návrhy řešení jsem před sepsáním plánu vyzkoušel na kopiích skriptů mimo repozitář (označeno „vyzkoušeno“).

## 1. Výsledek a hranice

Po změně:

- **A4:** návod na opravu prostředí leží uvnitř složky každého skillu a je dosažitelný i přes junction nebo symbolický odkaz. Chybová odpověď spouštěče navíc říká, kde je kořen kódu a kde je návod, takže agent ví, ve které složce má spustit `uv sync`.
- **A5:** připravené prostředí nastartuje i bez `uv` v `PATH`. `watch-me.sh` funguje i v Git Bashi na Windows.
- **A6:** každý podřízený Python (okna, pracovní procesy, pomocné procesy háků) běží s `-I`, takže soubory v projektu agenta ani `PYTHONPATH` uživatele nemohou zastínit moduly. Okna nedrží pracovní adresář agenta.

Mimo rozsah (záměrně):

| Co | Proč |
| --- | --- |
| Přežití okna po skončení příkazu, job objekty (A2) | Samostatná změna s vlastním ověřením v hostitelích. |
| Přesun `.venv` do složky stavu (A3) | Větší změna instalace; tento plán ji neztěžuje. |
| Zkrácení `SKILL.md` (A8), vlastník relace (A7) | Jiné nálezy. |
| Cesta `ROOT_NOT_FOUND` v `skills/*/scripts/*.cmd` a `*.sh` | Funguje, hlídá ji `tests/unit/test_launchers.py`. Mění se jen jeden řádek navíc (krok L6). |
| Kódování `-X utf8` u oken | Okna ho dnes nemají a plán to nemění, aby se nezměnilo chování exportu. |

Souběh s [plánem přejmenování skillu](implementation-plan-rename-skills.md): tento plán nikde nepíše jméno složky skillu natvrdo mimo testovací konstantu `SKILLS`. Kdo přijde druhý, upraví jen cesty v odkazech dokumentace.

## 2. Zjištění v aktuálním kódu

| Místo | Stav dnes | Důsledek pro realizaci |
| --- | --- | --- |
| `scripts/launch.bat:4-8`, `scripts/launch.sh:3-6` | `uv` se kontroluje jako první, i když se nepoužije | Kontrolu přesunout do větve „interpret chybí“ |
| `scripts/launch.sh:7` | Zná jen `.venv/bin/python` | Přidat `.venv/Scripts/python.exe` pro MSYS a Cygwin |
| `scripts/launch.bat`, `launch.sh`, `scripts/bootstrap.py:27-32` | Chyby `UV_MISSING`, `PYTHON_MISSING`, `ENVIRONMENT_INVALID` neříkají, kde je kořen kódu | Přidat pole `root` a `help` |
| `skills/*/SKILL.md` (4 odkazy), `docs/installation.md:12` a `:303`, `README.md:87`, `watch-me-spec.md:242` | Odkazují na `docs/agent-startup.md` | Návod přesunout do `skills/<skill>/references/` a odkazy opravit |
| `host/runner.py:163-174`, `host/editor_launcher.py:142-148` | `[gui_python(), "-m", "watch_me", …]`, `cwd=Path.cwd()` | Přidat `-I`, pracovní adresář změnit |
| `host/live_transcription.py:62-74`, `editor/transcription.py:92-104`, `editor/archiving.py:231-243` | `[console_python(), "-X", "utf8", "-m", "watch_me", …]` | Přidat `-I` |
| `platform/windows_input.py:77`, `platform/windows_uia.py:54` | Totéž pro `watch_me.platform.windows_mouse_hook` a `windows_uia_helper` | Přidat `-I` |
| `host/cli.py:82-83`, `core/config.py:385-396` | Cesta ke konfiguraci z `--config` nebo z proměnné prostředí může být relativní | Před předáním oknu převést na absolutní |
| `core/config.py:293-300`, `:324` | `recording_folder`, `whisper_model_path`, `ffmpeg_path`, `whisper_cli_path` projdou jen `expanduser()` | Relativní hodnota se dnes vztahuje k pracovnímu adresáři toho, kdo zrovna volá; rozhodnutí R4 |
| `tests/unit/test_bootstrap.py:33-72` | Test skutečného `launch.bat`; kořen má jméno `space ž` | Rozšířit o start bez `uv` a o pole `root` |
| `tests/unit/test_launchers.py:50-62` | Vlastní náhradní `launch.bat` a `launch.sh` | Změn spouštěče se netýká |
| `tests/unit/test_host_packaging.py` | Hlídá manifesty a frontmatter skillů | Přidat kontrolu odkazů v `SKILL.md` |

## 3. Rozhodnutí

**R1 – `uv` se vyžaduje jen tehdy, když chybí interpret prostředí.** H5 (oddíl 3.1) říká, že spouštěč „nejprve ověří dostupnost uv“. Tato změna to ruší: `uv` je potřeba k opravě, ne ke startu. Pořadí chyb při opravě zůstává stejné: bez `.venv` a bez `uv` přijde `UV_MISSING`, bez `.venv` s `uv` přijde `PYTHON_MISSING`. Do `docs/h5-startup-and-wait.md` (ř. 31 a 43) doplnit jednu datovanou větu, že pravidlo bylo zúženo.

**R2 – návod bude v obou skillech jako stejný soubor.** Každý skill se registruje vlastním odkazem, takže společné místo mimo složku skillu není přes odkaz dosažitelné. Dvě shodné kopie `references/agent-startup.md` hlídá test, stejně jako se už hlídá shoda spouštěčů (`test_launchers_are_lf_and_differ_only_in_the_title_comment`). `docs/agent-startup.md` zanikne (`git mv`), ostatní dokumenty odkážou na kopii ve `skills/watch-me/references/`.

**R3 – pracovní adresář oken je domovská složka uživatele.** Existuje vždy, nikdo ji nemaže a nepřejmenovává. Složka stavu se nehodí (ve vývojovém režimu je to checkout a zůstal by zamčený), složka nahrávek také ne (Settings ji umí přestěhovat a staré `.work/<id>` se má dát smazat). S `-I` obsah pracovního adresáře neovlivní importy. Vedlejší přínos: `shutil.which("ffmpeg")` na Windows hledá nejdřív v pracovním adresáři, takže dnes může najít `ffmpeg.exe` z projektu agenta.

**R4 – relativní cesty v konfiguraci se vztáhnou ke složce konfiguračního souboru.** Dnes znamenají pokaždé něco jiného podle toho, odkud se volá, takže `run` a pozdější `wait` z jiné složky se rozejdou už teď. Změna pracovního adresáře okna by to zhoršila. Alternativa: relativní cestu odmítnout s `CONFIG_INVALID`. Doporučuji vztáhnout ke konfiguračnímu souboru; výchozí i běžně nastavené hodnoty jsou absolutní, takže se pro nikoho nic nezmění.

**R5 – chybová odpověď s cestou se na Windows píše přes PowerShell.** `cmd.exe` vypisuje do roury v kódové stránce konzole, takže cesta s diakritikou by přišla agentovi rozbitá. Proto dnešní chyby žádnou cestu neobsahují. PowerShell se spustí jen v chybové větvi (vyzkoušeno: 238 ms, stderr je platný JSON v UTF-8, kořen `…\space ž` se vrátil beze změny). Když PowerShell selže, vypíše se dnešní text bez cest. `watch-me.cmd` už PowerShell jako zálohu používá.

## 4. Kroky realizace

Pořadí je dané závislostmi: L1 a L2 jsou samostatné, L3 až L6 mění tytéž skripty a jdou po sobě. Po každém kroku spustit jeho cílené testy.

### L0 – výchozí stav

Spustit a zapsat výsledek, aby bylo jasné, co bylo zelené před změnou:

```bash
uv run pytest tests/unit/test_bootstrap.py tests/unit/test_launchers.py tests/unit/test_starters.py tests/unit/test_host_packaging.py tests/unit/test_startup.py tests/unit/test_editor_launcher.py tests/unit/test_windows_mouse_source.py tests/unit/test_install_hosts.py -q
```

### L1 – jedna funkce pro příkaz podřízeného Pythonu, vždy s `-I` (A6)

1. Do `src/watch_me/platform/process.py` přidat:

   ```python
   def python_command(*args: str, gui: bool = False, utf8: bool = True) -> list[str]:
       """Command line of a child Python of this installation. Always isolated (-I):
       neither the working directory nor PYTHON* variables reach its sys.path."""
       exe = gui_python() if gui else console_python()
       return [exe, "-I", *(("-X", "utf8") if utf8 else ()), *args]
   ```

   Přidat do `__all__`.
2. Nahradit sedm míst z tabulky v oddílu 2. Okna volat s `gui=True, utf8=False` (beze změny kódování), pracovní a pomocné procesy s výchozími hodnotami. Výsledný příkaz se od dnešního liší jen vloženým `-I` za interpretem.
3. Testy:
   - `tests/unit/test_runner.py` nebo nový `test_process_commands.py`: `python_command(...)[1] == "-I"` pro obě varianty.
   - Skutečný běh: ve složce `tmp_path` se souborem `argparse.py`, který končí chybou, spustit `python_command("-m", "watch_me", "version")` s `cwd=tmp_path` a s `PYTHONPATH=tmp_path`; musí vrátit kód 0 a JSON s verzí.
   - Pojistka proti návratu: test projde `src/watch_me/**/*.py` a selže, když mimo `platform/process.py` najde seznam obsahující `"-m"` následované řetězcem začínajícím `"watch_me`.
   - `tests/unit/test_windows_mouse_source.py:145` kontroluje jen konec příkazu a projde beze změny.

`-I` vypíná `PYTHON*` proměnné, uživatelský `site-packages` a pracovní adresář v `sys.path`. Proměnné `WATCH_ME_HOME`, `WATCH_ME_ROOT` a `WATCH_ME_CONFIG` se dědí dál. Soubory `.pth` ve `.venv` (editovatelná instalace) se načítají i s `-I` (ověřeno: `python -I -m watch_me version` funguje).

### L2 – pracovní adresář oken a absolutní cesty (A6)

1. `platform/process.py`: `spawn_detached` při `cwd=None` použije `Path.home()`, pokud je to složka; jinak nechá výchozí chování.
2. `host/runner.py:174` a `host/editor_launcher.py:148`: odstranit `cwd=Path.cwd()`.
3. `host/cli.py::_config_file` vrátí absolutní cestu (`Path(args.config).expanduser().resolve()`); `core/config.py::config_path` totéž pro hodnotu z proměnné prostředí.
4. Podle R4: `core/config.py::load_config` po načtení vztáhne relativní `recording_folder`, `whisper_model_path`, `whisper_cli_path` a `ffmpeg_path` ke složce konfiguračního souboru. `config_from_dict` bez souboru (požadavek `startup.json` pro okno) dostává hodnoty už absolutní.
5. Testy:
   - `spawn_detached` se skutečným potomkem, který vypíše `os.getcwd()` do logu: výsledek je domovská složka, ne pracovní adresář testu.
   - `test_startup.py` a `test_editor_launcher.py`: náhradní `spawn` už dostává `cwd=None`; doplnit kontrolu, že cesta za `--config` je absolutní i při relativním `--config`.
   - Konfigurace s relativním `recording_folder` načtená ze dvou různých pracovních adresářů dá stejnou absolutní cestu.

### L3 – `uv` jen když je potřeba (A5)

Nová logika `scripts/launch.bat` (stejně `launch.sh`):

```text
interpret = <kořen>\.venv\Scripts\python.exe
když interpret neexistuje:
    když uv není v PATH -> UV_MISSING (20)
    jinak               -> PYTHON_MISSING (22)
spustit interpret -I bootstrap.py %*
když značka bootstrapu nevznikla -> PYTHON_MISSING (22)
```

Úspěšná cesta tím ztratí jedno volání `where uv`. Testy v `tests/unit/test_bootstrap.py::test_real_bat_never_runs_uv_and_preserves_arguments`:

- nový případ: úplné prostředí, `PATH` bez `uv` → kód 7 z náhradního bootstrapu a správné argumenty,
- stávající případy (bez interpretu s `uv` → 22, bez interpretu bez `uv` → 20) zůstávají.

Přidat stejný test pro skutečný `launch.sh` (na POSIX vždy; na Windows, když je k dispozici `sh` z Gitu, jinak přeskočit).

### L4 – `launch.sh` na Windows (A5)

Za zjištěním `WM_PYTHON` doplnit zálohu jen pro MSYS a Cygwin (vyzkoušeno v Git Bashi: `version` vrátí kód 0 s `uv` i bez něj, prázdný kořen bez `uv` vrátí 20; značka bootstrapu z `mktemp` se mezi Bashem a `python.exe` převede správně):

```sh
WM_PYTHON="$WM_ROOT/.venv/bin/python"
if [ ! -x "$WM_PYTHON" ]; then
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*)
      [ -f "$WM_ROOT/.venv/Scripts/python.exe" ] && WM_PYTHON="$WM_ROOT/.venv/Scripts/python.exe" ;;
  esac
fi
```

WSL se záměrně nepřidává: cesty `/mnt/…` se pro `python.exe` nepřevádějí. Test: v L3 přidaný test `launch.sh` na Windows pokryje i tuto větev (prostředí vytvořené přes `uv venv` má `Scripts/python.exe`).

`SKILL.md` dál říká „Windows: `.bat`“. Změna jen zajistí, že agent, který v Bashi sáhne po `.sh`, nedostane falešnou chybu.

### L5 – návod do složky skillu (A4)

1. `git mv docs/agent-startup.md skills/watch-me/references/agent-startup.md` a stejný soubor zkopírovat do `skills/watch-me-editor/references/`.
2. V obou `SKILL.md` změnit čtyři odkazy na `references/agent-startup.md`.
3. Opravit odkazy v `docs/installation.md:12` a `:303`, `README.md:87` a `watch-me-spec.md:242`. Historické dokumenty (plány, revize, `docs/h5-startup-and-wait.md`) se nepřepisují.
4. V návodu upravit oddíl „Prepare the plugin environment“: `<root>` je hodnota pole `root` z chybové odpovědi (L6), ne cesta odvozená od složky skillu. Při instalaci přes odkaz totiž tři úrovně nad skriptem nejsou kořen kódu.
5. Testy v `tests/unit/test_host_packaging.py`:
   - každý relativní odkaz v `skills/*/SKILL.md` neobsahuje `..` a po spojení se složkou skillu vede na existující soubor,
   - obě kopie `references/agent-startup.md` jsou bajtově shodné.

### L6 – chybová odpověď říká, kde je kořen a kde návod (A4)

1. `skills/*/scripts/*.cmd` a `*.sh`: před voláním společného spouštěče nastavit `WM_HELP` na `<složka skillu>/references/agent-startup.md` (na Windows `%~dp0..\references\agent-startup.md`). Je to cesta, kterou hostitel agentovi dal, takže ji agent umí otevřít, a nezávisí na jménu skillu.
2. `scripts/launch.bat`: chyby `UV_MISSING` a `PYTHON_MISSING` vypsat podle R5. Kostra (vyzkoušeno):

   ```bat
   set "WM_CODE=PYTHON_MISSING"
   set "WM_MESSAGE=Prepare the project environment with uv sync --locked."
   powershell -NoProfile -NonInteractive -Command "$e=New-Object Text.UTF8Encoding $false; $w=New-Object IO.StreamWriter([Console]::OpenStandardError(),$e); $w.WriteLine((ConvertTo-Json -Compress ([ordered]@{ok=$false;code=$env:WM_CODE;message=$env:WM_MESSAGE;root=$env:WM_ROOT;help=$env:WM_HELP}))); $w.Flush()" && exit /b 22
   >&2 echo {"ok":false,"code":"PYTHON_MISSING","message":"Prepare the project environment with uv sync --locked."}
   exit /b 22
   ```

   Hodnoty jdou přes proměnné prostředí, ne přes text příkazu, takže uvozovky ani `%` v cestě nic nerozbijí. Vypisovací část dát do jednoho návěští (`:fail`), ne ji opakovat.
3. `scripts/launch.sh`: `printf` s kořenem a návodem; zpětná lomítka a uvozovky v cestě escapovat přes `sed`.
4. `scripts/bootstrap.py::fail`: přidat `root=str(ROOT)` a `help` z `WM_HELP` (když je nastavená).
5. Testy: v `test_bootstrap.py` u případů bez interpretu ověřit `json.loads(stderr)["root"] == str(root)` při kořeni `space ž` (stderr číst jako UTF-8) a totéž pro `ENVIRONMENT_INVALID`. Případ se zakázaným PowerShellem (`PATH` bez něj) musí vrátit dnešní text a stejný kód.

Úspěšná cesta se nemění a PowerShell se při ní nespouští.

### L7 – dokumentace a stav revize

- `docs/installation.md`, oddíl Troubleshooting: `UV_MISSING` znamená „chybí prostředí i uv“; `.sh` funguje i v Git Bashi.
- `docs/h5-startup-and-wait.md`: datovaná věta podle R1.
- `watch-me-review-2026-11-14.md`: nahoru tabulku „Stav po opravách“ s A4, A5 a A6 a s tím, co bylo ověřeno a jak (stejný zvyk jako v revizi z 13. 11.).
- Tento plán: stav a průběh realizace v hlavičce.

### L8 – ověření

1. `uv run ruff check src tests` a celá sada `uv run pytest tests/unit -q` na Windows.
2. CI na všech třech systémech (větev s pull requestem).
3. Čtyři pokusy z revize zopakovat proti opraveným skriptům:
   - junction na `skills\watch-me`, soubor `references\agent-startup.md` přes něj existuje,
   - `sh skills/watch-me/scripts/watch-me.sh version` v Git Bashi → kód 0,
   - `watch-me.bat version` s `PATH` bez uv → kód 0,
   - složka se souborem `argparse.py`: `watch-me.bat run --detach` z ní otevře okno, `wait --timeout 0` vrátí `ready`.
4. Ruční zkouška oken na Windows: spustit `run --detach` z dočasné složky, při otevřeném okně tu složku smazat (musí jít), Record, pár vteřin řeči a kliknutí, Stop, editor, Process. V `recording.log` zkontrolovat, že běžel hák myši, UI Automation i přepis (všechny tři jsou podřízené procesy dotčené L1).
5. Jeden průchod v Claude Code se skillem přes odkaz: „Start Watch Me“ až po `processed`. Codex a Cursor zůstávají v matici `tests/manual/hosts.md` (nález A1).

## 5. Rozdělení práce

Podle pokynu z 14. 11.: jednotlivé úkoly delegovat na subagenta Opus 5.5 s úsilím high tam, kde na ně stačí, a nepředávat nic, kde hrozí chybné provedení.

| Krok | Kdo | Důvod |
| --- | --- | --- |
| L0 | hlavní relace | Jedno spuštění testů. |
| L1 | **subagent Opus 5.5, high** | Mechanická náhrada sedmi míst jednou funkcí, přesně zadaná, hlídaná třemi testy. |
| L2 | hlavní relace | Mění význam relativních cest v konfiguraci (R4) a pracovní adresář oken; chyba se projeví až za běhu, ne v testech. |
| L3, L4, L6 | hlavní relace | Dávkové soubory a shell: uvozování, kódové stránky a návratové kódy `cmd.exe`. Tady se chybuje nejsnáz a testy běží jen na Windows. |
| L5 | **subagent Opus 5.5, high** | Přesun souboru, oprava vyjmenovaných odkazů a dva testy. Bod 4 (úprava textu návodu) až po L6 v hlavní relaci. |
| L7 | hlavní relace | Krátké, závisí na skutečném výsledku. |
| L8 | hlavní relace | Ověření a ruční zkouška; okno musí vidět a ovládat uživatel. |

Výstup subagenta se nepřebírá naslepo: po L1 i L5 přečíst diff a spustit cílené testy v hlavní relaci. L1 a L5 se nedotýkají stejných souborů a mohou běžet souběžně; L3, L4 a L6 mění stejné skripty a jdou po sobě.

## 6. Rizika

| Riziko | Ošetření |
| --- | --- |
| Některý podřízený proces spoléhal na `PYTHON*` proměnnou | V `src` a ve spouštěčích žádná taková není (prohledáno); `scripts/live_benchmark.py` si nastavuje `PYTHONUTF8`, ale pracovní procesy dostávají `-X utf8` výslovně. Ruční zkouška L8 bod 4 projde všechny tři druhy potomků. |
| Uživatel má relativní cestu v konfiguraci | R4 jí dává pevný význam; zmínit v `docs/installation.md`. |
| PowerShell je na stroji zakázaný nebo pomalý | Běží jen v chybové větvi a má zálohu bez cest (R5); test to pokrývá. |
| Převod cest mezi Git Bashem a `python.exe` | Vyzkoušeno pro značku bootstrapu a argumenty; test `launch.sh` na Windows to hlídá dál. Cygwin samotný vyzkoušen není. |
| Dvě kopie návodu se rozejdou | Test shody v L5. |
| Souběh s přejmenováním skillu | Cesty ke skillu jen v konstantě `SKILLS` a v odkazech dokumentace; `WM_HELP` se počítá od skriptu. |
| Hostitel má `SKILL.md` v mezipaměti se starým odkazem | Po změně začít nový chat; u instalace jako plugin zvednout verzi pluginu. |

## 7. Podmínky dokončení

- [x] R1 až R5 potvrzeny nebo upraveny.
- [x] L1: žádný příkaz podřízeného Pythonu mimo `python_command`; test se zastíněným `argparse.py` prochází.
- [x] L2: okno má pracovní adresář v domovské složce; relativní `--config` a relativní cesty v konfiguraci mají testy.
- [x] L3 a L4: start bez `uv` v `PATH` a `.sh` v Git Bashi vracejí kód 0; pořadí `UV_MISSING` a `PYTHON_MISSING` při chybějícím prostředí se nezměnilo.
- [x] L5: žádný odkaz v `SKILL.md` nevede mimo složku skillu; `docs/agent-startup.md` už neexistuje a nic na něj neodkazuje.
- [x] L6: chyby prostředí obsahují `root` a `help` v UTF-8 i pro kořen s diakritikou.
- [ ] L8: lint, celá sada testů na Windows, CI na třech systémech, čtyři pokusy z revize a ruční zkouška oken mají zapsaný výsledek.
- [x] Revize z 14. 11. má tabulku „Stav po opravách“.
