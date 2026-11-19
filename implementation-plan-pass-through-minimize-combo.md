# Plán: kratší blikání, Pass through, minimalizace Drawing tools, combo box šablon

Zdroj: nahrávka `20261119-182738` (0:00–9:02), master instrukce „Create Plan“.
Plán zapracovává odpovědi na otevřené otázky z první verze.

## Cíl

Čtyři úpravy pluginu Watch Me:

1. **Recorder, blikání rámečku:** červené i zelené blikání bude mít čtyři kroky po 125 ms, tedy 0,5 s.
2. **Recorder, nové tlačítko Pass through (P):** ve výchozím stavu je odmáčknuté. Kreslicí vrstva pak ukazuje obrázek obrazovek pořízený v okamžiku zapnutí kreslení. Zamáčknuté tlačítko ukazuje živou obrazovku. Při zoomu se vrstva zmrazí na aktuální živý obraz.
3. **Recorder, minimalizace okna Drawing tools:** tlačítko v hlavičce (ikony ve stylu YouTube fullscreen / exit fullscreen) sbalí okno na malou hlavičku. Stav platí po celou dobu běhu jednoho Watch Me Recorderu.
4. **Video editor, dialog Instructions:** tři tlačítka šablon nahradí combo box `Custom` / `Draft Intent` / `Create Plan` / `Implement`, výchozí hodnota je `Custom`.

## Co nahrávka ukázala (kontext)

- 2:00–3:20: tray menu se po Ctrl+Space zavře. Vrstva je dnes při 100 % průhledná, takže zavřené menu je hned vidět. Snímek z okamžiku zapnutí (`OverlayWindow._snapshot`, `overlay.py:962`) je vidět jen při zoomu. Podle tebe snímek menu zachytí, protože se menu zavírá až po pořízení snímku. Ruční ověření tedy není potřeba.
- 5:24: první řádek Drawing tools je `Sketch (S) | Snap to grid (G) | Clear (Ctrl+Alt+C)`. Pass through patří mezi Snap to grid a Clear.
- 7:41–8:45: v dialogu Instructions se řada `Draft Intent | Create Plan | Implement` nahradí jedním širokým combo boxem.

## Kroky

### 1. Blikání 4 × 125 ms (`src/watch_me/ui/overlay.py`)

- `FLASH_STEP_MS = 250` změnit na `125`.
- `OPEN_FLASH` zůstane: červená, tmavě červená, červená, tmavě červená (500 ms).
- `CLOSE_FLASH` rozšířit na zelená, tmavě zelená, zelená, tmavě zelená (500 ms).
- Opravit docstring modulu (ř. 70–76) a zmínky ve `watch-me-spec.md` a `skills/watch-me-recorder/SKILL.md`.
- **Ověření:** unit testy v `tests/unit/test_overlay.py`: obě sekvence mají 4 kroky a 500 ms, leave() skryje vrstvu po 500 ms.

### 2. Pass through (P) (`src/watch_me/ui/overlay.py`)

**Stav a obrázky.** `DrawingOverlay` dostane `_pass_through = False` (`pass_through`, `set_pass_through`, `toggle_pass_through`). `show()` ho při novém zapnutí kreslení vrátí na `False`, stejně jako Sketch a Snap to grid. Každé `OverlayWindow` bude držet dva obrázky:

- `_start_snapshot`: dnešní `_snapshot`, pořízený v `show()` při zapnutí kreslení. Do `hide()` se nemění.
- `_live_snapshot`: živý obraz zmrazený ve chvíli, kdy uživatel s Pass through zapnutým začal zoomovat. Při návratu na 100 % se zahodí.

**Co vrstva ukazuje:**

| Pass through | Zoom 100 % | Zoom > 100 % |
|---|---|---|
| vypnutý (výchozí) | `_start_snapshot` 1:1 | `_start_snapshot` zvětšený |
| zapnutý | živá obrazovka (průhledná vrstva jako dnes) | `_live_snapshot` zvětšený |

**Přechody:**

- **Zoom z 100 % výš s Pass through zapnutým:** nejdřív se pořídí `_live_snapshot` daného monitoru, pak se zvětší. Každé nové přiblížení ze 100 % pořídí čerstvý obraz.
- **Odzoomování na 100 % (kolečko nebo `0`):** `_live_snapshot` se zahodí a je znovu vidět živá obrazovka.
- **Vypnutí Pass through** (při jakémkoli zoomu): vrstva ukáže `_start_snapshot` se zachovaným výřezem a `_live_snapshot` se zahodí.
- **Zapnutí Pass through při zoomu > 100 %:** pořídí se `_live_snapshot` a pokračuje se se stejným výřezem. Plyne to z tvého pravidla, že při zoomu se zmrazí aktuální živý obraz.
- Obrazce jsou v souřadnicích plátna, takže při výměně obrázku zůstanou na místě.

**Pořízení živého obrazu bez vrstvy.** Zatímco je vrstva vidět, `grabWindow(0)` by vyfotilo i ji. Nakreslené obrazce by pak byly v obrázku podruhé a po zvětšení by vedle sebe byly dvakrát. Postup:

- **Windows:** těsně kolem grabu přepnout overlay okna na `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)` a hned zpět na `WDA_NONE`. Na obrazovce nic neblikne. S `mss` už je to ověřené (`implementation-plan-draw-flash-capture.md`); s `QScreen.grabWindow` to ověřit. Kdyby nefungovalo, grabovat přes `mss`. Grab a recorder tick se musí vyloučit zámkem, jinak by snímek nahrávky pořízený přesně v ten moment neobsahoval obrazce.
- **Linux/macOS:** na pár milisekund skrýt obsah vrstvy (`setWindowOpacity(0)`), vyfotit a vrátit. Je to záložní řešení, protože editor i kreslení se ověřují hlavně na Windows.
- Toolbar a okno recorderu na obrázku zůstanou, stejně jako dnes na `_start_snapshot`.

**Tlačítko a zkratka:**

- V `OverlayToolbar` přibude checkable `QPushButton("Pass through (P)")` se signálem `pass_through_requested` a metodou `set_pass_through(bool)`. Tlačítko patří do `_action_buttons`, takže ho v pauze zašedí `set_frozen`.
- Tooltip (vysvětlení): *„Pass through (P): see the live screens through the drawing layer (videos keep playing); zooming in freezes the live picture. Off: the layer shows the screens as they were when drawing started.“*
- První řádek bude mít čtyři tlačítka, ale nástrojů je šest ve stejných sloupcích. Proto 12 sloupců: akční tlačítka po třech, nástroje po dvou. Ověřit šířku okna při 100 % i 150 % DPI.
- Zkratka `PASS_THROUGH_SHORTCUT = "P"` patří do bindings (ř. 2607–2617) s `_unless_frozen`. Holé `P` se zatím nepoužívá; `Ctrl+Alt+P` je Pause.
- **Odchod:** během zeleného blikání zůstane vidět to, co bylo vidět předtím. Obrázky se zahazují až v `hide()`.

**Záznam do timeline.** Doporučuju zapisovat přepnutí tlačítka:

```text
212000 PASS THROUGH on: the drawing layer shows the live screens (zooming in freezes them)
231000 PASS THROUGH off: the drawing layer shows the screens as at 182000 (drawing started)
```

- Recorder zapíše do sidecaru stav `pass_through` u každého ticku (`capture/recorder.py`, jako u `background`/sketch). `host/events.py` z něj udělá řádky `PASS THROUGH on/off` a doplní legendu. Výstup `frames` dostane pole `picture`: `"live"`, `"start"` (obraz ze začátku kreslení) nebo `"zoom"` (živý obraz zmrazený při zoomu, s časem pořízení).
- Staré nahrávky pole nemají a čtou se jako `"live"` při 100 % a `"start"` při zoomu. Odpovídá to dnešnímu chování, takže se jejich timeline nezmění.
- Popis přibude do `skills/watch-me-recorder/SKILL.md` (ovládání kreslení i legenda timeline).

**Ověření:**

- **Unit testy:**
  - výchozí stav je off a `show()` ho resetuje;
  - `P` přepíná a v pauze je zablokované;
  - texty prvního řádku jsou `["Sketch (S)", "Snap to grid (G)", "Pass through (P)", "Clear (Ctrl+Alt+C)"]` (`test_overlay.py:616`, `test_overlay_redo_grid.py:156`);
  - paintEvent vybírá obrázek přesně podle tabulky;
  - všechny přechody fungují: zoom in/out s Pass through, vypnutí při zoomu, zapnutí při zoomu;
  - `_grab_screen` je při testech mockovaný;
  - v events testech řádky `PASS THROUGH` a stará sidecar bez pole.
- **Ručně:** spustit video na YouTube a Ctrl+Space, video stojí. `P` ho rozběhne, zoom ho zastaví na aktuálním obraze bez zdvojených obrazců, odzoomování ho znovu rozběhne. Opětovné `P` ukáže první snímek. Na závěr zkontrolovat `timeline` krátké nahrávky.

### 3. Minimalizace okna Drawing tools (`src/watch_me/ui/overlay.py`, `src/watch_me/ui/icons.py`)

- **Ikony:** v `icons.py` přibudou `collapse_icon()` a `expand_icon()`. Nakreslím je vlastním QPainterem jako ostatní ikony, takže nepotřebují žádnou cizí licenci.
  - **Rozbalit** (jako YouTube „full screen“): čtyři rohové závorky v rozích čtverce, otevřené ven.
  - **Sbalit** (jako YouTube „exit full screen“): čtyři rohové závorky otočené dovnitř ke středu.
  - Kreslí se černě podle stylu toolbaru, aby fungovaly ve světlém i tmavém režimu.
- **Hlavička:** mezi titulek a křížek přibude `QToolButton` `overlayToolbarCollapse` ve stylu křížku (průhledný, s hover efektem). Tooltip je „Minimize the drawing tools“, ve sbaleném stavu „Restore the drawing tools“.
- **Sbalený stav:** `OverlayToolbar.set_collapsed(bool)` skryje layout pod hlavičkou, zmenší titulek a okraje a přepne ikonu. Díky `SetFixedSize` se okno zmenší na obsah. Levý horní roh zůstane na místě.
- **Chování ve sbaleném stavu:** všechny zkratky dál fungují a okno jde přetahovat za hlavičku. Titulek „Drawing tools (paused)“ se zobrazuje i sbalený.
- **Trvání stavu:** stav si drží `OverlayToolbar`, které vzniká jednou na `DrawingOverlay` (`_ensure_toolbar`) a přežije `hide()`/`show()`. Esc a nové Draw ho tedy zachovají. `DrawingOverlay` se vytváří v `ui/app.py:92`, jednou na běh recorderu, takže nový start Watch Me Recorderu začne rozbaleně. `show()` stav neresetuje, na rozdíl od Sketch, Snap to grid a Pass through. Ověřit, že každé nahrávání opravdu běží v novém procesu nebo nové instanci; jinak stav resetovat při startu nahrávání.
- **Ověření:**
  - unit testy: sbalení skryje nástroje a paletu, okno je výrazně menší, rozbalení vrátí původní velikost, zkratky fungují sbalené, stav přežije `leave()`+`show()`, nová instance začíná rozbalená;
  - ručně na dvou monitorech s různým DPI.

### 4. Combo box šablon v Instructions (`src/watch_me/editor/instructions_dialog.py`)

- Místo řady `template_buttons` bude jeden `QComboBox` (`template_combo`) přes celou šířku dialogu s položkami `Custom`, `Draft Intent`, `Create Plan`, `Implement`. Každá šablona má tooltip z `Template.tooltip`.
- **Výběr při otevření:** pokud text odpovídá šabloně (porovnání po `strip()`), vybere se ta šablona, jinak `Custom`. Prázdné pole je `Custom`.
- **Přepnutí na šablonu:** pokud pole obsahuje jiný text, vyskočí potvrzovací modál (jako dnes). Po potvrzení se text nahradí šablonou.
- **Přepnutí na Custom:** pokud pole není prázdné, zeptá se „Clear the instructions?“. Po potvrzení se pole úplně vyprázdní.
- **Odmítnutí v modálu:** combo se vrátí na předchozí položku (pod `blockSignals`) a text zůstane.
- **Ruční úprava textu šablony:** combo se samo přepne na `Custom` bez dotazu a bez mazání (v `textChanged`, pod `blockSignals`).
- `Custom` se do `TEMPLATES` nepřidává a `instructions.txt` se nemění.
- Upravit docstring modulu, `skills/watch-me-video-editor/SKILL.md` (sekce 2), `watch-me-spec.md:173` a README, pokud zmiňuje tlačítka šablon.
- **Ověření:**
  - `tests/unit/test_editor_requests.py` (5 míst s `template_buttons`) přepsat na combo:
    - výchozí Custom;
    - šablona do prázdného pole bez dotazu;
    - šablona přes jiný text s potvrzením i s odmítnutím (combo se vrátí);
    - Custom vyprázdní pole po potvrzení, po odmítnutí zůstane šablona;
    - otevření s textem šablony vybere šablonu;
    - ruční úprava přepne na Custom.
  - Ručně ve světlém i tmavém tématu (`editor/theme.py`).

### 5. Závěrečné ověření

- `uv run pytest tests/unit` a lint/typy podle `pyproject.toml`.
- Ruční průchod s videem: Pass through vypnutý i zapnutý, zoom v obou stavech, sbalení a rozbalení přes Esc/Draw a nový start recorderu, `timeline` nahrávky s řádky `PASS THROUGH`. Pak v editoru combo v Instructions.
- Verzi a distribuci nijak neměnit, dokud o to nepožádáš.

## Rizika a předpoklady

- **Grab živého obrazu při zoomu** je jediná technicky citlivá část. Když overlay nejde vyloučit ze snímku, obrazce budou v obrázku dvakrát. Proto `WDA_EXCLUDEFROMCAPTURE` na Windows a zámek proti souběhu s recorder tickem. Na Linuxu X11 jen záložní řešení s krátkým skrytím.
- **Zmrazený obraz jde do nahrávky:** s vypnutým Pass through snímky ukazují statický obraz. Je to záměr a agent to pozná z řádků `PASS THROUGH`.
- **Výkon:** při 100 % s vypnutým Pass through se při každém překreslení kreslí celá obrazovka (`drawPixmap`). Ověřit, že štětec na 4K neseká.
- **Blikání 8 Hz** po dobu 0,5 s může být nepříjemné pro fotosenzitivní uživatele. Je ale krátké.

## Otevřené otázky

Žádné, všechny jsou zodpovězené. Zbývá jen to, co ověří implementace: `WDA_EXCLUDEFROMCAPTURE` s `grabWindow` a jeden recorder proces na jedno spuštění.
