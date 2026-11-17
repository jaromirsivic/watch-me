# Implementační plán: držet se ořezu a druhé kolo snímků

Datum: 17. 11. 2026. Verze plánu: 3. Stav: **K1–K5 a README implementovány 17. 11. 2026 (commit `d92eeeb`)**. Verze zvednuta na 0.4.0 (čtyři manifesty, `src/watch_me/__init__.py` a `uv.lock`; commit `eda75f5`). Zbývá: ruční zkoušky z oddílu 5.

Kontext: kontrola toho, jak agent po stisku **Process** zpracovává nahrávku, ukázala odchylky od záměru. Rozhodnutí uživatele ze 17. 11. 2026 k bodům, kterých se plán týká:

| # | Zjištění | Rozhodnutí |
|---|---|---|
| 1 | Ořez je jen výchozí rozsah, agent se za něj dostane (`timeline --all`, `transcript.txt`, `frames --at`). | Technicky nechat. Skill a plugin musí říkat, že se agent **primárně drží ořezané oblasti**. |
| 2 | Řeč, kreslení a kliky jsou v jedné časové ose, ne ve dvou prioritách. | Nechat. |
| 3 | Nedělá se výtah, časová osa je vždy celá. | Nechat. |
| 4 | Skill popisuje jeden průchod snímky, další kolo nezmiňuje. | Doplnit do skillu **druhé kolo**: kdykoli agent usoudí, že potřebuje další informace, smí si vzít další snímky (například když obrazec něco překrývá: snímek z doby před kreslením). |

## 1. Výsledek a hranice

Po změně:

- Agent ví, že ořez vymezuje, s čím má pracovat. Mimo ořez sahá jen výjimečně, z daného důvodu, a v odpovědi to řekne.
- Agent ví, že když snímky z prvního kola nestačí, smí si podle vlastního úsudku vzít další a projít materiál znovu. Když nestačí ani ty, zeptá se uživatele, pokud to instrukce nezakazují.
- Totéž se dozví agent připojený přes MCP, který `SKILL.md` nečte.

Beze změny zůstává (záměrně):

| Co | Proč |
|---|---|
| `build_timeline`, pořadí a obsah řádků časové osy | Body 2 a 3 jsou v pořádku. |
| Přepínače `--all`, `--start-ms`, `--end-ms`, cesta `transcript_txt` ve výsledku | Bod 1: ořez nemá být bariéra. |
| Limity jednoho volání (`--window` 24 snímků, 20 000 znaků, 12 000 znaků inline) | Počet kol se neomezuje kódem, jen textem skillu. |
| `references/agent-startup.md` | Týká se startu, ne zpracování. Musí zůstat bajt po bajtu stejný v obou skillech (`test_recovery_guide_is_the_same_file_in_both_skills`). |

Souvislost: plán `implementation-plan-rename-display-recorder.md` přejmenovává `skills/watch-me` na `skills/watch-me-display-recorder`. Když se provede dřív, platí kroky níže pro novou cestu; obsah změn je stejný.

## 2. Rozhodnutí (schválena uživatelem 17. 11. 2026)

- **D1 – kdy smí agent za ořez.** Jen když (a) to výslovně žádají instrukce nebo uživatel v řeči, nebo (b) něco uvnitř ořezu nejde bez toho pochopit (věta začíná před ořezem, obrazec byl nakreslen před ním). Požadavky vyslovené mimo ořez agent **nikdy neplní**. Když za ořez sáhne, řekne to.
- **D2 – upozornění přímo ve výstupu příkazů (krok K4).** Ano. Text ve skillu agent po dlouhé práci snadno pustí z hlavy; poznámka ve výsledku `timeline` a `frames` mu to připomene ve chvíli, kdy ořez opouští.
- **D3 – strop na počet kol.** Žádný limit, ani v kódu, ani v textu. O dalším kole rozhoduje agent sám, kdykoli usoudí, že potřebuje další informace.
- **D4 – dotaz na uživatele.** Když nestačí ani další snímky, agent se zeptá. Výjimka: instrukce říkají, že se ptát nemá. Instrukce mají nejvyšší váhu, agent pak jedná podle nejlepšího výkladu a řekne, co předpokládal (poslední část je doplněk autora plánu, uživatel ji výslovně neřekl).

## 3. Kroky

### K1 – `skills/watch-me/SKILL.md`

**a) Pravidlo ořezu.** V kroku 2 (ř. 143–145, odstavec začínající „`crop` is the part of the recording…“) nahradit první větu a přidat pravidlo:

```text
`crop` is the part of the recording the user wants you to act on (the whole recording
unless they cropped it in the editor). Stay inside it: read the speech, the events and
the frames of that range only, and carry out only what is said there. What lies outside
the crop was cut away on purpose - never act on a request spoken there. Look outside
only when the instructions or the speech ask for it, or when something inside the crop
cannot be understood without it (a sentence that begins before the crop, a shape drawn
before it), and say in your answer that you did. `timeline` covers exactly the crop
(`--start-ms`/`--end-ms` or `--all` change it; see the rule above before you use them).
```

**b) Místa, kde agent ořez opouští, aniž si toho všimne.** Ke každému jedna vedlejší věta:

- ř. 311–333 (krok 4, `frames`): „`--at` takes any time of the recording; keep it inside `crop`.“
- ř. 355 („The whole transcript is the file `transcript_txt`.“): doplnit „It also holds what was said outside the crop; the timeline is the transcript of the crop.“
- ř. 298–302 (`mouse` bez `--at`): rozsah je ořez; beze změny chování, jen zmínka „of the crop“.

**c) Nový krok 5 – druhé kolo.** Vložit za odrážky kroku 4 (za ř. 333), před odstavec „Frames are named…“:

```text
**Step 5 - look again when you need to.** If the frames of the first round are not
enough, fetch more and go through the material again - a second round. This is your
call: whenever you find that you need more information to understand what the user
means, take it. For example, a drawn shape may cover what you need to read (take the
`before` time of its `DRAW` line: the screen before the drawing), or a frame may show
the moment just before a menu opened (take a later one).

If the frames still do not settle it, ask the user, citing the time stamp - unless the
instructions say not to ask: they carry the most weight, so then go by your best
reading and say what you assumed.
```

Záměr textu (podle zadání uživatele ze 17. 11. 2026): druhé kolo je obecné oprávnění, o kterém rozhoduje agent sám. Příklady jsou jen příklady, ne výčet povolených případů. Počet kol text nepočítá ani neomezuje.

Dnešní věta v kroku 4 „add the `before` time only when the shape hides what you need to see“ zůstává; krok 5 na ni navazuje.

**d) Oddíl `## 5. Act`.** Číslo se nemění (je to oddíl, ne krok). Jeho věta „When speech and image disagree or something is unclear, ask, citing the time stamp.“ se změní na „When speech and image still disagree or something stays unclear after you looked again, ask, citing the time stamp - unless the instructions say not to ask.“

**e) Délka.** `SKILL.md` má 411 řádků; přibude asi 20. Zůstat pod 500 řádky (doporučení Agent Skills).

### K2 – `skills/watch-me-editor/SKILL.md`

Krok 3 oddílu 2 (ř. 66–78) popisuje totéž zpracování zkráceně a odkazuje na „section 4 of the watch-me skill“. Doplnit dvě věty:

- za „(the cropped range as one text timeline: …)“: „Stay inside that range: what lies outside the crop was cut away on purpose.“
- za „(for a shape the `after` time of its `DRAW` line)“: „When these frames are not enough, fetch more and look again as step 5 of that section describes (for example the `before` time of a shape that covers what you need to read).“

Pravidla se neopisují celá, aby se oba skilly nerozešly.

### K3 – MCP (`src/watch_me/host/mcp_server.py`)

Hostitel bez shellu čte jen `INSTRUCTIONS` (ř. 88–121) a popisy nástrojů.

- `INSTRUCTIONS`: za větu o `watch_me_timeline` přidat pravidlo ořezu jednou větou; za větu o `watch_me_get_frame` přidat druhé kolo jednou až dvěma větami: když snímky nestačí, smí si agent vzít další (například snímek před obrazcem, který něco zakrývá); když nestačí ani ty, zeptá se uživatele, pokud to instrukce nezakazují.
- Popis `watch_me_timeline` (ř. 753): k `start_ms`/`end_ms` „only when the crop is not enough“.
- Popis `watch_me_get_transcript` (ř. 731): „the whole recording, also outside the crop; prefer watch_me_timeline“.
- Popis `watch_me_get_frame` (ř. 806): „keep at_ms inside the crop“.

`tests/unit/test_mcp_server.py:525` kontroluje jen, že instrukce jmenují `watch_me_wait`; změna ho nerozbije.

### K4 – upozornění ve výstupu příkazů (D2)

- `build_timeline` (`src/watch_me/host/events.py:776–781`): když `window` přesahuje `crop`, přidat do výsledku `range_note`: „The range leaves the user's crop (<start>-<end>): what lies outside was cut away on purpose; do not act on requests spoken there.“ Platí pro CLI i MCP, obě cesty volají tuto funkci.
- `frames_at` (`src/watch_me/host/runner.py:620`): načíst ořez (`read_crop`) a když `at_ms` leží mimo, přidat `outside_crop: true` a `crop`. Uvnitř ořezu se výsledek nemění.
- `cmd_timeline`, `cmd_mouse` (`src/watch_me/host/cli.py:1050`, `1072`): nápověda `--all` „the whole recording, ignoring the crop (only when the crop is not enough)“.

Výstup uvnitř ořezu zůstává bajt po bajtu stejný, takže existující testy časové osy a snímků se nemění.

### K5 – testy

- Nové (ke K4), do `tests/unit/test_cli_agent_files.py` nebo vedle testů `build_timeline`:
  - `timeline` bez přepínačů nemá `range_note`; s `--all` u oříznuté nahrávky ho má; u neoříznuté nahrávky ho `--all` nemá.
  - `frames --at` uvnitř ořezu nemá `outside_crop`; mimo ořez má `outside_crop: true`.
- Nový malý test do `tests/unit/test_host_packaging.py`: `skills/watch-me/SKILL.md` i MCP `INSTRUCTIONS` obsahují pravidlo ořezu a druhé kolo (hledat krátké pevné úseky, například `Stay inside` a `before`), aby se oba kanály nerozešly.
- Spustit celé `tests/unit` (zejména `test_host_packaging.py`: frontmatter, odkazy uvnitř složky skillu, shodný `agent-startup.md`).

### K6 – dokumentace a doručení

- `README.md` ř. 97 (odstavec „Agents use `run --detach`…“): doplnit jednu větu o ořezu a jednu o druhém kole.
- Hostitel může mít `SKILL.md` v mezipaměti: po změně začít nový chat; u instalace jako plugin zvednout verzi ve všech čtyřech místech najednou (`plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml`; `test_names_versions_and_descriptions_agree` hlídá shodu).

## 4. Pořadí a rozdělení práce

1. K1 a K2 (text skillů) – drží se spolu, jeden commit.
2. K3 (MCP texty) – samostatný commit.
3. K4 a K5 (kód a testy) – samostatný commit.
4. K6.

K1–K3 jsou formulace, na kterých záleží chování agenta: psát v hlavní relaci. K4 a K5 jsou přesně zadané a kryté testy: lze předat subagentovi a diff zkontrolovat.

## 5. Ověření

- `tests/unit` projdou.
- Ruční zkouška na oříznuté nahrávce s obrazcem přes text: agent po Process (a) nevolá `timeline --all` ani nečte `transcript.txt`, (b) po prvním snímku si sám vezme snímek `before` a přečte zakrytý text, (c) na požadavek vyslovený mimo ořez nereaguje, (d) s instrukcí „neptej se“ se při nejasnosti nezeptá a v odpovědi uvede, co předpokládal.
- Zkouška přes MCP se stejnou nahrávkou.

## 6. Rizika

| Riziko | Ošetření |
|---|---|
| Agent začne dělat druhé kolo vždy a utratí víc za snímky. | Text druhé kolo podmiňuje („If the frames of the first round are not enough“) a krok 3 skillu dál vede k šetření. Zbytek je záměrně na úsudku agenta. |
| Pravidlo ořezu je moc přísné a agent nepochopí větu useknutou hranicí. | Výjimka (b) v D1; titulek přesahující hranici ořezu časová osa už dnes předává celý. |
| Skill a MCP instrukce se časem rozejdou. | Test z K5. |
