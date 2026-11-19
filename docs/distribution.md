# Sestavení distribuce pluginu Watch Me

Tento návod platí, kdykoliv uživatel řekne „vyrob novou distribuci“ („sestav distribuci“,
„udělej dist“). Agent podle něj sestaví složku `dist/watch-me-<verze>/`, například
`dist/watch-me-0.5.1/`. Uživatel ji pak zazipuje a pošle komukoliv, kdo si plugin
nainstaluje do Claude Code, Codexu nebo Cursoru.

Návod je psaný tak, aby se dal provést doslova, bez domýšlení. Ověřeno 17. 11. 2026 na
Windows 11 s verzí 0.5.1: celý postup podle něj provedl i Opus 5.5 (effort high).

## Pravidla pro agenta

1. **Postupuj přesně podle kroků 1 až 6, v tomto pořadí.** Bloky příkazů spouštěj
   doslova, nic v nich neměň a nenahrazuj je vlastním postupem.
2. **Každý blok spusť celý jedním voláním nástroje PowerShell**, v kořeni repozitáře.
   Nepoužívej Bash: příkazy jsou v syntaxi PowerShellu. Proměnné se mezi voláními
   neuchovávají, proto si každý blok všechno potřebné nastaví sám. Když nástroj nezačíná
   v kořeni repozitáře, dej na začátek každého bloku řádek
   `Set-Location -LiteralPath '<kořen repozitáře>'`. To je jediný dovolený přídavek.
   K blokům ani k jejich příkazům nepřidávej přesměrování chybového výstupu (`2>&1`,
   `2>$null`): Windows PowerShell 5.1 by pak očekávanou chybu `PYTHON_MISSING` v kroku 5
   vzal jako selhání a blok by ukončil.
3. **Dlouhý příkaz nech doběhnout.** Testy (krok 2) běží asi čtyři minuty a nástroj je
   může po chvíli přesunout na pozadí, i když má nastavený delší limit. Pak počkej na
   oznámení o dokončení a vyhodnoť jeho výstup. Nespouštěj tentýž příkaz podruhé, dokud
   první běží.
4. **Když krok nedopadne tak, jak popisuje „Co musí vyjít“, skonči.** Řekni uživateli,
   který krok selhal a co přesně vypsal. Chybu neobcházej a neopravuj ji úpravou
   souborů v `dist`.
5. **Soubory ve složce `dist/watch-me-<verze>` ručně neupravuj, nepřidávej ani nemaž.**
   Jejich obsah určuje jen krok 3.
6. **Ve složce `dist/watch-me-<verze>` nic nespouštěj**, ani spouštěče, ani `uv`.
   Vznikla by tam `.venv` a `__pycache__` a odešly by příjemci.
7. **Nic necommituj, nezvedej verzi, nepushuj a nevyráběj zip**, pokud o to uživatel
   výslovně nepožádal.
8. **Neptej se na nic, co návod rozhoduje.** Uživatele se ptáš jen tam, kde to návod
   říká (krok 1, necommitované změny).

## Přehled kroků

| Krok | Co se děje | Jak dlouho | Kdy skončit |
| --- | --- | --- | --- |
| 1 | kontrola repozitáře a verze | vteřiny | necommitované změny (zeptej se), neshoda verzí |
| 2 | lint a jednotkové testy | asi 4 minuty | cokoliv neprojde |
| 3 | export z `HEAD` do `dist/watch-me-<verze>` | vteřiny | blok skončí chybou |
| 4 | kontrola obsahu a validace pluginu | vteřiny | kontrola nebo validace neprojde |
| 5 | zkušební instalace v dočasné složce | 10 s až 10 min | kterýkoliv ze čtyř výsledků nesedí |
| 6 | závěrečná zpráva uživateli | | |

## Co je distribuce

- **Hotový standardní plugin ze skutečných souborů.** Ve složce není žádný junction ani
  symbolický odkaz a nic v ní neodkazuje do vývojového repozitáře.
- **Obsah pochází z commitu `HEAD`**, ne z pracovní složky. Soubory vybere `git archive`,
  takže se do distribuce nedostane nic rozpracovaného ani nesledovaného a konce řádků
  odpovídají `.gitattributes` (`.bat` s CRLF, ostatní s LF).
- **Bez prostředí, modelu a FFmpegu.** Ty si příjemce stáhne při prvním spuštění: agent
  dostane od spouštěče chybu `PYTHON_MISSING` nebo `UV_MISSING`, podle
  `skills/watch-me-recorder/references/agent-startup.md` nainstaluje uv, připraví `.venv`
  (`uv sync --locked`) a po chybě `SETUP_REQUIRED` stáhne příkazem `setup` model
  Whisper (548 MB) a FFmpeg do `~/.watch-me`.
- **Složka `dist/` je v `.gitignore`.** Distribuce se necommituje.

### Co do distribuce patří

| Cesta v repozitáři | Proč |
| --- | --- |
| `.claude-plugin/` | manifest pluginu a marketplace `watch-me-local` (Claude Code, Codex) |
| `plugin.json` | manifest ve formátu Agent Plugins (Codex, Cursor) |
| `skills/` | oba skilly se spouštěči a návodem na opravu prostředí |
| `src/` | aplikace |
| `scripts/bootstrap.py`, `scripts/launch.bat`, `scripts/launch.sh` | společný start, který volají spouštěče skillů |
| `scripts/install-hosts.ps1`, `scripts/install-hosts.sh` | registrace skillů odkazem, pro hostitele bez pluginů (popisuje `docs/installation.md`) |
| `pyproject.toml`, `uv.lock` | podle nich uv připraví prostředí; spouštěče podle `pyproject.toml` poznají kořen |
| `README.md`, `LICENSE` | čte je sestavení balíčku (`readme`, `license` v `pyproject.toml`), bez nich `uv sync` selže |
| `models/LICENSE` | licence modelu Whisper |
| `docs/installation.md` | nastavení, MCP server, řešení potíží |
| `docs/distribution-install.md` | průvodce pro příjemce; v distribuci leží v kořeni jako `INSTALL.md` |

### Co do distribuce nepatří

`.git`, `.github`, `.gitignore`, `.gitattributes`, `tests/`, `implementation-plan*.md`,
`watch-me-review*.md`, `watch-me-spec*.md`, `docs/h5-startup-and-wait.md`,
`docs/distribution.md`, vývojové skripty (`scripts/ci_report.py`,
`scripts/frame_changes.py`, `scripts/live_benchmark.py`) a nic, co Git nesleduje: `.venv`,
`config.json`, `models/*.bin`, `bin/`, `__pycache__`, nahrávky.

`README.md` odkazuje na několik vývojových dokumentů, které v distribuci nejsou
(specifikace, plány, `tests/manual/hosts.md`). Je to vědomý ústupek, README se kvůli
distribuci neupravuje.

## Postup

### 1. Ověř repozitář a verzi

```powershell
if (-not ((Test-Path .git) -and (Test-Path pyproject.toml) -and (Test-Path skills\watch-me-recorder\SKILL.md))) { throw 'Tohle není kořen repozitáře Watch Me.' }
$changes = @(git status --porcelain)
"Necommitovaných změn: $($changes.Count)"
$changes
"Commit: $(git log -1 --format='%h %s')"
"Větev: $(git branch --show-current)"
```

Co musí vyjít:

- První řádek je `Necommitovaných změn: 0`. Počítá se každá změna, i nesledovaný soubor
  (řádek začínající `??`).
- Když je počet větší než 0, pod tím řádkem jsou změny vypsané. **Zeptej se uživatele** a
  do odpovědi nepokračuj: „V repozitáři
  jsou necommitované změny (vypiš je). Distribuce vzniká z posledního commitu, takže by
  v ní chyběly. Mám je nejdřív commitnout, nebo sestavit distribuci z posledního commitu
  bez nich?“ Podle odpovědi buď změny commitni a začni krokem 1 znovu, nebo pokračuj a
  v závěrečné zprávě uveď, které změny v distribuci nejsou.
- Krátký hash commitu (první slovo za `Commit:`) a jméno větve si zapamatuj pro
  závěrečnou zprávu.

Verze musí být stejná na všech šesti místech:

```powershell
$found = [ordered]@{
    'plugin.json'                     = (Get-Content -Raw plugin.json | ConvertFrom-Json).version
    '.claude-plugin/plugin.json'      = (Get-Content -Raw .claude-plugin\plugin.json | ConvertFrom-Json).version
    '.claude-plugin/marketplace.json' = (Get-Content -Raw .claude-plugin\marketplace.json | ConvertFrom-Json).plugins[0].version
    'pyproject.toml'                  = [regex]::Match((Get-Content -Raw pyproject.toml), '(?m)^version = "([^"]+)"').Groups[1].Value
    'src/watch_me/__init__.py'        = [regex]::Match((Get-Content -Raw src\watch_me\__init__.py), '__version__ = "([^"]+)"').Groups[1].Value
    'uv.lock'                         = [regex]::Match((Get-Content -Raw uv.lock), '(?m)^name = "watch-me"\r?\nversion = "([^"]+)"').Groups[1].Value
}
$found.GetEnumerator() | ForEach-Object { '{0,-34} {1}' -f $_.Key, $_.Value }
if (@($found.Values | Sort-Object -Unique).Count -ne 1) { throw 'Verze se neshodují.' } else { 'Verze se shodují.' }
```

Co musí vyjít: šest řádků se stejným číslem verze a řádek `Verze se shodují.` Tohle
číslo je `<verze>` ve zbytku návodu. Při chybě `Verze se neshodují.` skonči a vypiš
uživateli všech šest řádků; verzi sám neopravuj.

Sestavení verzi nikdy nezvedá. Distribuce nese verzi, která je v repozitáři. Chce-li
uživatel nové číslo verze, řekne to zvlášť a zvedne ji samostatný commit před sestavením.

### 2. Spusť lint a testy

Dva samostatné příkazy, oběma nastav časový limit nástroje na 10 minut. Testy běží asi
čtyři minuty; když je nástroj přesune na pozadí, počkej na oznámení o dokončení
(pravidlo 3). `uv run` si před prvním příkazem může samo vytvořit nebo doplnit vývojové
prostředí `.venv` v repozitáři a vypsat seznam balíčků. To je v pořádku, `.venv` Git
nesleduje a do distribuce se nedostane.

```powershell
uv run ruff check src tests
```

```powershell
uv run pytest tests/unit -q
```

Co musí vyjít: ruff vypíše `All checks passed!`, pytest skončí řádkem s počtem `passed`
bez `failed` a bez `error`, například `1308 passed, 1 skipped in 223.01s`. Přeskočené
testy (`skipped`) nevadí a do závěrečné zprávy se nepíšou. Když něco neprojde, skonči a
vypiš uživateli, co selhalo; distribuci nesestavuj.

Když uživatel výslovně řekl, že testy nechce, krok vynech a v závěrečné zprávě napiš
„testy vynechány na žádost“.

### 3. Sestav složku

```powershell
$ErrorActionPreference = 'Stop'
$version = (Get-Content -Raw plugin.json | ConvertFrom-Json).version
$target = Join-Path (Get-Location) "dist\watch-me-$version"
$paths = @(
    '.claude-plugin', 'plugin.json', 'skills', 'src',
    'scripts/bootstrap.py', 'scripts/launch.bat', 'scripts/launch.sh',
    'scripts/install-hosts.ps1', 'scripts/install-hosts.sh',
    'pyproject.toml', 'uv.lock', 'README.md', 'LICENSE', 'models/LICENSE',
    'docs/installation.md', 'docs/distribution-install.md'
)

# Starou složku téže verze nahraď. Odkaz ani složku s odkazy nikdy nemaž.
if (Test-Path -LiteralPath $target) {
    $links = @(Get-Item -LiteralPath $target -Force) + @(Get-ChildItem -LiteralPath $target -Recurse -Force) |
        Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }
    if ($links) { throw "V $target je odkaz (junction nebo symlink): $($links[0].FullName). Nic nemažu." }
    Remove-Item -LiteralPath $target -Recurse -Force
    'Nahrazena existující složka této verze.'
}
New-Item -ItemType Directory -Force $target | Out-Null

# Export z HEAD přes soubor zip: roura mezi programy by v PowerShellu binární data poškodila.
$zip = Join-Path $env:TEMP "watch-me-$version-export.zip"
git archive --format=zip --output $zip HEAD -- $paths
if ($LASTEXITCODE -ne 0) { throw 'git archive selhal.' }
Expand-Archive -LiteralPath $zip -DestinationPath $target
Remove-Item -LiteralPath $zip

# Průvodce pro příjemce patří do kořene pod jménem INSTALL.md.
Move-Item -LiteralPath (Join-Path $target 'docs\distribution-install.md') -Destination (Join-Path $target 'INSTALL.md')
"Sestaveno: $target"
```

Co musí vyjít: poslední řádek začíná `Sestaveno:` a končí cestou
`...\dist\watch-me-<verze>`.

- Když se před ním objeví `Nahrazena existující složka této verze.`, uveď to v závěrečné
  zprávě (viz šablona v kroku 6).
- `git archive selhal` s hláškou `pathspec ... did not match any files` znamená, že
  některá cesta ze seznamu `$paths` v commitu `HEAD` není (typicky ještě nebyla
  commitnuta). Skonči a řekni uživateli, která to je.
- Seznam `$paths` v tomto bloku je jediný zdroj pravdy o obsahu distribuce. Krok 4
  používá stejný seznam; oba se mění jen společně (viz „Údržba návodu“).

### 4. Zkontroluj výsledek

```powershell
$ErrorActionPreference = 'Stop'
$version = (Get-Content -Raw plugin.json | ConvertFrom-Json).version
$target = Join-Path (Get-Location) "dist\watch-me-$version"
$paths = @(
    '.claude-plugin', 'plugin.json', 'skills', 'src',
    'scripts/bootstrap.py', 'scripts/launch.bat', 'scripts/launch.sh',
    'scripts/install-hosts.ps1', 'scripts/install-hosts.sh',
    'pyproject.toml', 'uv.lock', 'README.md', 'LICENSE', 'models/LICENSE',
    'docs/installation.md', 'docs/distribution-install.md'
)
$all = @(Get-ChildItem -LiteralPath $target -Recurse -Force)
$files = @($all | Where-Object { -not $_.PSIsContainer })
$problems = @()

# a) stejný počet souborů jako v HEAD
$expected = @(git ls-tree -r --name-only HEAD -- $paths).Count
if ($files.Count -ne $expected) { $problems += "Počet souborů $($files.Count), v HEAD je $expected." }

# b) žádný odkaz
$all | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } |
    ForEach-Object { $problems += "Odkaz: $($_.FullName)" }

# c) nic, co do distribuce nepatří
$all | Where-Object {
    $_.Name -in '.venv', '.git', '.github', '__pycache__', 'config.json', 'tests' -or
    $_.Extension -in '.bin', '.pyc', '.log'
} | ForEach-Object { $problems += "Nepatří sem: $($_.FullName)" }

# d) všechno, bez čeho plugin nejde nainstalovat nebo spustit
foreach ($need in @(
    'INSTALL.md', 'README.md', 'LICENSE', 'plugin.json', 'pyproject.toml', 'uv.lock',
    '.claude-plugin\plugin.json', '.claude-plugin\marketplace.json',
    'scripts\bootstrap.py', 'scripts\launch.bat', 'scripts\launch.sh',
    'src\watch_me\__init__.py', 'docs\installation.md',
    'skills\watch-me-recorder\SKILL.md', 'skills\watch-me-recorder\scripts\watch-me-recorder.bat',
    'skills\watch-me-recorder\scripts\watch-me-recorder.sh',
    'skills\watch-me-recorder\references\agent-startup.md',
    'skills\watch-me-video-editor\SKILL.md', 'skills\watch-me-video-editor\scripts\watch-me-video-editor.bat',
    'skills\watch-me-video-editor\scripts\watch-me-video-editor.sh',
    'skills\watch-me-video-editor\references\agent-startup.md'
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $target $need) -PathType Leaf)) { $problems += "Chybí: $need" }
}

# e) verze v manifestech distribuce
foreach ($manifest in 'plugin.json', '.claude-plugin\plugin.json') {
    $v = (Get-Content -Raw -LiteralPath (Join-Path $target $manifest) | ConvertFrom-Json).version
    if ($v -ne $version) { $problems += "$manifest má verzi $v, čekám $version." }
}

"Souborů: $($files.Count), velikost: $([math]::Round(($files | Measure-Object Length -Sum).Sum / 1MB, 2)) MB"
if ($problems) { $problems; throw 'Distribuce neprošla kontrolou.' } else { 'Kontroly a) až e) prošly.' }
```

Co musí vyjít: řádek `Souborů: N, velikost: X MB` (obě čísla opiš do závěrečné zprávy
tak, jak jsou vypsaná; u verze 0.5.1 to bylo `Souborů: 152, velikost: 1.92 MB`) a řádek
`Kontroly a) až e) prošly.` Při `Distribuce neprošla kontrolou.` skonči a vypiš
uživateli všechny řádky s problémy. Neopravuj je ručně v `dist`.

Pak validace manifestů a skillů nástrojem Claude Code:

```powershell
$version = (Get-Content -Raw plugin.json | ConvertFrom-Json).version
claude plugin validate (Join-Path (Get-Location) "dist\watch-me-$version")
```

Co musí vyjít: poslední řádek výpisu obsahuje `Validation passed` (před ním může být
znak zaškrtnutí, v konzoli někdy zkomolený). Varování o chybějící ikoně
(`ICON_MISSING`), rada o instalačním řádku v README a odstavec „About these checks“
výsledek nemění a nic se kvůli nim nedělá. Když příkaz `claude` na počítači není (PowerShell ho nenajde), validaci vynech a
v závěrečné zprávě napiš „validace vynechána, příkaz claude není k dispozici“.

### 5. Zkušební instalace mimo `dist`

Zkouška napodobí to, co udělá hostitel a agent u příjemce: zkopíruje plugin jinam,
spouštěč nahlásí chybějící prostředí, uv ho připraví a spouštěč pak odpoví. Běží nad
kopií v dočasné složce (záměrně s mezerou v cestě), nikdy ne v `dist`.

Nastav časový limit nástroje na 10 minut: s prázdnou mezipamětí uv se stahují stovky MB
balíčků, s naplněnou to trvá pár vteřin. Když nástroj blok přesune na pozadí, počkej na
oznámení o dokončení (pravidlo 3).

```powershell
$ErrorActionPreference = 'Stop'
$version = (Get-Content -Raw plugin.json | ConvertFrom-Json).version
$target = Join-Path (Get-Location) "dist\watch-me-$version"
$try = Join-Path $env:TEMP "watch-me dist-try\watch-me\$version"
if (Test-Path -LiteralPath $try) { Remove-Item -LiteralPath $try -Recurse -Force }
New-Item -ItemType Directory -Force (Split-Path $try) | Out-Null
Copy-Item -LiteralPath $target -Destination $try -Recurse
$bat = Join-Path $try 'skills\watch-me-recorder\scripts\watch-me-recorder.bat'
Remove-Item Env:WATCH_ME_ROOT -ErrorAction SilentlyContinue

'--- 1) před přípravou prostředí: čekám PYTHON_MISSING, kód 22'
cmd /d /c call "$bat" version
"kód: $LASTEXITCODE"

'--- 2) příprava prostředí podle agent-startup.md: čekám kód 0'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $try '.venv'
uv sync --locked --python 3.12 --project $try
"kód: $LASTEXITCODE"
Remove-Item Env:UV_PROJECT_ENVIRONMENT

"--- 3) po přípravě: čekám ok true, verzi $version, kód 0"
cmd /d /c call "$bat" version
"kód: $LASTEXITCODE"

'--- 4) co chybí ke spuštění: čekám kód 0 nebo 4'
cmd /d /c call "$bat" setup --check
"kód: $LASTEXITCODE"
```

Co musí vyjít (všechny čtyři body, jinak zkouška neprošla):

1. Pod řádkem `--- 1)` je JSON s `"code":"PYTHON_MISSING"` a pod ním `kód: 22`. Pole
   `root` v tom JSONu ukazuje do dočasné složky `...\watch-me dist-try\watch-me\<verze>`,
   ne do repozitáře. Tahle chyba je tady správný výsledek, ne selhání.
2. Pod řádkem `--- 2)` vypíše uv seznam nainstalovaných balíčků a pod ním je `kód: 0`.
   Mezi balíčky jsou i vývojové (`pytest`, `ruff`); tak to dělá i oprava prostředí
   u příjemce a je to v pořádku.
   Chyba lockfilu znamená, že `uv.lock` neodpovídá `pyproject.toml`: skonči a řekni to
   uživateli, oprava patří do repozitáře (`uv lock` a commit), ne do distribuce.
3. Pod řádkem `--- 3)` je JSON s `"ok": true` a `"version": "<verze>"`, pod ním `kód: 0`.
4. Pod řádkem `--- 4)` je JSON a pod ním `kód: 0` nebo `kód: 4`. Na vývojovém počítači
   bývá 0, protože model už leží v `~/.watch-me`; u příjemce by vyšlo 4 a jeho agent by
   spustil `setup`. Zkouška nic nestahuje do složky stavu a nemění nastavení.

Potom, **ať zkouška prošla, nebo ne**, smaž zkušební kopii (je v ní několik set MB):

```powershell
Remove-Item -LiteralPath (Join-Path $env:TEMP 'watch-me dist-try') -Recurse -Force
'Zkušební kopie smazána.'
```

Nakonec spusť ještě jednou první blok kroku 4 (ten, který končí
`Kontroly a) až e) prošly.`). Tím ověříš, že zkouška v distribuci nic nezanechala.

### 6. Řekni, co vzniklo

Závěrečnou zprávu napiš uživateli česky podle této šablony. Vyplň skutečné hodnoty a
řádky, které neplatí, vynech:

```text
Distribuce je hotová: dist/watch-me-<verze>

- Verze <verze>, větev <větev>, commit <hash>
- <N> souborů, <X> MB
- Testy: ruff v pořádku, pytest <počet> passed        (nebo: vynechány na žádost)
- Kontrola obsahu: prošla
- Validace pluginu (claude plugin validate): prošla    (nebo: vynechána, příkaz claude není k dispozici)
- Zkušební instalace: prošla (PYTHON_MISSING -> uv sync -> version <verze> -> setup --check kód <0 nebo 4>)
- Nahradil jsem dřívější složku téže verze. Pokud už ji někdo dostal, zvaž před
  rozesláním zvednutí verze, jinak se dvě různé distribuce <verze> nedají rozlišit.
- V distribuci nejsou tyto necommitované změny: <seznam>

Zazipuj celou složku „watch-me-<verze>“ (včetně .claude-plugin) a pošli ji.
Příjemce postupuje podle INSTALL.md v jejím kořeni.
```

Zip dělá uživatel sám. Agent ho vyrobí jen na výslovnou žádost, a to systémovým `tar`,
který zapisuje cesty s lomítky čitelnými i na Linuxu a macOS:

```powershell
$version = (Get-Content -Raw plugin.json | ConvertFrom-Json).version
& "$env:SystemRoot\System32\tar.exe" -a -c -f "dist\watch-me-$version.zip" -C dist "watch-me-$version"
"Zip: dist\watch-me-$version.zip, kód: $LASTEXITCODE"
```

## Když něco selže

| Co se stalo | Co to znamená | Co udělat |
| --- | --- | --- |
| `Tohle není kořen repozitáře Watch Me.` | příkazy neběží v kořeni repozitáře | přejdi do kořene repozitáře a začni krokem 1 |
| `Necommitovaných změn:` je větší než 0 | pracovní složka není čistá | zeptej se uživatele (krok 1) |
| `Verze se neshodují.` | šest míst s verzí není v souladu | skonči, vypiš šest řádků |
| ruff nebo pytest neprojde | kód není připravený k rozeslání | skonči, vypiš selhání |
| `pathspec ... did not match any files` | cesta ze seznamu `$paths` není v `HEAD` | skonči, řekni která |
| `V ... je odkaz (junction nebo symlink)` | v `dist` je odkaz, který tam nemá být | skonči, nic nemaž, řekni cestu odkazu |
| `Distribuce neprošla kontrolou.` | obsah `dist` neodpovídá očekávání | skonči, vypiš problémy |
| validace neskončí `Validation passed` | manifest nebo skill má chybu | skonči, vypiš chyby z validace |
| krok 5: jiný výsledek než čtyři popsané | plugin by se u příjemce nespustil | smaž zkušební kopii, skonči, vypiš výstup |
| nástroj přesunul příkaz na pozadí | příkaz dál běží | počkej na oznámení o dokončení, nespouštěj ho znovu |
| nástroj příkaz ukončil pro vypršení času | limit byl kratší než běh | spusť tentýž blok znovu s limitem 10 minut |

Ve všech případech „skonči“ zůstává složka `dist/watch-me-<verze>` tak, jak je; řekni
uživateli, že **není ověřená a nemá se rozesílat**.

## Jak plugin nainstaluje příjemce

Podrobně to popisuje `INSTALL.md` v kořeni distribuce (zdroj:
[distribution-install.md](distribution-install.md)). Ve zkratce:

| Hostitel | Instalace |
| --- | --- |
| Claude Code | `/plugin marketplace add <složka>`, potom `/plugin install watch-me@watch-me-local` |
| Codex | `codex plugin marketplace add <složka>`, potom `/plugins`, záložka `watch-me-local`, nainstalovat `watch-me` |
| Cursor | zkopírovat složku do `~/.cursor/plugins/local/watch-me` a znovu načíst okno |

Hostitel si složku zkopíruje k sobě. Při prvním „Start Watch Me“ agent připraví prostředí
u té kopie a stáhne model a FFmpeg do `~/.watch-me`. Proto musí být distribuce čistá:
cokoliv navíc (`.venv`, `config.json`) by se zkopírovalo také a u příjemce by to
nefungovalo, nebo by si plugin držel stav ve složce, kterou příští aktualizace přepíše.

Stav ověření hostitelů je stejný jako v [installation.md](installation.md): Claude Code
na Windows se používá, kroky pro Codex a Cursor jsou psané podle jejich dokumentace a
ještě nebyly vyzkoušeny. Archiv vyrobený na Windows nenese příznak spustitelnosti, proto
`INSTALL.md` na Linuxu a macOS radí `chmod +x` na spouštěče.

## Údržba návodu

- Přibude-li v repozitáři soubor nebo složka, bez které plugin u příjemce nepoběží,
  doplň ji do seznamu `$paths` v krocích 3 a 4 (oba seznamy musí být stejné), do tabulky
  „Co do distribuce patří“ a případně do seznamu povinných souborů v kroku 4 d).
- Změní-li se instalace v některém hostiteli, uprav `docs/distribution-install.md` a
  tabulku výše; `docs/installation.md` zůstává podrobným zdrojem.
