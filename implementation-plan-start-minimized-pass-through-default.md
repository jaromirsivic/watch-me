# Plán: Start Minimized místo Minimize to Tray, Pass through zapnutý ve výchozím stavu

Zdroj: nahrávka `20261120-135503` (0:00–1:37), master instrukce „Create Plan“.

## Cíl

Dvě úpravy Watch Me Recorderu:

1. **Settings:** položku **Minimize to Tray** nahradí **Start Minimized**, combo box se třemi
   možnostmi *Do not minimize* (výchozí), *Minimize to taskbar*, *Minimize to tray*.
2. **Kreslení:** po Ctrl+Space (nebo Ctrl+F1, Draw) je **Pass through** ve výchozím stavu
   zapnutý (vrstva ukazuje živé obrazovky).

## Co nahrávka ukázala (kontext)

- 0:23–1:01: v dialogu Settings šipky na řádek *Minimize to Tray* / *Do not minimize to tray*
  („místo minimize to tray … něco jako start minimized“), pak na hlavní panel (0:53) a na
  oznamovací oblast u `^` (0:56) jako dvě cílová místa minimalizace.
- 1:02–1:22: šipka na tlačítko *Pass through (P)* v Drawing tools; „teďka myslím si, že
  pástru není ve výchozím stavu zapnuto … chtěl bych, aby ve výchozím stavu bylo zapnuté“.

## Kroky

### 1. Konfigurace (`src/watch_me/core/config.py`)

- Nový klíč `start_minimized: str = "none"` s hodnotami `"none"`, `"taskbar"`, `"tray"`
  (validace jako `theme`/`image_format`), v `config_from_dict` a `to_json_dict`.
- Klíč `minimize_to_tray` zrušit bez náhrady: žádná zpětná kompatibilita ani migrace
  (pravidlo v `CLAUDE.md`).
- `config set start_minimized tray` funguje přes stávající cestu `config set`.

### 2. Settings (`src/watch_me/ui/settings_dialog.py`)

- `MINIMIZE_TO_TRAY_CHOICES` → `START_MINIMIZED_CHOICES`:
  `("none", "Do not minimize")`, `("taskbar", "Minimize to taskbar")`,
  `("tray", "Minimize to tray")`. Řádek **Start Minimized** zůstane hned pod Theme.
- Nový tooltip: co se stane se oknem Watch Me Recorder po stisku Record a co dělá tlačítko
  minimalizace v titulku (viz krok 3).
- Uložení `"start_minimized": self.minimize_combo.currentData()`.

### 3. Okno rekordéru (`src/watch_me/ui/control_window.py`)

- **Po stisku Record** (po úspěšném `controller.start_recording()` z tlačítka Record;
  ne po Continue Recording ani po Resume z pauzy):
  - `"none"`: nic;
  - `"taskbar"`: `showMinimized()` (okno zůstane na hlavním panelu);
  - `"tray"`: `hide_to_tray()`; bez systémové lišty spadne na `showMinimized()`.
- **Tlačítko minimalizace v titulku** (`_minimized_to_tray`): do tray jen při `"tray"`,
  jinak na hlavní panel (dnešní chování „Do not minimize to tray“).
- Konec nahrávání (Stop zkratkou, auto-stop) okno vrátí jako dnes (`restore_from_tray`,
  ř. 781); ověřit, že se obnoví i z `"taskbar"` minimalizace, aby uživatel viděl
  volbu Video Editor / Continue / Discard.
- Upravit docstring modulu (ř. 5–9) a `changeEvent`.

### 4. Pass through zapnutý ve výchozím stavu (`src/watch_me/ui/overlay.py`)

- `DrawingOverlay.show()` (ř. 2101): `self.set_pass_through(False)` → `True`; `__init__`
  (ř. 1821) `_pass_through = True` a komentáře (ř. 88, 1819–1820, docstring modulu).
- Snímek obrazovek při startu kreslení (`set_snapshot`) se dál pořizuje, protože ho
  potřebuje vypnutí Pass through (P) a zoom.
- Timeline (`host/events.py`, `_pass_through_events`) zvládá zapnutí hned při startu
  kreslení (v nahrávce už `PASS THROUGH on` v 25000 a 69500). Žádná změna logiky, jen
  zkontrolovat text legendy a `SKILL.md`, které dnes říkají „by default the drawing layer
  shows the screens as they were when drawing started“.

### 5. Dokumentace

- `watch-me-spec.md` (ř. 61, 69, 74 a popis Pass through), `docs/installation.md:114`,
  `README.md`, `skills/watch-me-recorder/SKILL.md` (sekce 3: Minimize to Tray a Pass through;
  sekce 4: odstavec `PASS THROUGH on / off`; `config` klíče v „Other commands“).

### 6. Testy a ověření

- `tests/unit/test_ui.py`:
  - pořadí a texty Settings (ř. 598, 622): `Start Minimized`, `Do not minimize`;
  - `test_settings_saves_minimize_to_tray` → ukládá `start_minimized` pro všechny tři hodnoty;
  - `test_minimize_stays_on_the_taskbar_unless_minimize_to_tray` (ř. 988–1017) přepsat:
    tlačítko minimalizace → tray jen při `"tray"`;
  - nové: Record s `"none"` okno nechá, s `"taskbar"` minimalizuje, s `"tray"` skryje do
    tray (mock `isSystemTrayAvailable`), bez tray spadne na taskbar; Stop okno obnoví.
- Config testy: výchozí `"none"`, neplatná hodnota → chyba.
- Continue Recording a Resume okno neminimalizují.
- `tests/unit/test_overlay.py`, `test_overlay_pass_through.py`, `test_overlay_redo_grid.py`:
  výchozí stav po `show()` je zapnutý, `P` ho vypne a ukáže snímek ze startu, nový `show()`
  ho znovu zapne.
- `uv run pytest tests/unit` a lint/typy podle `pyproject.toml`.
- Ručně: všechny tři volby se dvěma monitory (Record → okno zmizí / je dole / v tray;
  Ctrl+Alt+S ho vrátí); Ctrl+Space nad běžícím videem: video běží, `P` ho zastaví;
  `timeline` krátké nahrávky.
- Verzi a distribuci neměnit, dokud o to nepožádáš.

## Rizika a předpoklady

- Okno skryté do tray hned po Record: uživatel musí znát zkratky (Ctrl+Alt+S, Ctrl+Space).
  Stávající balónek tray (`hide_to_tray`) to říká; pro `"taskbar"` žádná nápověda není.
- Pass through zapnutý znamená, že frames během kreslení ukazují živé obrazovky; menu, které
  se po Ctrl+Space zavře, už na snímcích nebude (dřív ho zachytil snímek ze startu).
## Rozhodnuto (odpovědi na otázky)

1. Minimalizuje se až po stisku **Record**, ne při otevření okna.
2. Jen po Record; po Continue Recording ani po Resume ne.
3. Zpětnou kompatibilitu ani migraci neřešíme (plugin zatím nikdo nepoužívá; pravidlo
   zapsáno do `CLAUDE.md`).
4. S *Minimize to tray* schovává do tray i tlačítko minimalizace v titulku okna.

## Otevřené otázky

Žádné.
