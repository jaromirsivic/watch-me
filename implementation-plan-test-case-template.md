# Plán: šablony jako soubory, combo box Language a šablona „Test Case“

Zdroj: nahrávka `20261123-001736`, master instrukce „Create Plan“. Etapa 2 vychází z ořezu
(3:53–15:51), etapa 1 ze začátku nahrávky (0:00–3:53), který jsi mi dovolil přečíst a pak
zařadil do plánu jako první etapu.
Čtvrtá verze: zapracovává tvoje odpovědi z chatu. Nic není implementováno; čeká na schválení.

## Cíl

Dialog **Instructions for the AI** (Watch Me Video Editor) dostane tři věci:

1. **Šablony jako soubory.** Texty šablon se přesunou z kódu do souborů. Combo box se sestaví
   z vestavěné složky a ze složky vlastních šablon `custom-instructions`, takže nový soubor
   znamená novou položku.
2. **Combo box Language** vedle combo boxu šablon. Vybraný jazyk se propíše do textu šablony.
3. **Nová šablona Test Case** pod `Implement`: velký markdown, podle kterého AI agent
   z nahrávky vytvoří hybridní test case ve složce `test-cases` projektu.

## Rozhodnuto (tvoje odpovědi)

- Šablona Test Case je **obecná**, bez čehokoli mimosího.
- Výstupy se píšou **anglicky** a je to řečeno hned v nadpisu Goal; jazyk jde přepínat.
- Závěrečný report běhu je **`report.md`** vedle `run.log`.
- Položka se jmenuje **`Test Case`**, postup testu je v **`tests/<test>/test.md`**.
- Šablony leží v **`src/watch_me/editor/assets/instructions/`** a načítají se za běhu,
  **všechny**, i tři dnešní. Soubor, který tam přibude, vytvoří novou položku combo boxu.
- Vlastní šablony mají druhou složku **`custom-instructions`** ve stavové složce
  (typicky `~/.watch-me/custom-instructions/`), která přežije aktualizaci pluginu.
- Combo box Language zůstává při `Custom` aktivní, ale na text nesahá.
- Combo box Language je **první etapa** tohoto plánu, Test Case druhá.
- Testy řídí agent podle `test.md` a skripty jsou po částech (**varianta A**, bez runneru).

## Etapy a kdo je dělá

| Etapa | Obsah | Kdo |
| --- | --- | --- |
| 1 | Šablony jako soubory, combo boxy Action a Language, jazyk v šablonách | subagent Opus 5.5, úsilí high |
| 2 | Markdown šablony Test Case, jeho zařazení, testy a dokumentace | hlavní session (Fable 5.2) |

- Etapa 1 je přesně zadaná a hlídají ji testy, takže na ni Opus 5.5 s úsilím high stačí.
  Po jejím dokončení projdu diff, sám spustím `uv run pytest` a `uv run ruff check`
  a zkusím dialog v editoru. Teprve pak začne etapa 2.
- Etapu 2 dělám sám: destilace vyžaduje úsudek a prostudované zdroje mám v kontextu.
  Úpravy kódu jsou v ní malé, protože načítání souborů zavede už etapa 1.

## Etapa 1: šablony jako soubory a combo box Language

### Co nahrávka ukázala (0:00–3:53)

- 0:24–0:52: řádek s combo boxem šablon (obdélník #2). Combo box se zúží, vpravo na stejný
  řádek přijde druhý combo box s výběrem jazyka (obdélník #3). Nad levý patří nadpis
  **Action**, nad pravý **Language** (šipky #4 a #5).
- 0:52–1:14: v seznamu jazyků je nahoře angličtina, druhá čeština, pak vodorovný oddělovač
  a pod ním všechny světové jazyky, mezi nimi znovu angličtina i čeština.
- 1:15–1:58: `Draft Intent` dostane do nadpisu Goal závorku s jazykem (šipka #6). Výchozí je
  vždy angličtina. Totéž platí pro `Create Plan`.
- 2:02–3:38: `Implement` závorku nedostane. Po několika přeformulováních platí poslední
  znění: jazykem implementace a komentářů ve zdrojovém kódu je angličtina; výchozím jazykem
  uživatelského rozhraní výstupu je vybraný jazyk. Slovo „ale“ tam být nemá.

### 1.1 Soubory šablon (`src/watch_me/editor/assets/instructions/`)

- Tři nové soubory s texty, které jsou dnes v kódu: `10-draft-intent.md`,
  `20-create-plan.md`, `30-implement.md`. Číslo na začátku názvu určuje pořadí v combo boxu.
- Formát souboru: nepovinná hlavička a pod ní text instrukcí.

  ```markdown
  ---
  name: Draft Intent
  tooltip: Turn the recording into a formal brief, then ask how to continue
  ---
  # Goal: a formal brief only (all outputs will be written in {language})
  ...
  ```

- Bez hlavičky se název položky odvodí z názvu souboru (`50-code-review.md` → „Code Review“)
  a tooltip zůstane prázdný. Hlavička se do instrukcí nepíše.
- Značka `{language}` v textu se nahradí vybraným jazykem. Soubor bez značky je platná
  šablona, na kterou jazyk nemá vliv.
- Změny textů:
  - `Draft Intent`: `# Goal: a formal brief only (all outputs will be written in {language})`.
  - `Create Plan`: `# Goal: an implementation plan (all outputs will be written in {language})`.
  - `Implement`: nadpis beze změny; přibudou dvě odrážky: `The implementation language and
    the language of comments in the source code is English.` a `The default language of a
    user interface in the output is {language}.`
- **Ověření:** soubory existují, každý má hlavičku se jménem a tooltipem, `Draft Intent`
  a `Create Plan` mají `{language}` v prvním řádku textu, `Implement` v odrážce.

### 1.2 Načítání šablon (nový modul `src/watch_me/editor/instruction_templates.py`)

- `TEMPLATES_DIR = Path(__file__).with_name("assets") / "instructions"` (stejně jako
  `SVG_PATH` v `mouse_activity.py`): vestavěné šablony.
- `custom_templates_dir() -> Path`: `state_root() / "custom-instructions"` (`state_root` je
  v `core/config.py`). Složka se sama nevytváří; když neexistuje, žádné vlastní šablony
  nejsou. Formát souborů je stejný jako u vestavěných, včetně `{language}`.
- `load_templates(*folders) -> list[Template]`: přečte všechny `*.md` nejdřív z vestavěné
  složky, pak z `custom-instructions`, v každé seřazené podle názvu souboru. Vlastní šablony
  jsou tedy v combo boxu pod vestavěnými. `Template` má `name`, `tooltip`, `text` (se
  značkou) a metodu `render(language) -> str`.
- Soubor se přeskočí a zapíše do logu jako varování, když nejde přečíst, je prázdný, jmenuje
  se `Custom` nebo stejně jako dřívější šablona (vestavěná má přednost před vlastní), nebo je
  jeho text delší než `MAX_INSTRUCTIONS_CHARS` (uložení by ho jinak potichu ořízlo).
- Konstanty `DRAFT_INTENT`, `CREATE_PLAN`, `IMPLEMENT` a n-tice `TEMPLATES`
  z `instructions_dialog.py` zmizí; nic je nenahrazuje.
- **Ověření:** unit testy nad dočasnými složkami (`tmp_path`): pořadí podle názvu souboru,
  vestavěné před vlastními, chybějící složka `custom-instructions` nevadí, hlavička, název
  odvozený z názvu souboru, přeskočené soubory (i vlastní se jménem vestavěné),
  `render("Czech")`.

### 1.3 Seznam jazyků (nový modul `src/watch_me/core/languages.py`)

- `DEFAULT_LANGUAGE = "English"`, `TOP_LANGUAGES = ("English", "Czech")` a `ALL_LANGUAGES`:
  anglické názvy jazyků podle ISO 639-1 (asi 180 položek), abecedně. Názvy jsou anglicky,
  protože se vkládají do anglické věty („written in Czech“).
- **Ověření:** unit test: seznam je seřazený, bez duplicit, obsahuje English i Czech.

### 1.4 Dialog (`src/watch_me/editor/instructions_dialog.py`)

- Řádek pod vysvětlením: vlevo nadpis **Action** a pod ním combo box šablon (roztažený),
  vpravo nadpis **Language** a pod ním combo box jazyků (pevná šířka, zhruba třetina řádku).
- Combo box šablon: `Custom` a pak šablony z
  `load_templates(TEMPLATES_DIR, custom_templates_dir())`. Obě složky se čtou při každém
  otevření dialogu (dialog se vytváří znovu při každém kliknutí na Instructions,
  `window.py:2427`), takže soubor přidaný za běhu editoru je vidět při dalším otevření.
- Combo box jazyků: English, Czech, oddělovač (`insertSeparator`), `ALL_LANGUAGES`. Výchozí
  je vždy English; výběr se nikam neukládá, nese ho text instrukcí.
- Výběr šablony vloží `template.render(<vybraný jazyk>)`.
- Změna jazyka při vybrané šabloně text přegeneruje bez dotazu (text je v tu chvíli přesně
  šablona, nic se neztrácí). Při `Custom` zůstává combo box Language aktivní, ale nic
  nedělá: text se nemění.
- Otevření dialogu s uloženým textem: hledá se šablona a jazyk, jejichž `render` dá přesně
  ten text; najdou-li se, oba combo boxy se podle toho nastaví. Jinak `Custom` a English.
- Ruční úprava textu dál přepne šablonu na `Custom`; jazyk zůstane, jak je.
- Docstring modulu přepsat podle nového chování.
- **Ověření:** `tests/unit/test_editor_requests.py` přepsat na nové API a doplnit:
  - combo šablon = `Custom` + vestavěné šablony + vlastní ze složky `custom-instructions`
    (test se složkou, kam se mezi dvěma otevřeními dialogu přidá soubor);
  - combo box Language je při `Custom` aktivní;
  - seznam jazyků: English, Czech, oddělovač, pak celý seznam; výchozí English;
  - `Draft Intent` + Czech → první řádek končí `(all outputs will be written in Czech)`;
  - `Implement` + Czech → nadpis bez závorky, odrážka o rozhraní říká Czech, odrážka o kódu
    English;
  - změna jazyka u vybrané šablony změní text a nezeptá se; u `Custom` text nezmění;
  - text uložený jako `Create Plan` v češtině otevře dialog na `Create Plan` a Czech;
  - dosavadní testy dotazů před přepsáním a přepnutí na `Custom` projdou i po úpravě.

### 1.5 Dokumentace

- `README.md` (ř. 71), `watch-me-spec.md` (ř. 173), `skills/watch-me-video-editor/SKILL.md`
  (ř. 111): Action a Language, jazyk v šablonách, šablony jako soubory a jak přidat vlastní
  do `custom-instructions` ve stavové složce (`config path` říká, kde stavová složka je).
- **Ověření:** `uv run pytest`, `uv run ruff check`; ručně v editoru: oba combo boxy
  s nadpisy, `Create Plan` + Czech dá správný nadpis, Save a nové otevření obnoví oba výběry;
  po zkopírování nového `.md` do `custom-instructions` se při dalším otevření dialogu objeví
  nová položka pod vestavěnými.

## Etapa 2: šablona Test Case

### Co nahrávka ukázala (3:53–15:51)

- 3:53–4:05, 15:15–15:21: nová položka patří do combo boxu pod `Implement` (šipka #15). Text
  šablony se objeví v textovém poli pod combo boxem (šipka #9).
- 4:08–5:00: zdroj je `D:\git\usy_mimosa_mockups\plugins\test-balancing-energy-market`,
  primárně `skills\mimosa-test-skill-authoring\SKILL.md` (cesta ve schránce v 4:50).
- 5:00–5:59: podstata, která má v textu být: test case startuje ústním zadáním agentovi nebo
  startovacím skriptem (typicky `start.bat`). Co jde dělat deterministicky, dělá se
  deterministicky. Když něco selže, zkusí to vyřešit AI agent, případně požádá uživatele
  o pomoc. Po vyřešení se pokračuje dalšími deterministickými částmi. Když to vyřešit nejde,
  skript selže.
- 6:26–14:45: struktura složky `test-cases` (konečná podoba ze schránky v 14:42, doplněná
  o soubory, které jsi jmenoval):

  ```text
  test-cases
  - README.md
  - scripts
  - - <popisný název>.py / .bat / .sh
  - tests
  - - test1
  - - - test.md
  - - test2
  - docs
  - - test1
  - - - documentation.md
  - - test2
  - logs
  - - test1
  - - - 2026-11-10-10-30-00
  - - - - run.log
  - - - - report.md
  ```

- 15:23–15:46: markdown se nejdřív uloží do projektu Watch Me, cesta se ukáže v chatu a další
  úpravy začnou až po přečtení.

Jak jsem četl nejasná slova přepisu: „dots“ = `docs` (potvrzuje schránka), „test 1 vat“ =
`test1_part1.bat`, „Mimoza“ = Mimosa, „obřízký skill“ = velký skill.

Změny názoru v nahrávce: složka běhů se postupně jmenovala `runs`, `run reports`,
`run-reports`, `run logs` a nakonec **`logs`**; platí `logs`. Názvy `test1_part1.bat` jsou jen
ilustrace, skripty mají mít názvy, které říkají, co skript dělá.

### Jak test běží (varianta A)

Test je rozdělený na několik malých skriptů, každý dělá jednu deterministickou část.
`test.md` je seznam kroků a u každého je napsáno, který skript ho provádí, nebo že ho dělá
agent či uživatel. Agent jde podle `test.md` shora dolů a skripty spouští. Každý skript skončí
návratovým kódem:

| Kód | Význam | Co následuje |
| --- | --- | --- |
| 0 | část prošla | další krok |
| 1 | chyba produktu (test selhal) | konec, agent nic neobchází |
| 2 | blokováno prostředím (VPN, přihlášení) | odstranit příčinu, spustit část znovu |
| 3 | selhala automatizace | agent udělá tuhle část ručně podle `test.md`, pak spustí další skript |

Test bez kroků pro agenta může celý pustit startovací skript (`start.bat` / `start.sh`),
který části spustí za sebou a zastaví se na prvním nenulovém kódu.

### Co jsem prostudoval

- `skills/mimosa-test-skill-authoring/SKILL.md` (celý), `shared/conventions.md` (celý),
  `skills/mimosa-test-run/SKILL.md` (celý). Na tyto dva soubory se authoring skill odkazuje.
- Nečetl jsem: `config.json` (obsahuje přihlašovací údaje), referenční skill
  `mimosa-internal-dashboard-overview`, `mimosa-login`, `mimosa-bug-report`, knihovnu
  `lib/mimosa_testkit`. Při psaní markdownu projdu ještě referenční skill a `mimosa-login`.

### 2.1 Napsat markdown šablony a dát ho k přečtení (stop)

- **Kde:** `src/watch_me/editor/assets/instructions/40-test-case.md`, s hlavičkou
  `name: Test Case` a `tooltip: Turn the recording into a repeatable test case (scripts,
  steps for the AI, documentation)`. Po etapě 1 se tím položka rovnou objeví v combo boxu,
  takže si text můžeš přečíst v souboru i v dialogu.
- **Jazyk textu šablony:** anglicky, jako ostatní šablony.
- **Rozsah:** cíl do 12 000 znaků, tvrdý strop 20 000 (`MAX_INSTRUCTIONS_CHARS`).
- **Jazyk výstupů:** značka `{language}` je v souboru právě jednou, v nadpisu Goal. Zbytek
  textu říká jen „the output language“. Hned pod nadpisem je věta, čeho se jazyk týká
  (`README.md`, `test.md`, `documentation.md`, `report.md`, zprávy uživateli) a co je vždy
  anglicky (názvy souborů a složek, kód skriptů, komentáře, řádky `run.log`).
- **Obsah je obecný:** žádné FD04, uuCmd, `config.json`, `mimosa-login`, žádná jména
  zákazníka ani údaje z jeho projektu. Osnova:
  1. **Goal** – `# Goal: a test case (all outputs will be written in {language})`, věta
     o jazyce a zadání: z nahrávky (jen z ořezu) vytvoř test case; co uživatel ukazuje
     a říká, jsou kroky a očekávané výsledky.
  2. **Principles** – hybridní test: co lze naprogramovat, je naprogramováno. Start ústním
     zadáním nebo startovacím skriptem. Při selhání zkusí část vyřešit agent, pak požádá
     uživatele, pak pokračují další deterministické části. Nejde-li to, test selže.
  3. **The `test-cases` folder** – najdi ji v projektu. Když neexistuje, vytvoř ji se třemi
     podsložkami `scripts`, `tests`, `docs` a s `README.md`, který popisuje strukturu, a vypiš
     uživateli, že vznikla, co v ní je a její absolutní cestu. Když není jasné, kde je projekt
     nebo kam složka patří, zeptej se. `logs` vzniká při prvním běhu.
  4. **`scripts/`** – spustitelné soubory všech testů, jedna deterministická část na skript,
     názvy podle toho, co dělají. Primárně Python (Playwright pro prohlížeč, Python pro REST),
     protože běží na Windows, macOS i Linuxu. Spouštěče `.bat` a `.sh`, případně startovací
     skript testu. Nejdřív platforma uživatele, který test nahrál; multiplatformnost, kdykoli
     to jde. Návratové kódy 0 / 1 / 2 / 3. Společný kód (log, kódy) patří od druhého skriptu
     do pomocného modulu.
  5. **`tests/<test>/test.md`** – postup pro AI agenta krok za krokem: čeho dosáhnout,
     tabulka kroků `# | Action | Expected result | Done by` (skript jménem, `ai` nebo `user`
     s důvodem), prerekvizity (jiné testy i skripty), testovací data, úklid.
  6. **`docs/<test>/documentation.md`** – lidský popis pro uživatele a klienta: o čem test je,
     prerekvizity, předpoklady, co dělá, co ověřuje. Žádné instrukce pro agenta.
  7. **`logs/<test>/<YYYY-MM-DD-HH-MM-SS>/`** – složku běhu založí ten, kdo test spouští
     (agent nebo startovací skript), a předá ji skriptům. `run.log`: co a jak se dělo.
     `report.md`: závěrečný report (výsledek, kroky s tím, kdo je provedl, nálezy).
  8. **Reuse and dependencies** – z toho, co uživatel říká, poznej vazby mezi testy
     a skripty; existující skripty a testy použij nebo uprav, neduplikuj.
  9. **Automation rules** – destilát oddílu 3 authoring skillu: chyba produktu (kód 1) proti
     chybě automatizace (kód 3), pořadí lokátorů bez CSS a XPath, žádné sleepy, čas se počítá,
     data testu nesou prefix běhu, úklid na konci, každá část začíná ze stavu, který nechala
     předchozí, žádné natvrdo zapsané URL a přihlašovací údaje.
  10. **Taking a part over** – agent nejdřív posoudí, jestli nejde o chybu produktu, pak
      udělá právě tu jednu část, nikdy nezměkčuje očekávaný výsledek, zapíše to do `run.log`
      a do `report.md` navrhne opravu skriptu.
  11. **Workflow** – nejdřív `test.md`, pak skripty, pak `documentation.md`, pak povinný
      zelený běh; co na konci říct uživateli (co test pokrývá, které kroky dělá agent nebo
      uživatel a proč, co test mění, kde je log).
  12. **Repairing a test** – oprava skriptu podle reportu jen se souhlasem uživatele.
- **Ověření:** soubor má pod 20 000 znaků, obsahuje `{language}` právě jednou, neobsahuje
  slova `mimosa`, `fingrid`, `uucmd`. Vypíšu absolutní cestu do chatu a **počkám, až si ho
  přečteš**. Kroky 2.2–2.4 začnou až po tvém souhlasu s textem.

### 2.2 Testy (`tests/unit/test_editor_requests.py`)

- Vestavěné šablony jsou `Draft Intent`, `Create Plan`, `Implement`, `Test Case` v tomto
  pořadí.
- Tři krátké šablony mají pod 1 000 znaků; `Test Case` nejvýš `MAX_INSTRUCTIONS_CHARS`.
- `normalize_instructions(text) == text.strip()` pro `Test Case` v angličtině i v nejdelším
  názvu jazyka (limit text neořízne, takže dialog šablonu po uložení zase pozná).
- První řádek je `# Goal: a test case (all outputs will be written in English)`; soubor má
  `{language}` právě jednou a slovo `English` také jen jednou, ve větě o tom, co je vždy
  anglicky.
- Text obsahuje `test-cases`, `scripts`, `tests`, `docs`, `logs`, `README.md`, `test.md`,
  `documentation.md`, `run.log`, `report.md`; neobsahuje `mimosa`.
- **Ověření:** `uv run pytest tests/unit/test_editor_requests.py` a `uv run ruff check`.

### 2.3 Dokumentace

- `README.md`, `watch-me-spec.md`, `skills/watch-me-video-editor/SKILL.md`: doplnit čtvrtou
  šablonu a jednou větou, co dělá.
- **Ověření:** `grep -rn "Create Plan"` nenajde výčet šablon bez `Test Case`.

### 2.4 Závěrečné ověření

- Celá sada `uv run pytest` a `uv run ruff check`.
- Jedna krátká zkušební nahrávka se šablonou Test Case v češtině: `wait` vrátí `instructions`
  celé (neoříznuté) a s češtinou v nadpisu, `instructions.txt` odpovídá vyplněné šabloně.

## Rizika a předpoklady

- **Vlastní šablony patří do `custom-instructions`.** Složka `assets/instructions` je součást
  nainstalovaného pluginu. Soubor přidaný tam se v combo boxu také objeví, ale při aktualizaci
  pluginu nebo nové distribuci zmizí. Dokumentace proto posílá uživatele do
  `custom-instructions`.
- **Název složky.** Řekl jsi „Custom Instructions“; zapisuji ho jako `custom-instructions`
  (malá písmena s pomlčkou, jako `test-cases`).
- **Seznam jazyků.** „Všechny světové jazyky“ beru jako ISO 639-1 (asi 180 jazyků s anglickými
  názvy). Úplnější seznamy mají přes 7 000 položek a pro combo box se nehodí.
- **Rozpoznání šablony při otevření** porovnává uložený text se všemi šablonami ve všech
  jazycích (stovky krátkých porovnání, neznatelné). Když se soubor šablony mezitím změní,
  dialog starý uložený text nepozná a otevře se na `Custom`; text zůstane, jak byl.
- **Délka instrukcí v každém výsledku.** `instructions` se vrací ve výsledku `wait`,
  `timeline` i `describe`. Šablona o 12 000 znacích tak agentovi přijde vícekrát. Funkčně to
  nevadí, stojí to tokeny. Zkrácení do tohoto plánu nezahrnuji.
- **Obsah cizího projektu.** Zdrojový plugin patří k zákaznickému projektu. Do Watch Me
  převezmu jen obecné principy, žádné texty specifikace, názvy obrazovek ani údaje.
- **Limit 20 000 znaků** platí i po ruční úpravě šablony uživatelem; delší text se při
  uložení ořízne (dnešní chování).
- **Předpoklad k jazyku v Test Case:** názvy souborů a složek, kód, komentáře a `run.log`
  jsou vždy anglicky; přepíná se jen jazyk dokumentů a zpráv uživateli.

## Otevřené otázky

Žádné. Dva předpoklady, které můžeš při schválení změnit: složka se jmenuje
`custom-instructions` a seznam jazyků je ISO 639-1.
