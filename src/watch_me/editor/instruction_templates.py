"""Instruction templates of the **Instructions** dialog, read from Markdown files.

The built-in templates live in ``assets/instructions`` next to this module; your own
go into ``custom-instructions`` in the state folder (``custom_templates_dir()``), which
survives an update of the plugin. Every ``*.md`` file is one template, ordered by file
name within its folder (``10-draft-intent.md`` comes before ``20-create-plan.md``), the
built-in ones first.

A file may start with a front matter of simple ``key: value`` lines between two
``---`` lines::

    ---
    name: Draft Intent
    tooltip: Turn the recording into a formal brief, then ask how to continue
    ---
    # Goal: a formal brief only (the draft intent will be written in {language})

The front matter is not part of the instructions. Without a ``name`` the name comes
from the file name (``60-code-review.md`` is "Code Review"). ``{language}`` in the
text stands for the language picked in the dialog; a text without it does not depend
on the language.

A line that holds nothing but ``{include:parts/test-case.md}`` is replaced by the text
of that file, so several templates can share one description. The path is relative to
the folder of the template and must stay inside it; the included text is taken as it is
(a ``{include:...}`` in it is not followed, a ``{language}`` is replaced like any
other). Only the ``*.md`` files directly in a folder are templates, so a file to
include goes into a subfolder (``parts``).

A file is skipped (with a warning in the log) when it cannot be read, holds no text,
includes a file that cannot be read, is named ``Custom`` or like a template read before
it (a built-in template wins over your own), or is longer than
``MAX_INSTRUCTIONS_CHARS`` with its includes (storing it would cut it off).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from watch_me.core.config import state_root
from watch_me.core.instructions import MAX_INSTRUCTIONS_CHARS
from watch_me.core.languages import ALL_LANGUAGES, TOP_LANGUAGES

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).with_name("assets") / "instructions"
CUSTOM_TEMPLATES_DIR_NAME = "custom-instructions"
LANGUAGE_PLACEHOLDER = "{language}"
RESERVED_NAME = "Custom"  # the dialog's own item for the user's own words
FRONT_MATTER_FENCE = "---"

_LONGEST_LANGUAGE = max((*TOP_LANGUAGES, *ALL_LANGUAGES), key=len)
_NUMERIC_PREFIX = re.compile(r"^\d+[-_ ]*")
# A line that holds only ``{include:<path>}``.
_INCLUDE_LINE = re.compile(r"^[ \t]*\{include:([^{}\n]+)\}[ \t]*$", re.MULTILINE)


class _IncludeError(Exception):
    """A file named by an ``{include:...}`` line cannot be used; the message says why."""


@dataclass(frozen=True)
class Template:
    name: str
    tooltip: str
    text: str  # may contain LANGUAGE_PLACEHOLDER

    def render(self, language: str) -> str:
        """The text with every ``{language}`` replaced by ``language``."""
        # Not str.format: a template may contain other braces.
        return self.text.replace(LANGUAGE_PLACEHOLDER, language)


def custom_templates_dir() -> Path:
    """The folder of the user's own templates; it is never created here."""
    return state_root() / CUSTOM_TEMPLATES_DIR_NAME


def load_templates(*folders: Path) -> list[Template]:
    """The templates of every ``*.md`` file in ``folders``, in the order of the folders
    and by file name within one; a missing folder holds none."""
    templates: list[Template] = []
    taken = {RESERVED_NAME.casefold()}
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md"), key=lambda p: p.name):
            if not path.is_file():
                continue
            template = _read_template(path)
            if template is None:
                continue
            key = template.name.casefold()
            if key == RESERVED_NAME.casefold():
                log.warning("skipping template %s: the name %r is reserved", path, template.name)
                continue
            if key in taken:
                log.warning(
                    "skipping template %s: a template named %r is already loaded",
                    path,
                    template.name,
                )
                continue
            taken.add(key)
            templates.append(template)
    return templates


def _read_template(path: Path) -> Template | None:
    try:
        # utf-8-sig: a byte order mark (Notepad) is no part of the text.
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        log.warning("skipping template %s: cannot read it: %s", path, exc)
        return None
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    fields, body = _split_front_matter(content)
    try:
        body = _expand_includes(path.parent, body)
    except _IncludeError as exc:
        log.warning("skipping template %s: %s", path, exc)
        return None
    body = body.strip()
    if not body:
        log.warning("skipping template %s: it holds no instructions", path)
        return None
    name = fields.get("name") or _name_from_file(path)
    template = Template(name=name, tooltip=fields.get("tooltip", ""), text=body + "\n")
    length = len(template.render(_LONGEST_LANGUAGE).strip())
    if length > MAX_INSTRUCTIONS_CHARS:
        log.warning(
            "skipping template %s: %d characters, more than %d",
            path,
            length,
            MAX_INSTRUCTIONS_CHARS,
        )
        return None
    return template


def _split_front_matter(content: str) -> tuple[dict[str, str], str]:
    """The ``key: value`` fields of the front matter and the text below it."""
    lines = content.split("\n")
    if not lines or lines[0].strip() != FRONT_MATTER_FENCE:
        return {}, content
    for end in range(1, len(lines)):
        if lines[end].strip() == FRONT_MATTER_FENCE:
            break
    else:
        return {}, content  # never closed: no front matter, all of it is text
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep and key.strip():
            fields[key.strip().lower()] = value.strip()
    return fields, "\n".join(lines[end + 1 :])


def _expand_includes(folder: Path, body: str) -> str:
    """``body`` with every ``{include:<path>}`` line replaced by the text of that file
    in ``folder``; raises ``_IncludeError`` when one of them cannot be used."""
    return _INCLUDE_LINE.sub(lambda match: _read_include(folder, match.group(1).strip()), body)


def _read_include(folder: Path, name: str) -> str:
    target = folder / name
    try:
        inside = target.resolve().is_relative_to(folder.resolve())
    except OSError:
        inside = False
    if not inside:
        raise _IncludeError(f"the included file {name!r} is outside the folder of the template")
    try:
        text = target.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise _IncludeError(f"cannot read the included file {name!r}: {exc}") from exc
    # Its text as it is: an include line in it stays a line of text (one level only).
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _name_from_file(path: Path) -> str:
    """``60-code-review.md`` -> ``Code Review``."""
    words = _NUMERIC_PREFIX.sub("", path.stem).replace("-", " ").replace("_", " ").split()
    return " ".join(words).title() if words else path.stem


__all__ = [
    "TEMPLATES_DIR",
    "Template",
    "custom_templates_dir",
    "load_templates",
]
