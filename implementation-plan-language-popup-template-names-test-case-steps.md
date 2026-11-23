# Plán: krátký seznam jazyků, jazyk v nadpisu šablon, „Immediately“ a „Test Case Step by Step“

Zdroj: nahrávka `20261123-012311` (celá, 0:00–3:49), master instrukce „Create Plan“ v češtině.
Druhá verze: zapracovává tvoje odpovědi z chatu (jazyk u Draft Intent a v Test Case je
rozhodnutý). Schváleno a implementováno 23. 11. 2026 s výchozím řešením A u obou zbylých
otázek. Odchylky od plánu:

- Odstavec o jazyce ve společném popisu test casu začíná „The language named in the goal
  applies to every document you write“ místo „The output language applies …“, protože nadpis
  už neříká „all outputs“.
- Řádky rozbaleného seznamu mají nastavenou výšku (text + 2 × 4 px), aby po přepnutí na seznam
  se scrollbarem zůstaly stejně vzdušné jako dřív.

## Cíl

Dialog **Instructions for the AI** (Watch Me Video Editor) se změní ve čtyřech věcech:

1. **Combo box Language** ukáže nejvýš 10 řádků a zbytek je pod scrollbarem (dnes se seznam
   roztáhne přes celou výšku obrazovky).
2. **Závorka s jazykem v nadpisu Goal** řekne, čeho se jazyk týká, místo obecného
   „all outputs will be written in …“: u Create Plan plán, u Draft Intent draft intent,
   u Test Case test a dokumentace.
3. **Přejmenování:** `Implement` → `Implement Immediately`, `Test Case` → `Test Case Immediately`.
4. **Nová šablona `Test Case Step by Step`** před `Test Case Immediately`: nejdřív plán testu,
   který schválíš, a teprve potom test case podle stejného popisu, jaký má dnešní Test Case.

Výsledné pořadí v combo boxu Action: `Custom`, `Draft Intent`, `Create Plan`,
`Implement Immediately`, `Test Case Step by Step`, `Test Case Immediately`.

## Jak jsem četl nahrávku

- 0:00–0:48 – rozbalený seznam Language (obdélník #2 přes celou výšku obrazovky): „obrovské
  množství políček … to se mi nelíbí … maximálně 10 položek a pak tam bude scrollbar“.
- 0:50–1:07 – Create Plan, šipka #3 na první řádek textu: místo „all outputs will be written in
  English“ má být „the plan will be written in English“.
- 1:09–1:22 – Draft Intent, šipka #4: „the draft will be written in English“.
- 1:22–1:45 – Test Case, šipka #5: „test a dokumentace budou napsány … v tom zvoleném jazyce,
  tyhle dva dokumenty primárně“.
- 1:45–2:24 – rozbalený seznam Action, šipka #6 na `Implement` („implement immediately“), šipka
  #7 na `Test Case` („test case immediately a před to dáme položku test case step by step“).
- 2:24–3:45 – popis Test Case Step by Step: mix plánu a test casu; plán obsahuje preconditions,
  akceptaci (jen co znamená, že test prošel), věci, které nejde plně automatizovat, a otevřené
  otázky s výchozím řešením od agenta.

Jak jsem si vyložil přepis: „moji pochu“ (1:45) beru jako „moji plochu“; „předto dáme“ jako „před
to dáme“, tedy nová položka je v seznamu **nad** Test Case Immediately. Mimo ořez jsem nečetl nic.

## Kroky

### 1. Combo box Language: nejvýš 10 řádků a scrollbar

- **Proč to dnes nefunguje:** aplikace běží ve stylu Fusion (`src/watch_me/editor/theme.py:121`).
  Ten otevírá seznam jako „popup“ přes celou obrazovku a vlastnost `maxVisibleItems` (výchozí
  hodnota je už 10) v tomto režimu ignoruje.
- **Co se změní:** `src/watch_me/editor/instructions_dialog.py`
  - nová konstanta `MAX_VISIBLE_ITEMS = 10`;
  - oběma combo boxům dialogu (`language_combo`, `template_combo`) se nastaví
    `setMaxVisibleItems(MAX_VISIBLE_ITEMS)` a styl `QComboBox { combobox-popup: 0; }`, který
    přepne seznam na klasický rozbalovací seznam pod polem se svislým scrollbarem.
- **Ověření:**
  - nový test v `tests/unit/test_editor_requests.py`: po `showPopup()` je výška seznamu
    (`language_combo.view()`) nejvýš 10 řádků a svislý scrollbar má `maximum() > 0`;
    `template_combo` s 6 položkami scrollbar nemá;
  - ručně: seznam Language má 10 řádků, kolečko myši i psaní písmene (skok na jazyk) fungují,
    vzhled pole se ve světlém i tmavém režimu nezměnil.
- **Záloha:** kdyby stylesheet změnil vzhled pole, použije se místo něj malý `QProxyStyle`,
  který pro `SH_ComboBox_Popup` vrací 0 (stejný výsledek, víc kódu).

### 2. Jazyk v nadpisu Goal

Soubory v `src/watch_me/editor/assets/instructions/`:

| Šablona | Dnes | Nově |
| --- | --- | --- |
| Draft Intent | `# Goal: a formal brief only (all outputs will be written in {language})` | `# Goal: a formal brief only (the draft intent will be written in {language})` |
| Create Plan | `# Goal: an implementation plan (all outputs will be written in {language})` | `# Goal: an implementation plan (the plan will be written in {language})` |
| Test Case Immediately | `# Goal: a test case (all outputs will be written in {language})` | `# Goal: a test case (the test and the documentation will be written in {language})` |

- U Draft Intent zůstává „a formal brief only“, mění se jen závorka s jazykem.
- V Test Case zůstává odstavec o jazyce (dnes řádky 11–13 souboru `40-test-case.md`), jak je:
  zvolený jazyk platí pro všechny dokumenty (`README.md`, `test.md`, `documentation.md`,
  `report.md`) i pro zprávy tobě; názvy souborů, kód, komentáře a `run.log` zůstávají anglicky.
  Nadpis jen jmenuje dva hlavní dokumenty.
- Implement Immediately se nemění: jazyk tam dál určuje jen výchozí jazyk uživatelského rozhraní.
- **Ověření:** testy prvních řádků (krok 6); v dialogu po přepnutí jazyka na Czech končí první
  řádek „(the plan will be written in Czech)“ a po zavření a otevření dialog šablonu i jazyk
  znovu pozná.

### 3. Přejmenování šablon

- `30-implement.md` → `30-implement-immediately.md`, `name: Implement Immediately`
  (text i tooltip beze změny).
- `40-test-case.md` → `50-test-case-immediately.md`, `name: Test Case Immediately`, tooltip
  `Turn the recording into a repeatable test case right away (scripts, steps for the AI, documentation)`.
- Bez zpětné kompatibility (pravidlo projektu): staré názvy souborů ani položek nezůstanou.
- **Ověření:** `git grep -n "Implement\b\|Test Case"` mimo staré plány nenajde staré názvy položek.

### 4. Společný popis test casu a vkládání do šablon

Obě šablony Test Case potřebují stejný popis (dnes asi 10 500 znaků). Aby nebyl ve dvou
souborech, navrhuji:

- **Nový soubor** `src/watch_me/editor/assets/instructions/parts/test-case.md`: všechno, co je
  dnes v `40-test-case.md` pod řádkem Goal (úvodní odstavec, odstavec o jazyce, Principles,
  oddíly 1–10). Podsložku `parts` čtení šablon nevidí (hledá `*.md` jen přímo ve složce), takže
  z ní nevznikne položka combo boxu.
- **`src/watch_me/editor/instruction_templates.py`:** řádek `{include:parts/test-case.md}` v textu
  šablony se při načtení nahradí obsahem toho souboru. Cesta je relativní ke složce šablony a
  nesmí z ní vést ven, vkládá se jen jedna úroveň (vložený soubor už nic nevkládá). Když soubor
  chybí nebo nejde přečíst, šablona se přeskočí s varováním v logu, stejně jako jiné vadné
  šablony. Limit `MAX_INSTRUCTIONS_CHARS` se počítá až po vložení. Funguje to i pro vlastní
  šablony v `custom-instructions`.
- `50-test-case-immediately.md` pak obsahuje jen hlavičku, řádek Goal a `{include:parts/test-case.md}`.
- **Ověření:** nové testy v `tests/unit/test_instruction_templates.py`: vložení textu, chybějící
  soubor (šablona přeskočena, varování v logu), cesta mimo složku odmítnuta, limit délky po
  vložení, soubor v `parts` není šablona. Vykreslený text Test Case Immediately se od dnešního
  liší jen řádkem Goal.

### 5. Nová šablona Test Case Step by Step

Nový soubor `src/watch_me/editor/assets/instructions/40-test-case-step-by-step.md`. Návrh textu:

```markdown
---
name: Test Case Step by Step
tooltip: Plan the test case first, wait for my approval, then create it
---
# Goal: a test case, step by step (the plan, the test and the documentation will be written in {language})

Process the recording (only its cropped range) in two steps: first a plan of the test
case, which I approve, and only then the test case itself.

## Step 1: the plan

Write the plan in the chat as Markdown. Do not create or change any file yet.

- **What the test proves:** one or two sentences.
- **What will be tested:** the steps in order, each with its expected result and the time
  stamp it comes from.
- **Preconditions:** the tests that must have passed before, the state the system must be
  in and what the environment needs.
- **Acceptance:** what it means that the test passed.
- **Not fully automated:** the steps a script cannot do reliably, who does them (the AI
  agent or me) and why. Leave this out when there are none.
- **Open questions:** everything that changes what you build. Give every question a
  default: what you will do when I do not answer it.

Then wait for my approval. I may answer the open questions or leave them; use your
defaults for those I leave unanswered.

## Step 2: the test case

After my approval, create the test case exactly as described below, with my answers
and the defaults of the plan.

{include:parts/test-case.md}
```

- Co plán záměrně neobsahuje: co znamená, že test neprošel (řekl jsi, že stačí jen „prošel“).
- Celý text vyjde asi na 12 000 znaků, pod limitem 20 000.
- **Ověření:** šablona je v combo boxu čtvrtá za Custom, první řádek odpovídá, text obsahuje
  oddíly „Step 1: the plan“ a „Step 2: the test case“ a celý společný popis; délka v nejdelším
  jazyce je pod `MAX_INSTRUCTIONS_CHARS`; `normalize_instructions(text) == text.strip()`.

### 6. Testy

- `tests/unit/test_instruction_templates.py`: `BUILT_IN_FILES` (pět souborů), test „exactly the
  four templates“ → pět, nové názvy a nové první řádky, vykreslení v češtině.
- `tests/unit/test_editor_requests.py`: konstanty `IMPLEMENT` a `TEST_CASE` s novými názvy, nová
  `TEST_CASE_STEP_BY_STEP`, seznamy položek combo boxu, kontroly prvních řádků (dnes řádky 268,
  299, 311–312), nový test seznamu Language z kroku 1, test, že dialog pozná Test Case Step by
  Step v češtině po uložení a novém otevření.
- **Ověření:** celá sada testů projde (`pytest`), stejně tak lint a kontrola typů, které
  projekt používá.

### 7. Dokumentace

- `skills/watch-me-video-editor/SKILL.md` (řádky 110–115): názvy šablon, nová šablona, věta
  o jazyce (plán / draft / test a dokumentace).
- `README.md` (řádek 71) a `watch-me-spec.md` (řádek 173): výčet šablon, popis `{include:…}`
  u vlastních šablon, seznam Language s 10 řádky.
- Docstringy: `instruction_templates.py` (příklad hlavičky, `{include:…}`),
  `instructions_dialog.py`, `core/languages.py` (příklad „all outputs will be written in Czech“).
- Staré soubory `implementation-plan-*.md` zůstanou, jak jsou (historie).
- **Ověření:** `git grep -n "all outputs will be written"` najde jen staré plány.

## Rizika

- **Stylesheet na combo boxu** může ve stylu Fusion nepatrně změnit vzhled pole nebo seznamu
  (hlavně v tmavém režimu). Ověřím ručně v obou režimech; záloha je `QProxyStyle` (krok 1).
- **Test výšky seznamu** běží bez skutečné obrazovky (offscreen); kdyby tam `showPopup()` nedal
  spolehlivou geometrii, test ověří jen `maxVisibleItems()` a styl a výšku ověřím ručně.
- **Vkládání souborů** je nová vlastnost čtení šablon, tedy i nové chybové stavy; proto jen jedna
  úroveň a jen uvnitř složky šablony.
- **Podsložka `parts` v distribuci:** `pyproject.toml` nemá výslovný seznam datových souborů;
  ověřím, že se `parts/test-case.md` dostane do sestavené distribuce stejně jako dnešní šablony.
- **Uložené instrukce starších nahrávek** se starým řádkem Goal dialog otevře jako `Custom`
  (text zůstane beze změny). Podle pravidla projektu se to neřeší.

## Předpoklady

- Limit 10 řádků dostane i combo box Action (dnes má 6 položek, ale vlastní šablony ho mohou
  prodloužit).
- Oddělovač pod English a Czech se počítá jako jeden z 10 řádků; vidět je tedy English, Czech,
  oddělovač a 7 dalších jazyků.
- Názvy položek píšu jako ostatní: `Implement Immediately`, `Test Case Step by Step`,
  `Test Case Immediately`.
- Text šablony Test Case Immediately se kromě řádku Goal nemění (viz otevřená otázka 2).
- Plán v Test Case Step by Step se píše do chatu, ne do souboru (stejně jako u Create Plan).
- Nová distribuce ani zvýšení verze nejsou součástí tohoto plánu.

## Rozhodnuto (tvoje odpovědi)

- **Draft Intent:** nadpis zůstává „a formal brief only“, závorka zní
  `(the draft intent will be written in {language})`.
- **Jazyk v Test Case:** `README.md`, `report.md` i zprávy agenta jsou ve zvoleném jazyce.

## Otevřené otázky

1. **Kde bude popis test casu, který potřebují obě šablony Test Case?** Obě šablony (Step by
   Step i Immediately) musí agentovi poslat stejný dlouhý popis: složka `test-cases`, pravidla
   skriptů, `test.md`, dokumentace, logy, běh testu (dnes asi 10 500 znaků).
   - **Varianta A, popis v jednom souboru (krok 4):** popis leží jednou v `parts/test-case.md`
     a obě šablony na něj odkazují řádkem `{include:parts/test-case.md}`. Editor při načtení
     ten řádek nahradí obsahem souboru, takže ty i agent vidíte v dialogu celý text jako dnes.
     Úprava popisu se dělá na jednom místě. Cena: asi 30 řádků nového kódu ve čtení šablon
     a jeho testy.
   - **Varianta B, popis ve dvou kopiích:** celý popis je v obou souborech šablon. Žádný nový
     kód, ale každou úpravu popisu je nutné udělat dvakrát; test hlídá, že jsou kopie stejné,
     a spadne, když se rozejdou.
   - Výchozí řešení: varianta A.
2. **Má se Test Case Immediately dál ptát?** Dnešní Test Case:
   - **ptá se jen na to, co mění, co se staví** (oddíl 9, bod 1: „Ask me about anything that
     changes what you build, with the time stamp“), a ve třech určených případech: když
     nepozná kořen projektu, když projekt nemá kam uložit URL a přihlašovací údaje, a než přidá
     krok, který mění data a který jsi neukázal;
   - **preconditions a akceptaci předem neshrne** a **nečeká na schválení**: po případných
     otázkách rovnou napíše `test.md`, skripty a dokumentaci a udělá zelený běh. Preconditions
     jsou až v `test.md` a v dokumentaci, akceptace jen jako očekávaný výsledek u každého kroku;
   - **shrnutí dá až na konci:** co test pokrývá, které kroky dělá agent nebo ty a proč, co
     test mění v systému, co agent předpokládal. Očekávaný výsledek, který si odvodil, označí
     `(assumed, verify)`.

   Možnosti pro Test Case Immediately:
   - **A:** text nechat, jak je (ptá se jen na to, co mění, co se staví).
   - **B:** jako Implement Immediately: neptá se, pokud není opravdu zablokovaný, rozhoduje sám
     a předpoklady vypíše na konci; tři určené případy výše zůstanou (jde o data a přihlašovací
     údaje). Věta o otázkách se pak přesune ze společného popisu do jednotlivých šablon.
   - Výchozí řešení: A.
