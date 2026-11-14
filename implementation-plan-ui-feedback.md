# Implementační plán: úpravy ovládacího okna, Settings, editoru a kreslení

Zdroj: nahrávka `20261114-082807` (16:15, česky), celý rozsah. Pokyny: jen plán, nic neimplementovat.

## Cíl

Zjednodušit a sjednotit ovládací okno Watch Me (pozice, tlačítka, tooltipy, stavový
řádek), přesunout volbu tématu do Settings a sdílet ji s editorem, učinit okna
nerozměnitelnými, opravit chybějící text v titulcích editoru a upravit dvě drobnosti
kreslení (zkratka G, nápověda pravého tlačítka).

## Kroky

### 1. Ovládací okno se otevře uprostřed hlavní obrazovky (0:13–0:31)

- **Co:** `ControlWindow._place_window()` ([control_window.py:311](src/watch_me/ui/control_window.py:311)) dnes dává okno do pravého horního rohu (`right - width - 24`, `top + 24`). Nově střed `primaryScreen().availableGeometry()` (screen1).
- `_fit_width(right)` dnes drží pravý okraj při změně šířky. Nově bude držet **střed** okna (`center_x` místo `right`), aby se vystředěné okno při Record/Pause/Mute neposouvalo do strany. Po kroku 4 (stejně široká tlačítka) se šířka mezi stavy téměř nemění, takže je to hlavně pojistka.
- **Ověření:** pytest-qt: po konstrukci je `geometry().center()` ve středu `availableGeometry()` (±1 px). Po `_on_record()` a `pause_recording()` se střed nezmění.

### 2. Pryč tlačítka tématu a „Hide to Tray“, místo nich minimalizace v titulku (0:42–1:40)

- **Co:** odstranit `theme_button` a `tray_button` z prvního řádku (a jejich `_apply_icons`, `toggle_theme`, `set_theme`, `THEME_SETTING` z okna, kromě aplikace tématu při startu, viz krok 3).
- Do titulku vedle křížku přidat standardní tlačítko **minimalizovat**. Kliknutí na něj skryje okno do tray (dnešní `hide_to_tray()` včetně balónku zůstane).
  - Okno má dnes `Qt.WindowType.Tool`. Windows u tool-window minimalizační tlačítko nezobrazí, proto flag `Tool` nahradit `Qt.WindowType.Window` a přidat `WindowMinimizeButtonHint`. `WindowStaysOnTopHint` zůstane.
  - `changeEvent(QEvent.WindowStateChange)`: když je okno minimalizované, `QTimer.singleShot(0, …)` vrátí stav na `WindowNoState` a zavolá `hide_to_tray()`. Bez systémové tray se okno normálně minimalizuje (žádná hláška).
  - `restore_from_tray()` použije `showNormal()`.
- **Ověření:** pytest-qt: v okně nejsou tlačítka „Theme“ ani „Hide to Tray“. `setWindowState(WindowMinimized)` vede na `in_tray == True` a skryté okno. Kliknutí na ikonu v tray okno vrátí. Ručně na Windows: tlačítko „_“ je vedle křížku, okno zmizí do tray a nahrávání běží dál.

### 3. Téma v Settings, společné pro rekordér i editor, výchozí světlé (1:43–5:46)

- **Konfigurace:** nové pole `theme: "light" | "dark"` v `Config` ([config.py](src/watch_me/core/config.py)), výchozí `"light"`. Patří do `config_from_dict`/`to_json_dict` a do validace (`ConfigError` pro jinou hodnotu) a lze ho nastavit přes `config set theme dark`.
- **Settings dialog** ([settings_dialog.py](src/watch_me/ui/settings_dialog.py)), nové pořadí řádků:
  1. **Theme** – combo `Light` / `Dark` (první řádek, tam kde byla Recording Folder),
  2. Capture Interval … Drawing Grid (beze změny),
  3. **Recording Folder** – poslední řádek před Save/Cancel: pole s cestou, **Browse…**, hned za ním **Open Folder**,
  4. řádek **Recordings** se zruší (jeho Open Folder je teď v řádku Recording Folder).
- **Okamžité použití (rozhodnuto):** změna v comboboxu Theme hned zavolá `apply_theme(...)`, takže se přebarví dialog Settings i ovládací okno. Dialog k tomu dostane callback `on_theme_preview(dark)`, kterým ovládací okno překreslí ikony tlačítek (ty se řídí barvou textu tématu, dnešní `_apply_icons`). **Save** volbu uloží do `config.json`. **Cancel** a zavření křížkem vrátí téma, se kterým se dialog otevřel.
- **Jen před nahráváním (rozhodnuto):** Settings, a tím i téma, jdou otevřít jen před spuštěním nahrávání. Tlačítko Settings je během nahrávání skryté jako dnes a `_open_settings()` během nahrávání nic neudělá. Žádná změna chování, jen se to doplní do testů a dokumentace.
- Ovládací okno při startu čte téma z `config.json` místo z `QSettings("WatchMe","Recorder")`.
- **Editor (rozhodnuto: jedno společné téma, měnitelné v rekordéru i v editoru):** editor při startu aplikuje `config.theme` místo `QSettings("WatchMe","Editor") view/dark` ([window.py:3420](src/watch_me/editor/window.py:3420)). Jeho přepínač (slunce/měsíc nad Edit, Ctrl+T) zůstane. Přepne téma hned a zapíše ho do `config.json`, takže platí i pro rekordér. Zápis přes nové `core/config.py: save_theme(theme, config_file)`: načte aktuální `config.json`, změní jen `theme` a uloží s retry z `core/fileio.py`, takže nepřepíše jiné klíče, které mezitím uložil rekordér.
- Každá aplikace téma čte při svém startu (rekordér i znovu při otevření Settings). Změna v jedné běžící aplikaci se do druhé, právě otevřené, nepromítne živě. Projeví se až při jejím dalším spuštění nebo otevření Settings.
- Staré klíče `view/dark` v obou QSettings se ignorují a odstraní (`settings.remove`).
- **Ověření:** unit: výchozí Config má `theme == "light"`, neplatná hodnota hodí `ConfigError`. pytest-qt: výběr Dark v comboboxu hned ztmaví paletu aplikace, Cancel vrátí světlou a `config.json` zůstane beze změny, Save uloží `"theme": "dark"`. Během nahrávání `_open_settings()` žádný dialog neotevře. První řádek formuláře je Theme, poslední datový řádek Recording Folder s tlačítky `Browse...` a `Open Folder`, žádný řádek „Recordings“. Uložení Dark → `config.json` obsahuje `"theme": "dark"` a paleta aplikace je tmavá. Editor spuštěný s takovým configem je tmavý. Přepínač v editoru zapíše `"theme": "light"` a ostatní klíče `config.json` zůstanou beze změny. Další start rekordéru je světlý.

### 4. Okna nejdou roztahovat (3:47–4:24)

- **Co:** Settings dialog dostane `form.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)`, takže nejde měnit velikost a sám se přizpůsobí, když se objeví nebo zmizí řádek JPEG Quality. Totéž pro ovládací okno (`layout.setSizeConstraint(SetFixedSize)` místo dnešního `setFixedHeight` a ručního `adjustSize`).
- **Ověření:** pytest-qt: `minimumSize() == maximumSize()` u obou oken. Přepnutí PNG↔JPEG změní výšku dialogu.

### 5. Tlačítka ovládacího okna bez zkratek, zarovnaná do mřížky (6:00–7:28)

- **Co:** popisky jen `Stop`, `Pause`/`Resume`, `Keypoint`, `Mute Mic`/`Unmute Mic`, `Mute PC`/`Unmute PC`, `Draw` (zrušit `_with_shortcut` v textech). Odpočet `Keypoint (3)` zůstane, protože to není zkratka.
- Řádky 1 a 2 nahradí jeden `QGridLayout` 3×2: nahoře Stop | Pause | Keypoint, dole Mute Mic | Mute PC | Draw. Všechny sloupce budou stejně široké, a to podle **nejširšího textu ze všech stavů** (Resume, Unmute Mic, Keypoint (3) …), aby se šířka při přepnutí nehýbala. Před nahráváním je v horním řádku Record | Settings ve stejné šířce sloupců.
- **Ověření:** pytest-qt: texty tlačítek neobsahují „Ctrl“. Všech šest tlačítek má stejnou šířku a jejich x-pozice v obou řádcích sedí. Šířka okna se po Pause→Resume a Mute→Unmute nezmění.

### 6. Tooltipy začínají zkratkou, Keypoint zkrácený (7:05–8:20)

- **Co:** každý tooltip začne zkratkou v závorce, např. `(Ctrl+Alt+P) Pause the recording: nothing is recorded …`, `(Ctrl+Alt+S) Stop …`, `(Ctrl+Alt+M) …`, `(Ctrl+Alt+L) …`, `(Ctrl+Space or Ctrl+F1) Draw …`. Zkratka uprostřed textu se vypustí.
- Keypoint: jen `(Ctrl+Alt+K) Insert a new keypoint into the timeline.` Věta „The next one can follow after 3 s“ (a zmínka o zelené čáře) zmizí.
- **Ověření:** pytest-qt: `toolTip().startswith("(Ctrl+")` pro všech šest tlačítek ve všech stavech a tooltip Keypoint neobsahuje „next one“.

### 7. Stavový řádek: `Recording 00:09:52 / 01:50:08` (8:23–10:01)

- **Co:** `_tick()` ([control_window.py:1116](src/watch_me/ui/control_window.py:1116)) bude psát `"{state} {elapsed} / {remaining}"`, kde remaining je zbývající čas do auto stopu. Část `|  auto stop in …` se zruší. Zbytek zůstane: `| 2 screen(s), 1900 frames | text −00:49 | N keypoints`. Při pauze `Paused 00:09:52 / 01:50:08`.
- Auto stop má minimum 1 min (`AUTO_STOP_MIN_MINUTES = 1`), takže je vždy aktivní a lomítko se zobrazí vždy. Kdyby vznikla volba „vypnuto“, lomítko se vynechá.
- **Ověření:** úprava `tests/unit/test_ui.py` (dnes hledá „auto stop in“): text odpovídá `^Recording \d\d:\d\d:\d\d / \d\d:\d\d:\d\d  \|` a neobsahuje „auto stop“.

### 8. Editor: titulky ukážou text, kdykoli se vejde aspoň „X…“ (10:56–13:11)

- **Příčina:** `narration_shows_text()` ([view.py:691](src/watch_me/editor/timeline/view.py:691)) kreslí text jen od zoomu `NARRATION_TEXT_MIN_ZOOM = 40 px/s`. Proto ani široký box při menším zoomu text nezobrazí, i když by se vešel (frame 685 500 ms: box ~700 px bez textu).
- **Co:** zoomovou hranici zrušit. `_paint_box_text` ([view.py:1432](src/watch_me/editor/timeline/view.py:1432)) spočítá minimální šířku jako `fontMetrics().horizontalAdvance(first_char + "…")` a text kreslí, jen když se vejde do `inner.width()`. Výsledek `elidedText` tvořený jen „…“ nebo prázdný se nekreslí. Tím odpadne pevná `NARRATION_TEXT_MIN_W` a měřítko obrazovky (DPI) se vyřeší samo.
- Při přiblížení je vidět víc textu, při oddálení se text skryje, jakmile se nevejde ani jeden znak a tři tečky. Tooltip při najetí zůstává.
- Pro výkon počítat text jen pro boxy v kreslené (clip) oblasti.
- **Ověření:** unit/pytest-qt v `tests/unit/test_editor_search.py` (dnes používá `NARRATION_TEXT_MIN_ZOOM`): box 300 px při zoomu 5 px/s text ukáže. Box užší než „X…“ ho neukáže. Box o šířce přesně „X…“ ukáže „X…“. Ručně: oddálit nahrávku `20261114-080135` a ověřit, že dlouhý box zobrazuje „1, 2, 3, …“.

### 9. Snap to grid: zkratka `G` místo `Ctrl+G` (13:40–14:00)

- **Co:** `GRID_SHORTCUT = "G"` ([overlay.py:187](src/watch_me/ui/overlay.py:187)). V `keyPressEvent` ([overlay.py:1230](src/watch_me/ui/overlay.py:1230), [1249](src/watch_me/ui/overlay.py:1249)) bude G holá klávesa jako `S` (bez Ctrl/Alt/Shift) a zařadí se mezi `plain` klávesy blokované při pauze. Tlačítko ukáže `Snap to grid (G)` a tooltip „(G)“. Text v timeline `Snap to grid switched on (G)` ([events.py:610](src/watch_me/host/events.py:610)) a legenda ([events.py:65](src/watch_me/host/events.py:65)) se upraví také.
- G nekoliduje s nástroji (R/E/L/B/A/U), Sketch (S) ani barvami 1–9. Ctrl+G přestane fungovat.
- **Ověření:** úprava `tests/unit/test_overlay.py:242,616` a `test_overlay_redo_grid.py:145` na „G“. G přepíná `grid_locked`, Ctrl+G nic nedělá, při pauze je G blokované.

### 10. Věta o pravém tlačítku jen u Arrow (14:01–15:29)

- **Co:** v `OverlayToolbar` ([overlay.py:1423](src/watch_me/ui/overlay.py:1423)) přidat dovětek „the right mouse button always draws an arrow (Shift: with a head at both ends)“ jen pro `Tool.ARROW`. U Rectangle, Ellipse, Line, Brush a Eraser zůstane jen `Name (key): tip`.
- **Ověření:** pytest-qt: tooltip Arrow obsahuje „right mouse button“, ostatních pět ne.

### 11. Dokumentace

- Docstringy `control_window.py`, `settings_dialog.py`, `editor/theme.py`, `overlay.py`, `editor/timeline/view.py`.
- `watch-me-spec.md`, `README.md` (téma, Hide to Tray, Ctrl+G) a `skills/watch-me/SKILL.md` (ovládací okno: minimalizace do tray místo tlačítka, `G` místo `Ctrl+G`).
- Na závěr celé `uv run pytest` a ruční průchod na Windows (Record → Pause → Mute → Draw → G → Stop → editor).

## Rizika a předpoklady

- **Flag `Tool` → `Window`:** okno dostane tlačítko na hlavním panelu a může se chovat jinak při fokusu nebo Alt+Tab. Na Linux/macOS se minimalizace chová podle správce oken. Ověřit ručně na všech třech OS (CI pokryje jen testy).
- **„Tenhle formulář“ (3:47):** předpokládám dialog Settings, protože byl tehdy na obrazovce. Nerozměnitelné udělám i ovládací okno.
- **Sdílený `config.json`:** editor a rekordér běží jako dva procesy. Zápis tématu z editoru musí jít přes retry v `core/fileio.py` (sdílení souborů na Windows) a nesmí přepsat jiné klíče, které mezitím uložil rekordér (načíst, upravit `theme`, uložit).
- **Výchozí světlé téma** platí i pro stávající instalace: kdo měl uložené tmavé v QSettings, uvidí po aktualizaci světlé, dokud si ho v Settings nepřepne.
- **Stavový řádek:** „kolik zbývá“ chápu jako zbývající čas do auto stopu (1:50:08 při 2h limitu), ne jako celkový limit.

## Rozhodnuto

- Settings (a tím téma) jdou otevřít jen před nahráváním, ne během něj.
- Téma se použije hned při výběru v comboboxu; Save ho uloží, Cancel vrátí původní.
- Jedno společné téma uživatelského rozhraní (light / dark) pro rekordér i editor, uložené v `config.json`. Měnit ho jde v Settings rekordéru i přepínačem v editoru (slunce/měsíc, Ctrl+T).

## Otevřené otázky

Žádné.
