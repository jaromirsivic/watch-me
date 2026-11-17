# Implementační plán: špatně rozpoznaná slova a změna názoru během nahrávky

Datum: 17. 11. 2026. Verze plánu: 1. Stav: **M1–M5 implementovány 17. 11. 2026** včetně doplňků A1–A5 (uživatel je schválil), verze zvednuta na 0.5.1. `watch-me-spec.md` pravidla čtení neobsahuje, proto se neměnil. Zbývá: ruční zkoušky z oddílu 5.

Kontext: kontrola skillu `watch-me-recorder` ze 17. 11. 2026 ukázala dvě mezery v tom, jak má agent po stisku **Process** číst nahrávku.

| # | Zjištění | Rozhodnutí uživatele ze 17. 11. 2026 |
|---|---|---|
| 1 | O chybách přepisu mluví skill jen obecně v oddílu Limits (jména, čísla, interpunkce). Neříká, že špatně mohou být celá slova, ani co s tím. Dotaz na uživatele váže jen na snímky a na rozpor řeči s obrazem. | Doplnit: přepis může některá slova rozpoznat špatně. Když jde smysl pochopit z kontextu (okolní věty, klikání myší, kreslení, případně obrázek), **není nutné se ptát**. Když to jednoznačně pochopit nejde, vznikají nesrovnalosti nebo nekonzistence, nebo v přepisu zaznělo něco, co nedává smysl, **je lepší se zeptat**. |
| 2 | Skill nikde neříká, že uživatel může během nahrávky změnit názor. Oddíl 5 naopak velí plnit požadavky „in order“, takže agent může provést i krok, který uživatel později odvolal. | Doplnit do kroku 3 a oddílu 5: uživatel může názor v oříznutém úseku změnit i několikrát. Příklad: popíše kroky A, B a C, pak řekne, že A chce jinak a B tím pádem není potřeba. Platí nový krok A, krok B se neprovádí a krok C se provede tak, jak ho uživatel původně popsal. |
| 3 | Agent připojený přes MCP `SKILL.md` nečte; skill editoru zpracování popisuje zkráceně. | Stejné znění do pokynů MCP a zmínka do skillu `watch-me-video-editor`. |

## 1. Výsledek a hranice

Po změně:

- Agent počítá s tím, že slovo nebo věta v řádku `SAY` může být rozpoznaná špatně, a smysl si nejdřív dovodí z kontextu. Ptá se až tehdy, když kontext nestačí.
- Agent si před prací sestaví konečnou podobu požadavků: pozdější vyjádření nahrazuje dřívější, co pozdější vyjádření nezmínilo, zůstává, jak bylo řečeno.
- Totéž se dozví agent připojený přes MCP.

Beze změny zůstává (záměrně):

| Co | Proč |
|---|---|
| Kód (`build_timeline`, `frames_at`, nástroje MCP), výstup příkazů | Jde jen o to, jak agent text čte. Časová osa obsahuje vše potřebné už dnes. |
| Pravidlo ořezu a druhé kolo snímků (`implementation-plan-skill-crop-second-look.md`) | Nová pravidla na ně navazují, nemění je. |
| Váha instrukcí z editoru | Instrukce dál vítězí nad řečí; uživatel je píše až po nahrávce. |
| Výjimka „unless the instructions say not to ask“ | Schválena 17. 11. 2026 jako D4 plánu ořezu. Platí i pro nové důvody k dotazu. |
| `references/agent-startup.md` | Týká se startu. Musí zůstat stejný v obou skillech. |

## 2. Rozhodnutí

Schválená uživatelem (viz tabulka výše): R1 kontext má přednost před dotazem, R2 poslední vyjádření platí a nedotčené kroky zůstávají, R3 stejné znění do MCP a zmínka do skillu editoru.

Doplňky autora plánu, které uživatel výslovně neřekl. Když s některým nesouhlasíte, příslušná věta z textu vypadne:

- **A1 – agent řekne, jak slovo přečetl.** Dnes skill velí „do not translate or clean it up silently“. Aby to s R1 nebylo v rozporu: agent se neptá, ale když jeho výklad špatně rozpoznaného slova ovlivnil, co udělal, zmíní ho v odpovědi jednou větou.
- **A2 – agent řekne, co kvůli změně názoru vynechal.** Jedna věta v odpovědi („krok B jsem neprovedl, v čase 3:12 jste ho zrušil“), aby uživatel viděl, že vynechání bylo záměrné.
- **A3 – nejasná změna názoru je důvod k dotazu.** Když není zřejmé, jestli pozdější věta dřívější krok ruší, nebo ho jen doplňuje, postupuje agent podle R1: nejdřív kontext, potom dotaz.
- **A4 – změna názoru vyslovená mimo ořez neplatí.** Plyne z pravidla ořezu: co je mimo ořez, uživatel odstřihl záměrně. Text to řekne jednou vedlejší větou.
- **A5 – verze 0.5.1.** Hostitel s kopií pluginu převezme změněný skill až s novou verzí.

## 3. Kroky

### M1 – `skills/watch-me-recorder/SKILL.md`

**a) Špatně rozpoznaná slova.** V kroku 2 rozšířit odrážku `SAY` (ř. 193–196). První dvě věty zůstávají, za ně přijde nový text; věta o „Here“, „this“ a „that“ zůstává na konci.

```text
- `SAY` is a transcript segment with the cursor screen and position at its start and
  end. The text keeps the spoken language; do not translate or clean it up silently,
  quote it when you need to confirm what was said. The transcript is made by a
  speech-to-text model and can get words wrong: a word that sounds alike, a name, a
  number, a term from another language, now and then a whole sentence that makes no
  sense. Work out what was meant from the context: the sentences around it, the
  instructions, what the user clicked, drew or pointed at around that time, a copied
  text, and a frame when the text is not enough. When the context makes it clear, go by
  it without asking the user, and say in your answer how you read a word if it changed
  what you did. Ask only when the context does not settle it: the meaning stays
  ambiguous, parts of the recording contradict each other, or something that was said
  makes no sense - then ask, quoting the words and the time stamp (unless the
  instructions say not to ask). "Here", "this" and "that" usually mean the cursor
  position or a shape drawn around that time.
```

**b) Změna názoru.** V kroku 3 (ř. 313–318) vložit za první větu nový odstavec; zbytek kroku se nemění.

```text
**Step 3 - pick the moments that need a picture.** Read the whole timeline once, work
out what the user asks for and list the requests in order.

The user may change their mind while recording, more than once: the later statement
replaces the earlier one. Settle what the user wants in the end before you list the
requests. For example, the user describes steps A, B and C and then says that A should
be done differently and that B is therefore not needed: do the new A, leave B out and
do C as it was first described. What a later statement does not touch stays as it was
said. Only statements inside the crop count. When it is not clear whether a later
sentence replaces an earlier request or only adds to it, treat it like a misheard word:
context first, then ask. Say in your answer which request you left out or changed
because of it.

For each request that remains, decide whether the text already answers it: ...
```

Důsledek pro snímky: pro zrušený krok agent žádný snímek nebere, protože seznam požadavků vzniká až po vyhodnocení změn.

**c) Oddíl `## 5. Act`** (ř. 383–389). Dvě věty se změní:

```text
Apply the `instructions` to the whole task, then carry out the requests that remain
after the user's changes of mind (step 3), in order, combining the words with the
shapes, cursor positions and the few frames you fetched. When speech and image still
disagree, words make no sense and the context does not settle them, or something stays
unclear after you looked again, ask, citing the time stamp - unless the instructions
say not to ask.
```

Zbytek oddílu (instrukce vítězí nad řečí, jazyk, nedotýkat se složky nahrávky) zůstává.

**d) Oddíl `## Limits`** (ř. 433–435). Za „expect mistakes in names, numbers and punctuation“ doplnit „and now and then in whole words (see `SAY` in section 4)“.

**e) Délka.** `SKILL.md` má 435 řádků, přibude asi 22. Zůstane pod 500 řádky.

### M2 – `skills/watch-me-video-editor/SKILL.md`

Krok 3 oddílu 2 (ř. 69–83) odkazuje na oddíl 4 skillu `watch-me-recorder`. Za větu o druhém kole (ř. 83) doplnit jednu větu:

```text
The rules of that section for misheard words (context first, then ask) and for a user
who changes their mind (the later statement replaces the earlier one) apply here too.
```

Pravidla se neopisují celá, aby se oba skilly nerozešly.

### M3 – MCP (`src/watch_me/host/mcp_server.py`)

Do `INSTRUCTIONS` (ř. 89–131) vložit za větu „Look outside only when … and say that you did.“ (ř. 102):

```text
The transcript can get words wrong: work out what was meant from the context (the
sentences around it, the clicks, the drawings, a frame) and go by it without asking;
ask only when the context does not settle it or something that was said makes no
sense. The user may change their mind while recording: the later statement replaces
the earlier one, and what it does not touch stays as it was said (steps A, B, C, then
"do A differently, B is not needed": the new A, no B, C as first described).
```

Výjimku „unless the instructions say not to ask“ už `INSTRUCTIONS` obsahují o pár vět dál; platí pro každý dotaz, neopakuje se.

Popisy jednotlivých nástrojů se nemění.

### M4 – testy

Rozšířit `test_skills_and_mcp_instructions_carry_the_same_reading_rules` v `tests/unit/test_host_packaging.py` o pevné úseky, které musí být ve skillu i v `INSTRUCTIONS`:

- `can get words wrong`
- `the context does not settle it`
- `the later statement replaces the earlier one`

a ve skillu editoru: `misheard words` a `changes their mind`.

Spustit celé `tests/unit` (frontmatter, délka a odkazy skillů, shodný `agent-startup.md`).

### M5 – dokumentace a verze

- `README.md`: k větě o ořezu a druhém kole doplnit jednu větu o obou pravidlech.
- `watch-me-spec.md`: projít zmínky o zpracování po Process a doplnit, jen pokud tam pravidla čtení jsou.
- Verze 0.5.1 na šesti místech (`plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml`, `src/watch_me/__init__.py`, `uv.lock` přes `uv lock`), viz A5.

## 4. Pořadí a rozdělení práce

1. M1 a M2 (texty skillů) a M4 (test) – jeden commit, test hlídá právě tyto texty.
2. M3 (MCP) – ve stejném commitu, jinak by test shody mezi commity neprocházel.
3. M5 – dokumentace v témže commitu, verze samostatně.

Všechno jsou formulace, na kterých záleží chování agenta: psát v hlavní relaci, subagentovi nepředávat.

## 5. Ověření

- `tests/unit` projdou, `ruff check` čistý.
- Ruční zkouška na nahrávce, kde uživatel (a) řekne slovo, které přepis zkomolí, ale z kliknutí je zřejmé, co myslel: agent se neptá a v odpovědi uvede, jak slovo přečetl; (b) řekne větu, která nedává smysl a kontext ji nevyjasní: agent se zeptá s citací a časem; (c) popíše kroky A, B, C a pak A změní a B zruší: agent provede nové A a původní C, B vynechá a řekne to; (d) totéž s instrukcí „neptej se“: agent se nezeptá a uvede, co předpokládal.
- Stejná nahrávka přes MCP.

## 6. Rizika

| Riziko | Ošetření |
|---|---|
| Agent si „z kontextu“ domyslí víc, než zaznělo, a provede něco, co uživatel nechtěl. | Dotaz je povinný při nejednoznačnosti, rozporu nebo nesmyslu; A1 ukáže uživateli, jak agent slovo přečetl. |
| Agent se začne ptát na každé zkomolené slovo. | Text říká výslovně „go by it without asking“ a dotaz podmiňuje tím, že kontext nestačí. |
| Agent vezme za změnu názoru větu, která krok jen doplňuje, a původní krok zahodí. | A3: nejasný případ je důvod k dotazu; A2 ukáže, co agent vynechal. |
| Oprava vyslovená mimo ořez se neuplatní a uživatel to nečeká. | A4 to říká výslovně; vychází z pravidla ořezu, které uživatel schválil. Kdyby to vadilo, řešením je posunout ořez, ne měnit pravidlo. |
| Skill a pokyny MCP se rozejdou. | Test z M4. |
