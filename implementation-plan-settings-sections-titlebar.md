# Implementační plán: kontrastní titulek oken, sekce v Settings, Minimize to Tray, tečky screenů, Auto process a tlačítko ⋯

Zdroj: nahrávka `20261114-102126` (8:48, česky), celý rozsah. Pokyny: jen plán, nic
neimplementovat, počkat na schválení. Plán je upravený podle tvých odpovědí na otevřené
otázky (viz „Rozhodnutí“ na konci).

## Cíl

1. Titulek oken Watch Me má být **kontrastní k tématu už od startu**: ve světlém tématu
   tmavý, v tmavém tématu světlý. Dnes se řídí systémem a mění se až po přepnutí témat.
2. Settings dostanou novou volbu **Minimize to Tray** (výchozí *Do not minimize to tray*),
   která platí jen pro okno rekordéru. Řádky se nově rozdělí do čtyř sekcí oddělených
   čarami, bez nadpisů.
3. V editoru se tečky screenů číslují **zprava** (nejpravější tečka = screen1).
4. Checkbox **Auto process** (zatím jen ten) dostane výrazný obrys: černý ve světlém
   tématu, světlý v tmavém.
5. Tlačítko **⋯** vedle New Folder má ve světlém tématu při najetí myší vypadat stejně
   jako tlačítko New Folder.

## Kroky

### 1. Titulek oken kontrastní k tématu (0:09–1:08, upřesněno v odpovědi na otázku 1)

- **Co je vidět:** ve snímku 0:20 má titulek „Watch Me Settings“ barvu formuláře
  (`#f3f3f3`). Po přepnutí Dark → Light (0:29–0:33) je ve snímku 0:40 tmavý (RGB 32,32,32).
  Totéž platí pro ovládací okno „Watch Me“ (0:51–1:08: „tam by to mělo fungovat úplně
  stejně“).
- **Požadavek:** titulek je vždy opačný než téma. **Light** → tmavý titulek, **Dark** →
  světlý titulek. Platí hned od otevření okna a po každém přepnutí tématu (Settings,
  slunce/měsíc v editoru), nezávisle na systémovém režimu Windows.
- **Pravděpodobná příčina dnešního chování (ověřit):** Windows QPA v Qt 6.12 nastavuje
  `DWMWA_USE_IMMERSIVE_DARK_MODE` podle barevného schématu. Při startu okno dostane světlý
  rámeček. Až změna palety (`app.setPalette` v `apply_theme`) přiměje Qt rámečky
  přepočítat, a to podle systémového schématu, které je na tomto PC tmavé.
- **Změna:** nový modul `src/watch_me/platform/windows_titlebar.py`:
  - `set_title_bar_dark(widget, dark: bool)`: přes ctypes zavolá
    `DwmSetWindowAttribute(hwnd, 20, c_int(1 if dark else 0), 4)`. Pro starší sestavení
    Windows 10 použije záložní atribut 19. Chyby jen zaloguje. Mimo Windows nedělá nic.
  - `title_bar_dark_for(theme_dark: bool) -> bool`: vrací `not theme_dark`. Pravidlo
    kontrastu je na jednom místě a jde snadno otestovat.
  - `install_title_bars(app)`: event filter na `QApplication` zachytí `QEvent.Show`
    a `QEvent.WinIdChange` u top-level widgetů (`widget.isWindow()`) a nastaví titulek
    podle aktuálního tématu (`not system_prefers_dark(app)`, tedy světlosti palety
    `Window`). Týká se to všech oken: ovládací okno, Settings, Stop dialog, editor, všechny
    jeho dialogy a `QMessageBox`.
  - `apply_theme()` ([theme.py](src/watch_me/editor/theme.py)) po `setPalette` projde
    `app.topLevelWidgets()` a titulky přepne, aby se změnily hned při přepnutí tématu,
    i v otevřeném Settings během náhledu. Zároveň tím přebije případné přepsání atributu
    od Qt při změně palety.
  - Volání `install_title_bars` přidat při startu rekordéru
    ([ui/app.py:101](src/watch_me/ui/app.py:101)) i editoru, vedle prvního `apply_theme`.
- **Proč ne `setColorScheme`:** `app.styleHints().setColorScheme(...)` (Qt ≥ 6.8) by
  rámečky sladilo s tématem (světlé téma → světlý titulek), tedy opak požadavku. Proto
  explicitní DWM.
- **Ověření:** unit test s nahrazenou funkcí DWM: po `apply_theme(False)` dostane zobrazený
  `QDialog` atribut 20 s hodnotou 1, po `apply_theme(True)` hodnotu 0. Test
  `title_bar_dark_for`. Ručně na Windows se systémem ve světlém i tmavém režimu: ve Light
  mají Settings i ovládací okno černý titulek hned po otevření, po přepnutí na Dark světlý
  a po návratu na Light zase černý. Kontrolní nahrávka: pixel titulku Settings ≈ (32,32,32)
  ve Light, světlý ve Dark.

### 2. Settings: nová volba Minimize to Tray (1:20–2:39)

- **Konfigurace** ([config.py](src/watch_me/core/config.py)): `minimize_to_tray: bool = False`
  (klíč `minimize_to_tray`), doplnit do `config_from_dict`, `to_json_dict` a validace.
  Nastavení přes `config set minimize_to_tray true`.
- **Settings:** řádek **Minimize to Tray** hned pod Theme. QComboBox s hodnotami
  *Do not minimize to tray* (`False`, výchozí) a *Minimize to tray* (`True`), s tooltipem.
- **Rozsah (rozhodnuto):** volba platí **jen pro okno rekordéru** (ovládací okno „Video
  Story“). Watch Me Editor ani žádné jiné okno (Settings, Stop dialog, dialogy editoru)
  se jí neřídí a minimalizují se běžně.
- **Ovládací okno** ([control_window.py:953](src/watch_me/ui/control_window.py:953)):
  `changeEvent` / `_minimized_to_tray` skryje okno do tray, jen když je
  `config.minimize_to_tray` zapnuté. Jinak zůstane obyčejná minimalizace na hlavní panel.
  Po Save v Settings okno použije novou konfiguraci (`result_config`) bez restartu.
  Ověřit, že okno s `WindowStaysOnTopHint` má tlačítko na hlavním panelu, kam se dá
  minimalizovat a odkud jde zase obnovit.
- **Ověření:** pytest-qt v [test_ui.py](tests/unit/test_ui.py): s výchozí konfigurací
  vede `setWindowState(WindowMinimized)` na `isMinimized()` a `in_tray == False`.
  S `minimize_to_tray=True` vede na `in_tray == True` (upravit dnešní testy kolem ř. 876).
  Ručně ověřit obě volby a to, že editor se v obou případech minimalizuje běžně na hlavní
  panel.

### 3. Settings: sekce oddělené čarami (2:39–5:31)

Nové pořadí řádků. Sekce oddělují **jen čáry**, bez nadpisů a popisků (rozhodnuto).
Názvy sekcí v tabulce slouží jen pro orientaci a pro komentáře v kódu, v dialogu nebudou.

| Sekce (jen v kódu) | Řádky |
|---|---|
| General | Theme, Minimize to Tray |
| — čára — | |
| Video | Capture Interval, Image Format, JPEG Quality |
| — čára — | |
| Audio | Audio Input, **Live Transcription** (přesunutý nahoru), Computer Audio |
| — čára — | |
| Recording Options | Mouse, Auto Stop Recording, Archive After, Drawing Grid (popisek zůstane, 5:07–5:11), Recording Folder + Browse… / Open Folder |
| — silnější čára — | |
| | Save, Cancel |

- **Čára:** použít `SeparatorLine` z [separators.py](src/watch_me/editor/separators.py),
  tedy tutéž jednopixelovou čáru v barvě z palety, kterou má editor
  (`form.addRow(SeparatorLine())` přes oba sloupce).
- **Silnější čára před Save/Cancel (rozhodnuto):** nový parametr `SeparatorLine(thickness=…)`
  v fyzických pixelech, výchozí 1. Začít s **2 px**, ručně porovnat s **3 px** a ponechat
  tu, která vypadá lépe. Hodnota bude jedna konstanta (`SETTINGS_FOOTER_LINE_PX`), takže
  změna je na jednom řádku. Výška widgetu se přizpůsobí tloušťce. Dvojitou čáru nepoužít,
  protože v editoru znamená přetahovatelný splitter.
- `_quality_row` se počítá z `rowCount()` po vložení řádku, takže skrývání JPEG Quality
  bude fungovat i s čarami. Dialog zůstane neměnné velikosti.
- **Ověření:** test prochází `QFormLayout` a kontroluje pořadí popisků a pozice čar
  (3 tenké, 1 silnější) a že dialog nemá žádné popisky sekcí. Ručně udělat snímky Settings ve světlém i tmavém tématu.

### 4. Editor: tečky screenů číslované zprava (5:47–6:24)

- **Dnes:** v [recordings_view.py](src/watch_me/editor/recordings_view.py) patří k-tá
  tečka zleva k `screens[k]`, takže screen1 je vlevo (snímek 6:05, tečky ●○).
- **Změna:** k-tá tečka zleva bude patřit k `screens[count-1-k]`, takže nejpravější tečka
  je screen1, druhá zprava screen2 atd. Týká se to `_paint_dots` (vyplněná tečka)
  a `_dot_hit` (párování obdélníků s obrácenými screeny). `dot_rects` jsou zarovnané
  doprava, takže screen1 je ve všech řádcích ve stejném sloupci, ať má nahrávka 1, 2 nebo
  4 screeny. `screen_position` (0 = screen1) a pravidlo „řádek s méně screeny ukáže svůj
  poslední“ zůstanou. Upravit docstring modulu (ř. 4–10).
- **Ověření:** [test_editor_list_rows.py](tests/unit/test_editor_list_rows.py): u řádku se
  dvěma screeny vrátí `dot_at` na pravé tečce screen1 a na levé screen2. Po kliknutí na
  levou tečku ukazují ostatní řádky screen2, případně svůj poslední screen.

### 5. Editor: obrys checkboxu Auto process (6:24–7:07)

- **Dnes:** rámeček indikátoru ve stylu Fusion je šedý a na bílém ani na tmavém pozadí
  není moc vidět.
- **Změna:** malá podtřída `OutlinedCheckBox(QCheckBox)`. `paintEvent` nejdřív zavolá
  `super()` a pak kolem `style().subElementRect(SE_CheckBoxIndicator, …)` nakreslí obrys
  ~1,5 px v barvě `palette().WindowText` (černá `#1e1e1e` ve světlém, `#e6e6e6` v tmavém
  tématu). Obrys tak sleduje téma. Stylesheet nepoužít (viz krok 6).
- **Rozsah (rozhodnuto):** zatím **jen** `auto_process_checkbox`
  ([window.py:813](src/watch_me/editor/window.py:813)). Checkboxy v Settings a jinde
  v editoru zůstanou beze změny. Podtřída bude ve sdíleném modulu (např.
  `src/watch_me/ui/widgets.py`), aby šla později snadno použít všude.
- **Ověření:** `widget.grab()` v obou tématech: pixely na hraně indikátoru mají barvu
  WindowText. Ručně zkontrolovat zaškrtnutý i nezaškrtnutý stav.

### 6. Editor: tlačítko ⋯ vypadá jako New Folder (7:12–8:41)

- **Dnes:** ve světlém tématu má ⋯ při najetí myší tmavou výplň (snímky 7:50 a 8:18),
  New Folder má světlý hover. V tmavém tématu jsou obě tlačítka stejná (8:24).
- **Pravděpodobná příčina:** `folders_menu_button.setStyleSheet("QToolButton::menu-indicator { image: none; }")`
  ([window.py:687](src/watch_me/editor/window.py:687)). Kvůli stylesheetu tlačítko
  kreslí `QStyleSheetStyle`, který kreslí hover jinak než Fusion u autoRaise tlačítka
  a nesleduje změnu palety.
- **Změna:** odstranit stylesheet i `setMenu` + `InstantPopup`. Na `clicked` volat
  `folders_menu.exec(button.mapToGlobal(button.rect().bottomLeft()))`. `aboutToShow` dál
  aktualizuje položky. Tlačítko je pak obyčejné autoRaise `QToolButton` bez indikátoru
  menu, stejné jako New Folder. Ikona teček se už při změně tématu překresluje (ř. 878).
- **Ověření:** test: `folders_menu_button.styleSheet() == ""`, kliknutí otevře menu
  (s nahrazeným `QMenu.exec`), Collapse all / Expand all fungují. Ručně ve světlém
  tématu: hover na ⋯ a na New Folder vypadá stejně, v tmavém tématu beze změny.

### 7. Dokumentace

- [SKILL.md](skills/watch-me/SKILL.md) ř. 94: minimalizace okna rekordéru jde na hlavní
  panel, se zapnutou volbou Minimize to Tray do tray.
- [watch-me-spec.md](watch-me-spec.md): řádek 59 (minimalizace), kap. 5 (nové
  pořadí Settings a sekce, `minimize_to_tray`), seznam nahrávek (tečky zprava), titulky
  kontrastní k tématu.
- Docstringy `settings_dialog.py`, `control_window.py` a `recordings_view.py`.
- Celé testy: `uv run pytest tests/unit`.

## Rizika a předpoklady

- **Titulek (krok 1):** Qt může DWM atribut při vlastních změnách palety přepsat. Proto se
  nastavuje znovu po každém `apply_theme` a při `Show`. Nativní `QFileDialog` (Browse…)
  neovlivníme. Starší Windows 10 bez podpory atributu 20/19 zůstanou u systémového titulku.
- **Titulek v tmavém tématu bude světlý.** Na nahrávce byl v tmavém tématu tmavý a označil
  jsi ho za v pořádku. Podle odpovědi na otázku 1 má ale být kontrastní, takže se to změní.
- **Změna výchozího chování (krok 2):** dnes se ovládací okno vždy schová do tray. Po změně
  se bez zapnuté volby minimalizuje na hlavní panel, kde zabírá místo, a při nahrávání může
  být hůř dosažitelné (zastavit jde dál přes `Ctrl+Alt+S`).
- Obrácené pořadí teček mění chování, na které už můžeš být zvyklý (tooltip tečky dál
  říká, který screen to je).

## Rozhodnutí (odpovědi na otevřené otázky)

1. **Titulek:** kontrastní k tématu. Light → tmavý, Dark → světlý (krok 1).
2. **Sekce Settings:** jen čáry, žádné nadpisy ani popisky (krok 3).
3. **Čára před Save/Cancel:** 2 px, vyzkoušet i 3 px a nechat lepší (krok 3).
4. **Obrys checkboxu:** zatím jen Auto process. Ostatní checkboxy případně později (krok 5).
5. **Minimize to Tray:** jen okno rekordéru, ne editor ani jiná okna (krok 2).

Žádné otevřené otázky nezbývají.
