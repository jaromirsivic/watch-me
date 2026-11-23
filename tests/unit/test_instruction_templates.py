"""Instruction templates read from Markdown files (built-in and custom folders)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from watch_me.core.config import state_root
from watch_me.core.instructions import MAX_INSTRUCTIONS_CHARS
from watch_me.core.languages import ALL_LANGUAGES
from watch_me.editor.instruction_templates import (
    TEMPLATES_DIR,
    Template,
    custom_templates_dir,
    load_templates,
)

BUILT_IN_FILES = (
    "10-draft-intent.md",
    "20-create-plan.md",
    "30-implement.md",
    "40-test-case.md",
)


def _write(folder: Path, name: str, content: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(content.encode("utf-8"))  # exactly these line endings
    return path


def _names(templates: list[Template]) -> list[str]:
    return [t.name for t in templates]


# The built-in files ------------------------------------------------------------------


@pytest.mark.parametrize("file_name", BUILT_IN_FILES)
def test_built_in_files_have_a_front_matter_with_name_and_tooltip(file_name: str):
    content = (TEMPLATES_DIR / file_name).read_text(encoding="utf-8")
    lines = content.splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    keys = {line.partition(":")[0] for line in lines[1:end]}
    assert {"name", "tooltip"} <= keys


def test_the_built_in_folder_holds_exactly_the_four_templates():
    assert tuple(sorted(p.name for p in TEMPLATES_DIR.glob("*.md"))) == BUILT_IN_FILES
    assert _names(load_templates(TEMPLATES_DIR)) == [
        "Draft Intent",
        "Create Plan",
        "Implement",
        "Test Case",
    ]


def test_built_in_templates_in_file_order_with_the_language_where_it_belongs():
    draft, plan, implement = load_templates(TEMPLATES_DIR)[:3]
    assert _names([draft, plan, implement]) == ["Draft Intent", "Create Plan", "Implement"]
    assert all(t.tooltip for t in (draft, plan, implement))
    assert draft.text.splitlines()[0] == (
        "# Goal: a formal brief only (all outputs will be written in {language})"
    )
    assert plan.text.splitlines()[0] == (
        "# Goal: an implementation plan (all outputs will be written in {language})"
    )
    implement_lines = implement.text.splitlines()
    assert implement_lines[0] == "# Goal: implement everything"
    assert "- The default language of a user interface in the output is {language}." in (
        implement_lines
    )
    assert not draft.text.startswith("---") and "tooltip:" not in draft.text


# Loading -----------------------------------------------------------------------------


def test_front_matter_gives_name_and_tooltip_and_is_not_part_of_the_text(tmp_path: Path):
    _write(
        tmp_path,
        "a.md",
        "---\r\nname: My Review\r\ntooltip: Review the code\r\n---\r\n\r\n# Review\r\nDo it.\r\n",
    )
    (template,) = load_templates(tmp_path)
    assert template == Template("My Review", "Review the code", "# Review\nDo it.\n")


def test_without_a_name_it_comes_from_the_file_name(tmp_path: Path):
    _write(tmp_path, "50-code-review.md", "Review the code.\n")
    _write(tmp_path, "60_my_own_steps.md", "---\ntooltip: Mine\n---\nSteps.\n")
    first, second = load_templates(tmp_path)
    assert (first.name, first.tooltip) == ("Code Review", "")
    assert (second.name, second.tooltip) == ("My Own Steps", "Mine")


def test_order_by_file_name_and_built_in_before_custom(tmp_path: Path):
    built_in = tmp_path / "built-in"
    custom = tmp_path / "custom"
    _write(built_in, "20-b.md", "---\nname: B\n---\nb\n")
    _write(built_in, "10-a.md", "---\nname: A\n---\na\n")
    _write(custom, "05-first.md", "first\n")
    _write(custom, "notes.txt", "not a template\n")
    assert _names(load_templates(built_in, custom)) == ["A", "B", "First"]


def test_a_missing_folder_holds_no_templates(tmp_path: Path):
    assert load_templates(tmp_path / "missing") == []
    assert _names(load_templates(TEMPLATES_DIR, tmp_path / "missing"))[:3] == [
        "Draft Intent",
        "Create Plan",
        "Implement",
    ]


def test_custom_templates_dir_is_in_the_state_folder_and_never_created():
    folder = custom_templates_dir()
    assert folder == state_root() / "custom-instructions"
    assert not folder.exists()
    load_templates(TEMPLATES_DIR, folder)
    assert not folder.exists()


def test_skipped_files_are_logged(tmp_path: Path, caplog):
    built_in = tmp_path / "built-in"
    custom = tmp_path / "custom"
    _write(built_in, "10-plan.md", "---\nname: Create Plan\n---\nplan\n")
    _write(custom, "10-empty.md", "---\nname: Empty\n---\n  \n\n")
    _write(custom, "20-custom.md", "---\nname: custom\n---\nmine\n")
    _write(custom, "30-plan.md", "---\nname: Create Plan\n---\nanother plan\n")
    _write(custom, "40-long.md", "x" * (MAX_INSTRUCTIONS_CHARS + 1))
    _write(custom, "50-good.md", "good\n")
    (custom / "60-binary.md").write_bytes(b"\xff\xfe\x00bad")
    with caplog.at_level(logging.WARNING, logger="watch_me.editor.instruction_templates"):
        templates = load_templates(built_in, custom)
    assert templates == [Template("Create Plan", "", "plan\n"), Template("Good", "", "good\n")]
    logged = caplog.text
    for name in ("10-empty.md", "20-custom.md", "30-plan.md", "40-long.md", "60-binary.md"):
        assert name in logged


def test_the_length_limit_counts_the_longest_language(tmp_path: Path):
    longest = max(ALL_LANGUAGES, key=len)
    room = MAX_INSTRUCTIONS_CHARS - len("{language}")
    _write(tmp_path, "10-fits-short-names-only.md", "x" * room + "{language}")
    _write(tmp_path, "20-too-long.md", "x" * (room + 1) + "{language}")
    fits = "x" * (MAX_INSTRUCTIONS_CHARS - len(longest)) + "{language}"
    _write(tmp_path, "30-fits-every-language.md", fits)
    assert _names(load_templates(tmp_path)) == ["Fits Every Language"]


def test_a_byte_order_mark_is_no_part_of_the_text(tmp_path: Path):
    (tmp_path / "a.md").write_bytes("﻿---\nname: A\n---\ntext\n".encode())
    assert load_templates(tmp_path) == [Template("A", "", "text\n")]


def test_an_unclosed_front_matter_is_text(tmp_path: Path):
    _write(tmp_path, "10-odd.md", "---\nname: Odd\nno end\n")
    (template,) = load_templates(tmp_path)
    assert template.name == "Odd"
    assert template.text == "---\nname: Odd\nno end\n"


# Rendering ---------------------------------------------------------------------------


def test_render_replaces_every_placeholder_and_keeps_other_braces():
    template = Template("T", "", "In {language}, {not this} and {language} again {0}.\n")
    assert template.render("Czech") == "In Czech, {not this} and Czech again {0}.\n"


def test_a_template_without_the_placeholder_renders_unchanged():
    template = Template("T", "", "Just do it.\n")
    assert template.render("Czech") == "Just do it.\n"


def test_built_in_templates_render_in_czech():
    draft, plan, implement = load_templates(TEMPLATES_DIR)[:3]
    assert draft.render("Czech").splitlines()[0].endswith("(all outputs will be written in Czech)")
    assert "{language}" not in plan.render("Czech")
    assert "is Czech." in implement.render("Czech")
    assert "source code is English." in implement.render("Czech")
