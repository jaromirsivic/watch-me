---
name: Bug Report
tooltip: Turn the recording into a bug report in the bugs folder of the project
---
# Goal: a bug report (the bug report will be written in {language})

Process the recording (only its cropped range) and file what I show and describe as a bug
report in the `bugs` folder of my project. Create the report right away, without a plan
for me to approve.

The language named in the goal applies to every document you write (`bugreport.md`,
`README.md`) and to your messages to me. File and folder names are always English.

One problem is one bug is one folder `bugs/<folder>/` that holds `bugreport.md` and, when
there are pictures, a `screens` subfolder. The report is for a developer who has not seen
the recording.

## 1. Collect the bug from the recording

My speech, clicks, copied texts and drawn shapes say what is wrong and where. Collect for
each bug:

- the times (ms) where the problem is shown or described;
- the frames of those moments: prefer the `after` time of a `DRAW` line, so that my
  highlight (a rectangle, an arrow) is in the picture, and add the `before` time when the
  highlight hides what is wrong;
- the steps I made before the problem (clicks, navigation): the basis of the steps to
  reproduce.

When the recording shows several problems, file each as a bug of its own (steps 3 to 7
for each of them).

Do not ask me about details: write what is known and mark the rest as not known. Ask only
when you cannot tell what the bug is (where it happens, what is wrong, what was expected),
citing the time stamp.

## 2. The `bugs` folder

Look for `bugs` in the root of the project. When it exists, read its `README.md`. When it
does not exist, create it with a `README.md` and tell me that you created it and its
absolute path. When you cannot tell which folder is the project root, ask me before you
create anything.

```text
bugs/
  README.md                                    what the folder holds, the structure of a bug, the list of bugs
  <YYYY-MM-DD>_<short-summary>/bugreport.md    one bug
  <YYYY-MM-DD>_<short-summary>/screens/        its screenshots
```

`README.md` says what the folder is for and what can be found in it, describes the basic
structure of a bug (the name of its folder, the sections of `bugreport.md`, the severities
A, B and C, the `screens` subfolder) and then lists the bugs: one line per bug with its
date, a link to its `bugreport.md`, its title and its severity. Keep it up to date. When
`bugs` exists without a `README.md`, create one and list the bugs that are already there.

## 3. Check for duplicates - always before you create anything

1. List the folders in `bugs` and read the title, the summary, the use case / feature and
   the actual result of each `bugreport.md`.
2. Compare them with the new bug: the same screen or feature and the same wrong behaviour
   mean the same bug, even when it is worded differently or was found in another
   environment or on another day.
3. **Probably a duplicate:** do not create a folder. Tell me which earlier bug it matches
   (folder name, title, date) and what is the same and what differs, and wait. Create the
   new bug only after I confirm that it should be filed; then name the earlier folder under
   **Related bugs**. When I want the new information added to the earlier bug instead, add
   a dated note to that `bugreport.md` rather than creating a new folder.
4. **Not a duplicate:** continue. When you are not sure, ask me the same way as for a
   duplicate.

## 4. The folder of the bug

Its name is `<YYYY-MM-DD>_<short-kebab-case-summary>`: English, lowercase, at most about
60 characters, saying where and what, for example
`2026-11-19_order-list-filter-ignores-status`. The date is the day the bug is filed. When
the name already exists, append `-2`, `-3`.

## 5. `bugreport.md`

The skeleton below is given in English. Write its headings, labels and fixed values
(`not looked up`, `always`, `none`) in the language of the goal; the severity letters stay
A, B and C.

```markdown
# <Title: what is wrong, where>

- Severity (proposed): <A | B | C> - <one-line reason>
- Environment: <server name and port, or the short name of the environment>, <browser or application>
- Use case / feature: <menu path or screen name>, <the whole URL where the problem was found>
- Specification: <chapter, ID | not looked up>

## Summary

<one or two sentences>

## Steps to reproduce

1. ...
2. ...

Preconditions / test data: <data, time window, role, or "none">.
Reproducibility: <always | sometimes | once | not verified>

## Expected result

<what should happen; say when it comes from the specification rather than from me>

## Actual result

<what happens instead; exact error messages and values>

## Screenshots

![<what it shows>](screens/01-<short-name>.jpg)
<one line: what is wrong in the picture, where my highlight points>

## Related bugs

<earlier folders, or "none">

## Notes

<the folder of the recording and the time range, workarounds, open questions>
```

- **Severity:** A is the most serious (the work is blocked, or data is lost or wrong), B is
  less serious (a function works wrong, but there is a way around it) and C is the least
  serious (cosmetic or a minor inconvenience). It is your proposal with a one-line reason;
  when I name the severity in the recording, use mine.
- **Environment:** only the server name and the port of the address (`host:port`), or the
  short name of the environment when I say it (for example FAT) - not the whole URL. For an
  application that is not a web page, its name and version.
- **Use case / feature:** the whole URL where the problem was found goes here, next to the
  menu path or the name of the screen. Leave out credentials and tokens that are part of
  the URL.
- **Specification:** when the project has a specification or documentation and you find the
  chapter that describes the behaviour, name it. When you do not find it, write
  `not looked up`. A difference from the specification alone is a deviation, not
  automatically a bug: say which of the two it is when you cite the specification.
- **Steps to reproduce** must let a developer get the bug without the recording. Say how to
  simulate it when it depends on data or time. When you cannot derive the steps, write what
  is known and mark the section `incomplete`.
- **Related bugs** and **Notes** come from what was said in the recording and from what you
  found out.
- Keep facts and assumptions apart. Quote my words when they matter, in the language I
  spoke, with the time stamp of the recording.
- Never write a login, a password, a session token or another secret into the report or
  into a file name.

## 6. `screens` - the screenshots

- Copy the frames you need from the recording into `screens` as `NN-<short-name>.<jpg|png>`
  (keep the format of the frame). Copy only the frames that show the bug - typically one to
  five - never the whole recording.
- Every screenshot is referenced from `bugreport.md` with a one-line caption.
- Leave the folder of the recording untouched; name it and the time range in **Notes**.

## 7. Finish

Add the line of the bug to `bugs/README.md`. Then tell me in the chat the absolute path of
the folder of the bug and of its `bugreport.md`, the title, the proposed severity and
everything that is left incomplete - or that you are waiting for my answer about a
duplicate.
