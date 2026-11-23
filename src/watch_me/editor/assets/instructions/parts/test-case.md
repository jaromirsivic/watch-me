Process the recording (only its cropped range) and turn what I do, show and say into a
repeatable test case in the `test-cases` folder of my project. What I click and type are
the steps; what I say should happen are the expected results.

The language named in the goal applies to every document you write (`README.md`, `test.md`,
`documentation.md`, `report.md`) and to your messages to me. File and folder names, the
code of the scripts, comments in the code and the lines of `run.log` are always English.

## Principles

- **What can be programmed is programmed.** Every part of the test that a script can do
  reliably is a script, so it runs the same way every time. An AI agent does only what a
  script cannot do (visual judgement, interpreting free text) and a person only what needs
  a person (entering credentials). "It was easier to describe than to code" is no reason.
- A test is started by telling an agent to run it, or by its start script when no step
  needs an agent.
- When a script breaks, the agent does that one part by hand and the next script continues.
  When the agent cannot do it either, it asks me. When nobody can, the test stops.
- The product decides. Never change or soften an expected result to make a step pass.

## 1. The `test-cases` folder

`test-cases` lives directly in the root of the project (the root of the repository or
folder you work in), next to its other top-level folders - never inside another folder
such as `tests/`, also when other conventions of the project put test work elsewhere.
Look for it there. When it exists, read its `README.md` and what is already there before
you add anything. When it does not exist, create it and tell me that you created it, what
is in it and its absolute path. When you cannot tell which folder is the project root, ask
me before you create anything.

```text
test-cases/
  README.md                        the structure, how to run a test, the list of tests
  .venv/                           the Python of the tests (not committed), see section 2
  scripts/                         the executable parts of all tests
  tests/<test>/test.md             the steps of one test, for the AI agent
  docs/<test>/documentation.md     the same test described for people
  logs/<test>/<YYYY-MM-DD-HH-MM-SS>/run.log, report.md     one folder per run
```

`<test>` is a lowercase, hyphenated name that says what is tested (`order-create-and-cancel`,
not `test1`); the same name is used in `tests`, `docs` and `logs`. Keep `README.md` up to
date: what each folder holds, how to install what the scripts need, how to run a test,
and one line per test with its prerequisites.

## 2. `scripts/` - the deterministic parts

- One script is one part of a test. Its name says what it does (`log_in.py`,
  `create_order.py`), never `test1_part1`.
- The scripts are shared by all tests. Before you write one, check whether an existing
  script already does the job: use it, or extend it with a parameter. Before you change
  one, find the tests that use it.
- Write the scripts in Python, because it runs on Windows, macOS and Linux: Playwright
  for the browser, plain Python for REST calls, files and databases. Declare what they
  need in one file in `scripts/`.
- Everything Python of the tests lives in `test-cases/.venv`: the one virtual environment
  of all scripts, built from that file, and - when Python itself has to be installed (for
  example with uv) - that installation too, inside `.venv`. Never install into the system
  or another folder, and never commit `.venv`. The launchers create or update `.venv` when
  it is missing or the file changed and run every script with its Python; `README.md` says
  how.
- Write first for the system I recorded on, and keep the scripts cross-platform wherever
  possible (no fixed path separators, no tools of one system only). `.bat` and `.sh` files
  are thin launchers. When something cannot be cross-platform, my system has priority and
  `README.md` says what is missing for the others.
- A test whose steps are all scripts gets a start script (`start-<test>.bat` and `.sh`)
  that creates the run folder, runs the parts in order and stops at the first exit code
  that is not 0.
- Every script takes `--run-dir <folder>`, appends what it does to `run.log` there and
  ends with one of these exit codes and a last line saying the same:

  | Code | Last line | Meaning |
  | --- | --- | --- |
  | 0 | `PASSED: ...` | The expected results of this part hold. |
  | 1 | `FAILED: ...` | The product behaves wrong. |
  | 2 | `BLOCKED: ...` | The environment prevents the test (no network, not logged in). |
  | 3 | `BROKEN: ...` | The automation failed: element not found, timeout, any unexpected error. |

- Values a later part needs (ids of created objects, chosen values) go to `context.json`
  in the run folder. A part starts from the state the previous part left and reads what it
  needs from `context.json`, because an agent may have done the previous part by hand.
- Code that a second script needs too (log, exit codes, `context.json`, configuration)
  moves to one helper module in `scripts/`.
- Never write URLs, logins or passwords into a script. Read them from the configuration
  of the project or from environment variables; when the project has none, ask me where
  they should live. Never print or log credentials or tokens.

## 3. `tests/<test>/test.md` - the steps, for the AI agent

- One sentence saying what the test proves.
- **Prerequisites:** tests that must have passed before, the state they leave, and what
  the environment needs (network, a logged-in user).
- **Test data:** what the test uses, creates, changes and deletes, and the keys it writes
  to `context.json`.
- **Steps:** a table `# | Action | Expected result | Done by`. "Done by" is the script that
  does the step, or `ai - <reason>`, or `user - <reason>`.
- **Cleanup:** how the test undoes its changes, or "none".

Write every step so that a person can do it from the text alone: name elements by their
visible label, heading or column, never by selectors or coordinates. That text is what an
agent follows when it takes a part over. Expected results come from what I said and
showed; mark one you inferred with `(assumed, verify)` and tell me.

## 4. `docs/<test>/documentation.md` - for people

For me and for my customer. No instructions for an agent and no internals of the scripts:
what the test is about and why it exists, prerequisites and preconditions, what it does
step by step in plain words, what it verifies, and what it changes in the system.

## 5. `logs/<test>/<YYYY-MM-DD-HH-MM-SS>/` - one run

Whoever starts the test (the agent or the start script) creates the folder, named by the
local time of the start.

- `run.log` - time-stamped lines: the start and the outcome of every part, what was done,
  every error, what an agent or a person did by hand.
- `report.md` - written at the end: the result (PASSED, FAILED, BLOCKED or NOT FINISHED),
  date and environment, a table `# | Step | Expected | Actual | Done by | Result`, the
  findings (bugs), repair suggestions for every part an agent took over (what broke, why,
  what the agent did instead, the proposed fix) and notes.
- Screenshots and other evidence go to the same folder.

## 6. What belongs together

Work out from what I say which tests this one depends on, which existing scripts it can
use as they are and which need a change, and whether the recording is a new test or a
change of an existing one. Do not duplicate: adapt what exists. When a test changes, change
`test.md`, its scripts and `documentation.md` together.

## 7. Rules for the scripts

1. **FAILED or BROKEN is your decision as the author.** State what the product must do as
   an explicit check of a found element or value: only such a check ends with code 1.
   Everything else that goes wrong is code 3. Never catch an error to turn it into a pass.
2. **Finding elements:** a test id when the application has one, then role and accessible
   name, label, visible text. No CSS, no XPath, no positions.
3. **No sleeps.** Wait for a condition: an element, a response, a changed value.
4. **Dates and times are computed**, never typed in.
5. **Data the test creates** carries a prefix unique to the run, so it can be found and
   removed. The last part cleans up and is safe to run after an earlier part failed.
6. **Setup and cleanup through an API** when there is one. Go through the user interface
   only for what the test is about.
7. **Side effects:** say which steps create, change or delete data. Ask me before you add
   such a step that I did not show.
8. Keep it small: labels as constants at the top, no frameworks.

## 8. Running a test and taking a part over

Create the run folder, follow `test.md` from the top and run each script with `--run-dir`.

- **0:** go on with the next step.
- **1:** stop. Do not take the part over and do not run it again to get a pass. Describe
  the finding in `report.md`.
- **2:** remove the cause or ask me, then run the part again.
- **3:** read `run.log` and the evidence. First judge whether the product is wrong after
  all; then the result is FAILED. Otherwise do exactly this one part by hand as `test.md`
  describes it, check its expected result yourself, write what you did to `run.log` and
  the values later parts need to `context.json`, and continue with the next script. One
  attempt: when you cannot do it either, ask me; when that does not help, stop with
  NOT FINISHED.
- A `user` step: put the request at the start of your message ("**Your turn:** ..."), with
  absolute paths in every command, and wait for my answer.
- Do only what the step says: no extra clicks, no other changes of data.
- Never repair a script during a run. Put the suggestion into `report.md` and offer the
  repair afterwards.

## 9. How to create the test

1. From the recording, work out the goal, the steps, the expected results, the data and
   the prerequisites. Ask me about anything that changes what you build, with the time
   stamp.
2. Find or create `test-cases`; read `README.md` and the tests and scripts that exist.
3. Write `test.md` first, then the scripts part by part, running each against the real
   system as you go, then `documentation.md`; update `README.md`.
4. **A green run is mandatory:** run the whole test once the way it will be run. Every
   scripted part must pass as scripted. A part that is not reliable after a reasonable
   effort becomes `ai - unstable automation: <what>`; an honest `ai` step is better than a
   flaky script. A bug of the product found on the way is a finding, not something to
   script around.
5. Tell me what the test covers, which steps are `ai` or `user` and why, what it changes
   in the system, how to run it, what you assumed, and the absolute paths of `test.md`,
   `documentation.md` and the folder of the green run.

## 10. Repairing a test

Only when I ask for it. Read the repair suggestions of the report and the evidence, then
decide: the script is wrong (fix it), the test changed on purpose (fix `test.md`, the
scripts and `documentation.md` together; a changed expected result needs my confirmation),
or the part cannot be scripted reliably (make it `ai`). Finish with a green run.
