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
    "30-implement-immediately.md",
    "40-test-case-step-by-step.md",
    "50-test-case-immediately.md",
    "60-bug-report.md",
)
BUILT_IN_NAMES = [
    "Draft Intent",
    "Create Plan",
    "Implement Immediately",
    "Test Case Step by Step",
    "Test Case Immediately",
    "Bug Report",
]


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


def test_the_built_in_folder_holds_exactly_the_six_templates():
    assert tuple(sorted(p.name for p in TEMPLATES_DIR.glob("*.md"))) == BUILT_IN_FILES
    assert _names(load_templates(TEMPLATES_DIR)) == BUILT_IN_NAMES


def test_built_in_templates_in_file_order_with_the_language_where_it_belongs():
    draft, plan, implement, step_by_step, immediately, bug = load_templates(TEMPLATES_DIR)
    assert all(t.tooltip for t in (draft, plan, implement, step_by_step, immediately, bug))
    assert draft.text.splitlines()[0] == (
        "# Goal: a formal brief only (the draft intent will be written in {language})"
    )
    assert plan.text.splitlines()[0] == (
        "# Goal: an implementation plan (the plan will be written in {language})"
    )
    assert step_by_step.text.splitlines()[0] == (
        "# Goal: a test case, step by step "
        "(the plan, the test and the documentation will be written in {language})"
    )
    assert immediately.text.splitlines()[0] == (
        "# Goal: a test case (the test and the documentation will be written in {language})"
    )
    assert bug.text.splitlines()[0] == (
        "# Goal: a bug report (the bug report will be written in {language})"
    )
    implement_lines = implement.text.splitlines()
    assert implement_lines[0] == "# Goal: implement everything"
    assert "- The default language of a user interface in the output is {language}." in (
        implement_lines
    )
    assert not draft.text.startswith("---") and "tooltip:" not in draft.text


def test_both_test_case_templates_share_the_description_in_parts():
    shared = (TEMPLATES_DIR / "parts" / "test-case.md").read_text(encoding="utf-8").strip()
    assert "The language named in the goal applies to every document you write" in shared
    step_by_step, immediately = load_templates(TEMPLATES_DIR)[3:5]
    for template in (step_by_step, immediately):
        assert template.text.endswith("\n\n" + shared + "\n")
        assert "{include:" not in template.text
    goal = "# Goal: a test case (the test and the documentation will be written in {language})"
    assert immediately.text == goal + "\n\n" + shared + "\n"


def test_the_bug_report_template_files_a_bug_in_the_bugs_folder():
    bug = load_templates(TEMPLATES_DIR)[5]
    assert bug.name == "Bug Report"
    assert not bug.text.startswith("---") and "tooltip:" not in bug.text
    for expected in (
        "<A | B | C>",
        "`bugs`",
        "screens/01-<short-name>.jpg",
        "not looked up",
        "absolute path",
    ):
        assert expected in bug.text
    assert "mimosa" not in bug.text.lower()
    assert "{include:" not in bug.text
    czech = bug.render("Czech")
    assert "{language}" not in czech
    assert czech.splitlines()[0].endswith("(the bug report will be written in Czech)")


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
    assert _names(load_templates(TEMPLATES_DIR, tmp_path / "missing")) == BUILT_IN_NAMES


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


# Includes ----------------------------------------------------------------------------


def test_an_include_line_is_replaced_by_the_text_of_that_file(tmp_path: Path):
    shared = "﻿\r\nShared in {language}.\r\n{include:parts/other.md}\r\n\r\n"
    _write(tmp_path / "parts", "shared.md", shared)
    _write(tmp_path / "parts", "other.md", "never read\n")
    _write(
        tmp_path, "10-a.md", "---\nname: A\n---\n# A\n\n  {include: parts/shared.md}  \n\nEnd.\n"
    )
    _write(tmp_path, "20-b.md", "# B\n{include:parts/shared.md}\n")
    first, second = load_templates(tmp_path)
    assert _names([first, second]) == ["A", "B"], "a file in a subfolder is no template"
    # The included text as it is: without its byte order mark and the empty lines around
    # it, and an include line in it stays text.
    assert first.text == "# A\n\nShared in {language}.\n{include:parts/other.md}\n\nEnd.\n"
    assert second.text == "# B\nShared in {language}.\n{include:parts/other.md}\n"
    assert first.render("Czech").splitlines()[2] == "Shared in Czech."


def test_an_include_inside_a_line_of_text_is_text(tmp_path: Path):
    _write(tmp_path, "10-a.md", "Write {include:parts/x.md} on a line of its own.\n")
    (template,) = load_templates(tmp_path)
    assert template.text == "Write {include:parts/x.md} on a line of its own.\n"


def test_a_template_whose_include_cannot_be_used_is_skipped(tmp_path: Path, caplog):
    folder = tmp_path / "templates"
    outside = _write(tmp_path, "outside.md", "not for templates\n")
    _write(folder, "10-missing.md", "# Missing\n{include:parts/missing.md}\n")
    _write(folder, "20-outside.md", "# Outside\n{include:../outside.md}\n")
    _write(folder, "30-absolute.md", f"# Absolute\n{{include:{outside}}}\n")
    (folder / "parts").mkdir()
    (folder / "parts" / "binary.md").write_bytes(b"\xff\xfe\x00bad")
    _write(folder, "40-binary.md", "# Binary\n{include:parts/binary.md}\n")
    _write(folder, "50-good.md", "good\n")
    with caplog.at_level(logging.WARNING, logger="watch_me.editor.instruction_templates"):
        templates = load_templates(folder)
    assert templates == [Template("Good", "", "good\n")]
    for name in ("10-missing.md", "20-outside.md", "30-absolute.md", "40-binary.md"):
        assert name in caplog.text
    assert caplog.text.count("is outside the folder of the template") == 2


def test_the_length_limit_counts_the_included_text(tmp_path: Path):
    _write(tmp_path / "parts", "long.md", "x" * MAX_INSTRUCTIONS_CHARS)
    _write(tmp_path, "10-too-long.md", "y\n{include:parts/long.md}\n")
    _write(tmp_path, "20-fits.md", "{include:parts/long.md}\n")
    assert _names(load_templates(tmp_path)) == ["Fits"]


# Rendering ---------------------------------------------------------------------------


def test_render_replaces_every_placeholder_and_keeps_other_braces():
    template = Template("T", "", "In {language}, {not this} and {language} again {0}.\n")
    assert template.render("Czech") == "In Czech, {not this} and Czech again {0}.\n"


def test_a_template_without_the_placeholder_renders_unchanged():
    template = Template("T", "", "Just do it.\n")
    assert template.render("Czech") == "Just do it.\n"


def test_built_in_templates_render_in_czech():
    draft, plan, implement = load_templates(TEMPLATES_DIR)[:3]
    first_line = draft.render("Czech").splitlines()[0]
    assert first_line.endswith("(the draft intent will be written in Czech)")
    assert "{language}" not in plan.render("Czech")
    assert "is Czech." in implement.render("Czech")
    assert "source code is English." in implement.render("Czech")
