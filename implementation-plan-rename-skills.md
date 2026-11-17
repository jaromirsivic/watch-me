# Implementační plán: přejmenování na Watch Me Recorder a Watch Me Video Editor

Datum: 14. 11. 2026, upraveno 17. 11. 2026. Verze plánu: 6. Stav: **rozhodnutí schválena, neimplementováno**.

Změny ve verzi 4 (rozhodnutí uživatele ze 17. 11. 2026):

- Přejmenovává se **všechno, co nese jméno jedné ze dvou aplikací**: složky a jména skillů, spouštěče, zobrazovaná jména i názvy v oknech a textech.
- **Žádná zpětná kompatibilita.** Plugin ani skilly zatím nikdo nepoužívá. Úklid starých odkazů v instalátorech (krok R3 ve verzi 3), odstavec „Upgrading“ v README a rizika pro stávající uživatele odpadají.
- Čísla řádků odpovídají větvi `feat/skill-crop-second-look` (commit `3ba619b`).

Změny ve verzi 5: rozhodnuté D1 (spouštěcí věty a spuštění podle záměru) a D3 (okno nastavení); D2 přepsáno na návrh, že spouštěče bez parametrů spustí svou aplikaci a `start-watch-me.*` se zruší.

Změna ve verzi 6: D2 schváleno uživatelem; žádné rozhodnutí už není otevřené.

## 1. Jména

Produkt a plugin se dál jmenují **Watch Me**. Mají dvě aplikace:

| | Dnes | Nově |
|---|---|---|
| Název aplikace pro uživatele | Watch Me | **Watch Me Recorder** |
| | Watch Me Editor | **Watch Me Video Editor** |
| Skill (složka, `name:`) | `watch-me` | `watch-me-recorder` |
| | `watch-me-editor` | `watch-me-video-editor` |
| Spouštěče ve složce skillu | `watch-me.bat\|cmd\|sh` | `watch-me-recorder.bat\|cmd\|sh` |
| | `watch-me-editor.bat\|cmd\|sh` | `watch-me-video-editor.bat\|cmd\|sh` |
| Zobrazované jméno (`agents/openai.yaml`) | „Watch Me“ | „Watch Me Recorder“ |
| | „Watch Me Editor“ | „Watch Me Video Editor“ |
| Volání v Claude Code (plugin) | `watch-me:watch-me` | `watch-me:watch-me-recorder` |
| | `watch-me:watch-me-editor` | `watch-me:watch-me-video-editor` |
| Identifikátor aplikace Windows | `WatchMe.Recorder` | beze změny |
| | `WatchMe.Editor` | `WatchMe.VideoEditor` |

Uživatel řekl „watchme-recorder“ a „watchme-video-editor“ i pro zobrazovaná jména a názvy pro uživatele. Plán to vykládá takto: identifikátory jsou `watch-me-recorder` a `watch-me-video-editor`, text pro lidi je „Watch Me Recorder“ a „Watch Me Video Editor“.

Při abecedním řazení je `watch-me-recorder` před `watch-me-video-editor`. Neověřeno, jestli nabídka hostitelů po `/watch` řadí abecedně (R6).

### Pravidlo pro texty

1. **„Watch Me Editor“ → „Watch Me Video Editor“** všude: 39 výskytů ve 20 souborech (mimo historické dokumenty).
2. **„Watch Me“ jako jméno nahrávacího okna nebo aplikace → „Watch Me Recorder“**: titulek okna, jméno aplikace, ikona v oznamovací oblasti, hlášky, které mluví o okně nahrávání.
3. **„Watch Me“ jako jméno produktu nebo pluginu zůstává**: „the Watch Me plugin“, „Watch Me root not found“, „the Watch Me state folder“, „a Watch Me window“ (kterékoli z oken), „Watch Me records the user's narration…“, „clicks into Watch Me itself“.

### Beze změny (záměrně)

| Co | Proč |
|---|---|
| Jméno pluginu `watch-me` v `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `plugin.json`, `pyproject.toml`; marketplace `watch-me-local` | Je to jméno produktu, ne jedné aplikace. |
| CLI `watch-me` a jeho příkazy (`run`, `edit`, `wait --editor`), balíček `watch_me` a moduly (`watch_me.editor`, `watch_me.ui`), MCP server `watch-me` a nástroje `watch_me_*` (`watch_me_edit`, `watch_me_wait_editor`) | Identifikátory v kódu, ne názvy pro uživatele. Přejmenování modulů a příkazů by byla jiná, mnohem větší změna. |
| Stav `editing`, pole `editor_session`, soubory `editor-*.json`, `editor.log`, `start-editor.lock` | Totéž. |
| Stavová složka `~/.watch-me`, proměnné `WATCH_ME_ROOT`, `WATCH_ME_HOME` | Patří produktu. |
| Tlačítko **Video Editor** v okně po Stop | Už se tak jmenuje. |
| Obecné „the editor“ v textech skillů („the editor's **Process** button“) | Není to vlastní jméno. |
| `references/agent-startup.md` v obou skillech | Jména aplikací ani skillů neobsahuje; musí zůstat v obou složkách bajt po bajtu stejný. Před změnou ověřit grepem. |
| Historické dokumenty `implementation-plan*.md`, `watch-me-review*.md`, `docs/h5-startup-and-wait.md`, `watch-me-spec-v2.md` | Popisují stav v době vzniku. |

Spouštěče hledají kořen repozitáře „tři úrovně nad skriptem“ (`skills/<jméno>/scripts/`). Hloubka se nemění, logika `WM_ROOT` v `.cmd` a `.sh` se neupravuje.

## 2. Rozhodnutí

### D1 – kdy se skill spustí (rozhodnuto 17. 11. 2026)

- Krátké věty zůstávají: „Watch Me“ a „Start Watch Me“ spouštějí Recorder, „Edit Watch Me“ spouští Video Editor. K nim přibudou plná jména aplikací.
- Recorder se spustí i tehdy, když uživatel **dostatečně jasně** vyjádří, že chce nahrávat nebo zaznamenávat obrazovku.
- Video Editor se spustí i tehdy, když uživatel **dostatečně jasně** vyjádří, že chce upravovat nahraný záznam obrazovky.

O spuštění rozhoduje hostitel podle `description` v `SKILL.md`, takže se toto pravidlo zapisuje tam. Navržené texty (limit Agent Skills je 1024 znaků):

```text
description: Watch Me Recorder: record the user's narrated screen session (microphone, every screen, cursor position) with a small always-on-top window, transcribe it offline, then act on what the user said while looking at the matching screenshots. Use when the user says "Watch Me", "Start Watch Me" or "Watch Me Recorder", clearly asks to record or capture their screen, or wants to show and tell what to do on screen. Do not use for transcribing existing media files or for plain screenshots, and do not use for editing a recording (that is the watch-me-video-editor skill).
```

```text
description: Watch Me Video Editor: open a simple cutting room for recordings made with Watch Me Recorder (list of recordings, preview with subtitles, timeline per screen, crop start/end, Render to MP4 + SRT at 24 fps), or export a recording to MP4 without the window. Use when the user says "Edit Watch Me", "Watch Me Video Editor" or "Open Watch Me Video Editor", clearly asks to edit, trim, cut or export a screen recording they made, or wants an MP4 video of what they recorded. Do not use for starting a recording (that is the watch-me-recorder skill) or for editing other video files.
```

Poznámka k editoru: umí otevřít jen nahrávky pořízené Watch Me Recorderem. Výluka „or for editing other video files“ proto zůstává; „a screen recording they made“ míří na nahrávky z Recorderu.

Hlášky typu „Open it later with Edit Watch Me“ zůstávají, protože krátká věta platí dál.

### D2 – k čemu je `start-watch-me.bat` a `.sh` (rozhodnuto 17. 11. 2026)

K čemu dnes slouží: je to startér **pro člověka bez agenta** v kořeni repozitáře (README, „Starting without an agent“). Dvojklik na `start-watch-me.bat` otevře okno nahrávání, `start-watch-me.bat edit` otevře editor. Je to šestiřádkový obal: zavolá spouštěč nahrávání a doplní `run` a `--detach`. Existuje jen proto, že spouštěč ve složce skillu bez parametrů nic nespustí (vypíše nápovědu CLI), takže na něj dvojklik nefunguje. Soubor `start-watch-me.cmd` neexistuje, jen `.bat` a `.sh`.

Rozhodnutí: **`start-watch-me.*` zrušit** a naučit oba spouštěče výchozí chování bez parametrů:

- `watch-me-recorder.bat|cmd|sh` bez parametrů = `run --detach` (otevře Watch Me Recorder);
- `watch-me-video-editor.bat|cmd|sh` bez parametrů = `edit --detach` (otevře Watch Me Video Editor);
- s parametry se oba chovají jako dnes, takže pro agenty se nic nemění.

Přínos: jeden soubor na aplikaci, jméno souboru říká, co spustí, a editor jde poprvé otevřít dvojklikem (dnes je potřeba napsat `edit` do terminálu). Nevýhoda: spouštěče leží hlouběji (`skills\watch-me-recorder\scripts\`); README na ně odkáže a doporučí zástupce na ploše.

Zamítnutá alternativa: startér v kořeni ponechat (jeden `start-watch-me.*`, nebo dva `start-watch-me-recorder.*` a `start-watch-me-video-editor.*`) a spouštěče neměnit.

### D3 – okno nastavení (rozhodnuto 17. 11. 2026)

Titulek zůstává „Watch Me Settings“. Nastavení platí pro obě aplikace.

## 3. Kroky

### R0 – úklid na vlastním počítači před změnou

Kompatibilita se neřeší v kódu, takže stará registrace se odstraní ručně, dokud staré složky ještě existují:

- `& .\scripts\install-hosts.ps1 -Claude -Codex -Cursor -Remove` (odstraní junction `watch-me` a `watch-me-editor`).
- Plugin `watch-me@watch-me-local` v Claude Code po změně aktualizovat nebo přeinstalovat (kopie v mezipaměti nese stará jména).
- Ruční konfigurace MCP (pokud existuje) má cestu `skills\watch-me\scripts\watch-me.bat`: po změně přepsat.

### R1 – přesun složek, spouštěče a samotné skilly

Přesuny (zachovají historii souborů):

```bash
git mv skills/watch-me skills/watch-me-recorder
git mv skills/watch-me-editor skills/watch-me-video-editor
git mv skills/watch-me-recorder/scripts/watch-me.bat skills/watch-me-recorder/scripts/watch-me-recorder.bat
git mv skills/watch-me-recorder/scripts/watch-me.cmd skills/watch-me-recorder/scripts/watch-me-recorder.cmd
git mv skills/watch-me-recorder/scripts/watch-me.sh skills/watch-me-recorder/scripts/watch-me-recorder.sh
git mv skills/watch-me-video-editor/scripts/watch-me-editor.bat skills/watch-me-video-editor/scripts/watch-me-video-editor.bat
git mv skills/watch-me-video-editor/scripts/watch-me-editor.cmd skills/watch-me-video-editor/scripts/watch-me-video-editor.cmd
git mv skills/watch-me-video-editor/scripts/watch-me-editor.sh skills/watch-me-video-editor/scripts/watch-me-video-editor.sh
```

Po přesunu ověřit, že `.sh` mají dál spustitelný bit a že nezůstala prázdná stará složka.

Spouštěče:

- `watch-me-recorder.bat` ř. 2: `call "%~dp0watch-me-recorder.cmd" %*`; `watch-me-video-editor.bat` ř. 2: `call "%~dp0watch-me-video-editor.cmd" %*`.
- Komentář v hlavičce `.cmd` (ř. 3) a `.sh` (ř. 2): „Watch Me Recorder launcher“ a „Watch Me Video Editor launcher“. Hláška `ROOT_NOT_FOUND` („Watch Me root not found…“) zůstává, jde o produkt.
- Výchozí chování bez parametrů (D2). V `.cmd` nahradit poslední volání (dnes ř. 25, `call "%WM_ROOT%\scripts\launch.bat" %*`) větvením bez návěští:

  ```bat
  if "%~1"=="" (
    call "%WM_ROOT%\scripts\launch.bat" run --detach
  ) else (
    call "%WM_ROOT%\scripts\launch.bat" %*
  )
  exit /b %ERRORLEVEL%
  ```

  U editoru `edit --detach`. `exit /b %ERRORLEVEL%` musí zůstat **za** blokem; uvnitř závorek by se hodnota dosadila předčasně. V `.sh` před voláním `launch.sh`: `[ "$#" -eq 0 ] && set -- run --detach` (u editoru `edit --detach`). Soubory `.cmd` jsou záměrně bez návěští a s konci řádků LF; to zachovat.

`skills/watch-me-recorder/SKILL.md`:

- ř. 2: `name: watch-me-recorder`;
- ř. 3 (`description`): text z D1;
- ř. 6: nadpis `# Watch Me Recorder`;
- ř. 17–25: `scripts/watch-me-recorder.bat|sh`; doplnit větu, že bez parametrů spouštěč otevře okno (`run --detach`), agent ale parametry píše vždy;
- ostatní výskyty „Watch Me“ (5 v souboru) projít podle pravidla z části 1; odkazy na „the editor“ zůstávají.

`skills/watch-me-video-editor/SKILL.md`:

- ř. 2: `name: watch-me-video-editor`;
- ř. 3 (`description`): text z D1;
- ř. 6: nadpis `# Watch Me Video Editor`;
- ř. 17–25: `scripts/watch-me-video-editor.bat|sh`;
- ř. 70: `section 4 of the watch-me-recorder skill`.

`agents/openai.yaml`:

- recorder: `display_name: "Watch Me Recorder"`, `default_prompt: "Use $watch-me-recorder to start Watch Me Recorder, ..."`;
- video editor: `display_name: "Watch Me Video Editor"`, `short_description` beze změny smyslu, `default_prompt: "Use $watch-me-video-editor to open the Watch Me Video Editor ..."`.

### R2 – cesty ve skriptech

- `git rm start-watch-me.bat start-watch-me.sh` (D2; nahrazuje je výchozí chování spouštěčů z R1).
- `scripts/install-hosts.ps1`:
  - ř. 4: jména skillů v komentáři;
  - ř. 28: `$skillNames = @('watch-me-recorder', 'watch-me-video-editor')`;
  - ř. 163: cesta MCP `skills/watch-me-recorder/scripts/watch-me-recorder.bat`;
  - ř. 188: závěrečná rada „Start Watch Me (or Edit Watch Me)“ beze změny (D1).
- `scripts/install-hosts.sh`:
  - ř. 2: komentář se jmény skillů;
  - ř. 15: `SKILL_NAMES="watch-me-recorder watch-me-video-editor"`;
  - ř. 151, 160, 168: cesty MCP `skills/watch-me-recorder/scripts/watch-me-recorder.sh`;
  - ř. 172: závěrečná rada beze změny.
- Klíč MCP serveru `watch-me` (`mcpServers.watch-me`, `[mcp_servers.watch-me]`) se **nemění**.
- Instalátory se jinak nemění: žádný úklid starých jmen.

### R3 – názvy v aplikacích a v kódu

Video Editor (pravidlo 1, všechny výskyty „Watch Me Editor“):

| Soubor | Místa |
|---|---|
| `src/watch_me/editor/window.py` | ř. 264 `WINDOW_TITLE`, ř. 3137, 3157, 3187 (zprávy o stavu pro čekajícího agenta) |
| `src/watch_me/editor/app.py` | ř. 28 `WINDOW_TITLE`, ř. 99 (`ALREADY_RUNNING`), ř. 105 `setApplicationName` |
| `src/watch_me/editor/app.py` ř. 106 a 108 | `install_app_icon(app, "WatchMe.VideoEditor")`, `QSettings("WatchMe", "VideoEditor")`. Uložená poloha a rozložení okna editoru se tím jednou vrátí na výchozí. |
| `src/watch_me/editor/__init__.py` | ř. 1 (docstring) |
| `src/watch_me/host/controller.py` | ř. 201, 226, 248 |
| `src/watch_me/host/cli.py` | ř. 523, 857, 1130 |
| `src/watch_me/host/mcp_server.py` | ř. 92, 648, 890 |
| `src/watch_me/host/transcription_lock.py`, `editor_lock.py`, `editor_launcher.py` | po jednom |
| `src/watch_me/ui/control_window.py` | ř. 115, 168, 808 |
| `src/watch_me/ui/settings_dialog.py` | ř. 6, 92, 97, 259 |
| `src/watch_me/ui/stop_dialog.py` | ř. 18, 40 |

Recorder (pravidlo 2):

| Soubor | Místo | Nově |
|---|---|---|
| `src/watch_me/ui/control_window.py` | ř. 202 `setWindowTitle("Watch Me")` | „Watch Me Recorder“ |
| | ř. 945 tooltip ikony v oznamovací oblasti | „Watch Me Recorder - click to show the window“ |
| | ř. 112 text o ikoně v oznamovací oblasti | „the Watch Me Recorder icon“ |
| | ř. 954 a 1200 titulek bubliny | „Watch Me Recorder“ |
| | ř. 881 „the next start of Watch Me“ | „…of Watch Me Recorder“ |
| `src/watch_me/ui/app.py` | ř. 66 `setApplicationName`, ř. 77 titulek chybového okna | „Watch Me Recorder“ |
| `src/watch_me/ui/settings_dialog.py` | ř. 90 „the Watch Me window“ | „the Watch Me Recorder window“ |
| | ř. 97 „the recorder and the Watch Me Editor“ | „Watch Me Recorder and Watch Me Video Editor“ |
| | ř. 122 titulek „Watch Me Settings“ | beze změny (D3) |
| `src/watch_me/host/mcp_server.py` | ř. 692 „Open the Watch Me control window“ | „Open the Watch Me Recorder window“ |
| `src/watch_me/host/cli.py` | ř. 993 nápověda `run` | „open the Watch Me Recorder window“ |

Zůstává podle pravidla 3: `ui/overlay.py` (titulky kreslicí vrstvy, „every Watch Me window“), `ui/hotkeys.py`, `host/runner.py` ř. 176 a `host/retention.py` ř. 41 („a Watch Me window“), `core/config.py` ř. 161, `scripts/bootstrap.py` ř. 72, `host/cli.py` ř. 980, texty o myši („clicks into Watch Me“).

Každý zbylý výskyt „Watch Me“ projít jednou a rozhodnout podle pravidla (celkem 175 výskytů v 61 souborech mimo historické dokumenty, z toho 39 je „Watch Me Editor“); nerozhodné případy nechat jako jméno produktu.

### R4 – testy

Jména skillů a cesty:

- `tests/unit/test_host_packaging.py` ř. 22, `tests/unit/test_install_hosts.py` ř. 19, `tests/unit/test_launchers.py` ř. 21: `SKILLS = ("watch-me-recorder", "watch-me-video-editor")`.
- `tests/unit/test_launchers.py`: jméno spouštěče se skládá jako `f"{skill}{EXT}"` (ř. 50, 130, 178, 187). Protože se spouštěče nově jmenují stejně jako skill, **další úprava není potřeba**.
- `tests/unit/test_host_packaging.py` ř. 190 a 196: cesty `"watch-me-recorder"` a `"watch-me-video-editor"`.
- `tests/unit/test_install_hosts.py` ř. 147, 152, 178, 183, 189: nová jména odkazů a cílů.
- `tests/unit/test_starters.py` zrušit (testuje `start-watch-me.*`, D2). Náhrada v `tests/unit/test_launchers.py`: pro každý skill ověřit, že spouštěč bez parametrů předá `run --detach` (recorder) nebo `edit --detach` (video editor), s parametry je předá beze změny, a že v obou případech vrátí návratový kód a výstup volaného příkazu právě jednou (to dnes hlídá `test_starter_returns_launcher_result_once` pro kódy 0, 4, 22 a 23).
- `tests/unit/test_mcp_transport.py` ř. 80: `skills/watch-me-recorder/scripts/watch-me-recorder.bat`.
- `tests/unit/test_bootstrap.py` ř. 72 a 118: `root / "skills" / "watch-me-recorder" / "references" / "agent-startup.md"`.
- `test_host_packaging.py` ř. 95 a `test_mcp_server.py` ř. 548 (jméno pluginu a MCP serveru) **beze změny**.

Názvy v aplikacích:

- `tests/unit/test_editor.py` ř. 460: `"Watch Me Video Editor"`.
- `tests/integration/test_editor_flow.py` ř. 105: `_find_window("Watch Me Video Editor", ...)`.
- Další testy, které porovnávají přejmenované hlášky, ukáže běh sady; opravit na nový text, neměnit hlášky zpět.

Nový test v `tests/unit/test_host_packaging.py`:

- `test_skill_folders_are_exactly_the_registered_ones`: `{p.name for p in (REPO / "skills").iterdir() if p.is_dir()} == set(SKILLS)`. Zabrání tomu, aby po přesunu na Windows zůstala prázdná stará složka (zamčený soubor), kterou by hostitelé načetli jako další skill.

### R5 – dokumentace

Všude platí pravidlo z části 1; níže místa s cestami a identifikátory.

- `README.md`: ř. 73 („the **Watch Me Editor** opens“), ř. 86–95 (oddíl „Starting without an agent“: místo `start-watch-me.*` dvojklik na `skills\watch-me-recorder\scripts\watch-me-recorder.bat` a `skills\watch-me-video-editor\scripts\watch-me-video-editor.bat`, na Linuxu a macOS odpovídající `.sh`; doporučit zástupce na ploše; odkaz na `skills/watch-me-recorder/references/agent-startup.md`), ř. 97 (odkaz `[skills/watch-me-recorder/SKILL.md](skills/watch-me-recorder/SKILL.md)`), jména aplikací v úvodu.
- `docs/installation.md`:
  - ř. 12, 319 a 402: odkazy `../skills/watch-me-recorder/references/agent-startup.md`;
  - ř. 129–130: „`watch-me-recorder` (recording) and `watch-me-video-editor` (the editor and MP4 export)“;
  - ř. 228–236 (ruční odkazy): seznamy a příklady s novými jmény;
  - ř. 243: `$watch-me-recorder`; ř. 245: `/watch-me-recorder`;
  - ř. 298, 311, 317 a 330: cesty `skills\watch-me-recorder\scripts\watch-me-recorder.bat|sh`;
  - ř. 404 (`ROOT_NOT_FOUND`): `scripts/watch-me-recorder.cmd` / `.sh`;
  - ř. 263 a 269 (`/plugin install watch-me@watch-me-local`) beze změny, jde o plugin.
- `watch-me-spec.md`: ř. 7 (jména obou skillů), ř. 220 (`skills/watch-me-recorder/SKILL.md`), jména aplikací v textu.
- `tests/manual/hosts.md`: ř. 124, 125, 126, 153 a 155 (jména odkazů, skillů a spouštěče; zkratku `...-edit` nahradit plným jménem). Ř. 137 a 145 (instalace pluginu `watch-me`) beze změny.
- `tests/manual/acceptance.md`: ř. 25 (cesta `~/.claude/skills/watch-me`) přepsat až po ručním ověření v R6, protože jde o záznam toho, co bylo skutečně vyzkoušeno; jména aplikací v popisech zkoušek upravit hned.
- Popisy pluginu v `plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` a `pyproject.toml` jména aplikací neobsahují; beze změny.

### R6 – ověření

1. Kontrola zbytků. Mimo historické dokumenty nesmí vrátit nic:

   ```bash
   git grep -n -E "Watch Me Editor|watch-me-editor|WatchMe\.Editor|skills[/\\\\]watch-me[/\\\\\"' ]|name: watch-me$|\\\$watch-me([^-]|$)|scripts[/\\\\]watch-me\.(bat|cmd|sh)|start-watch-me" -- . ':!implementation-plan*.md' ':!watch-me-review*.md' ':!docs/h5-startup-and-wait.md' ':!watch-me-spec-v2.md'
   ```

2. Testy: `uv run pytest tests/unit` (Windows), v CI i Linux a macOS. Zvláště `test_install_hosts`, `test_launchers`, `test_starters`, `test_host_packaging`, `test_mcp_transport`, `test_bootstrap`, `test_editor`. Lint: `ruff check` a `ruff format --check`.
3. Ručně na Windows:
   - `& .\scripts\install-hosts.ps1 -Claude` → výpis `created ...\watch-me-recorder` a `created ...\watch-me-video-editor`;
   - nová session: „Start Watch Me“ spustí skill, agent volá `...\skills\watch-me-recorder\scripts\watch-me-recorder.bat run --detach`; okno má titulek „Watch Me Recorder“;
   - „Edit Watch Me“ volá `...\skills\watch-me-video-editor\scripts\watch-me-video-editor.bat edit --detach`; okno má titulek „Watch Me Video Editor“ a vlastní ikonu na hlavním panelu (nový identifikátor `WatchMe.VideoEditor`);
   - dvojklik na `watch-me-recorder.bat` otevře Watch Me Recorder, dvojklik na `watch-me-video-editor.bat` otevře Watch Me Video Editor; totéž `.sh` bez parametrů, pokud je k dispozici Linux nebo macOS.
4. Plugin Claude Code (`watch-me-local`): po zvednutí verze a aktualizaci jsou v seznamu `watch-me:watch-me-recorder` a `watch-me:watch-me-video-editor`, nic jiného.
5. Spuštění podle záměru (D1): v nové session zkusit věty bez jména produktu, například „nahraj mi obrazovku“ a „chci sestříhat záznam obrazovky, který jsem nahrál“, a zapsat, jestli hostitel vybral správný skill. Zkusit i větu, která spustit nemá („udělej snímek obrazovky“).
6. Pořadí v nabídce: v každém dostupném hostiteli napsat `/watch` (Codex `$watch`) a zapsat do `hosts.md`, v jakém pořadí se oba skilly nabídnou.
7. Integrační zkouška `tests/integration/test_editor_flow.py` (hledá okno podle titulku), pokud je k dispozici obrazovka.
8. Codex a Cursor podle `tests/manual/hosts.md` (C1–C3, U1–U3), jen pokud jsou k dispozici; jinak výslovně zapsat jako neověřené.

## 4. Rizika

| Riziko | Dopad | Opatření |
|---|---|---|
| Prázdná stará složka skillu po `git mv` na Windows (zamčený soubor) | Hostitelé najdou tři nebo čtyři skilly | Nový test v R4 |
| `.sh` spouštěč ztratí spustitelný bit nebo konce řádků LF | Skill se na Linuxu a macOS nespustí | `git mv` bit zachová; `test_launchers` hlídá konce řádků; ověřit `git ls-files -s` |
| Přehlédnutý výskyt starého jména v hlášce, kterou čte agent | Agent uživateli řekne staré jméno | Grep v R6 bod 1 (hledá i `start-watch-me`) |
| „Watch Me“ přepsané na „Watch Me Recorder“ tam, kde znamená produkt | Zavádějící text (například u stavové složky) | Pravidlo 3 a průchod výskytů po jednom, žádné hromadné nahrazení |
| Nový `QSettings` klíč editoru | Editor jednou zapomene polohu okna | Přijatelné, kompatibilita se neřeší |
| Staré odkazy a kopie pluginu na vlastním počítači | Hostitel vidí rozbité nebo staré skilly | R0 |
| Spouštěč zavolaný omylem bez parametrů otevře okno, místo aby vypsal nápovědu | Agent, který zapomene parametry, otevře okno nahrávání nebo editor | Skilly parametry vždy uvádějí; nápověda je dál pod `--help` |
| Širší `description` spustí skill i tam, kde uživatel chtěl něco jiného | Okno se otevře nečekaně | Slovo „clearly“ v textu, výluky („plain screenshots“, „other video files“) a zkouška v R6 bod 5 |
| Hostitel neřadí nabídku abecedně | Recorder nemusí být po `/watch` první | Ověření v R6 bod 6 |

## 5. Pořadí a rozsah změny

R0 → R1 → R2 → R3 → R4 → R5, potom R6. R1 a R2 jsou bez R4 nekonzistentní (testy padají), proto jeden commit pro přejmenování skillů a spouštěčů (R1, R2 a příslušná část R4 a R5) a druhý pro názvy v aplikacích (R3 a zbytek R4 a R5).

Odhad: 2 přesuny složek, 6 přesunů souborů a 3 zrušené soubory (`start-watch-me.bat`, `.sh`, `test_starters.py`), asi 25 upravených souborů s kódem nebo skripty, 9 testových souborů a 5 dokumentů. Pracné je R3: 136 výskytů „Watch Me“ bez slova „Editor“ v kódu, testech a dokumentaci k posouzení po jednom.

Po změně zvednout verzi pluginu (čtyři manifesty, `src/watch_me/__init__.py`, `uv lock`).
