"""Instruction templates and languages, app icon, waveform fit, screen dot tooltips and
the recordings context menu (open folder, delete) of the editor (offscreen Qt)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import QItemSelectionModel, QPoint, Qt  # noqa: E402
from PySide6.QtGui import QFontMetrics, QTextCursor  # noqa: E402
from PySide6.QtWidgets import QComboBox  # noqa: E402
from test_editor import NEWEST, OLDER, _wait_loaded, make_recording  # noqa: E402

from watch_me.core.config import Config  # noqa: E402
from watch_me.core.instructions import (  # noqa: E402
    MAX_INSTRUCTIONS_CHARS,
    normalize_instructions,
)
from watch_me.core.languages import ALL_LANGUAGES  # noqa: E402
from watch_me.core.session import (  # noqa: E402
    SessionPaths,
    SessionState,
    Status,
    write_state,
)
from watch_me.editor.instruction_templates import (  # noqa: E402
    TEMPLATES_DIR,
    Template,
    custom_templates_dir,
    load_templates,
)
from watch_me.editor.instructions_dialog import (  # noqa: E402
    CUSTOM,
    EXPLANATION,
    MAX_VISIBLE_ITEMS,
    InstructionsDialog,
)
from watch_me.editor.window import EditorWindow  # noqa: E402
from watch_me.host import retention  # noqa: E402
from watch_me.ui.icons import APP_ICON_SIZES, app_icon  # noqa: E402

THIRD = "20260103-100000"


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    make_recording(tmp_path, OLDER, first_text="older one")
    make_recording(tmp_path, NEWEST)
    make_recording(tmp_path, THIRD, first_text="third one")
    return tmp_path


@pytest.fixture
def editor(qtbot, folder: Path):
    window = EditorWindow(Config(recording_folder=folder))
    qtbot.addWidget(window)
    window.resize(1400, 900)
    window.show()
    _wait_loaded(qtbot, window, THIRD)
    return window


# Instructions ---------------------------------------------------------------------


def test_instructions_button_has_no_icon_and_the_example_text_is_gone(editor):
    assert editor.instructions_button.icon().isNull()
    assert "Say what you want" not in EXPLANATION


def _built_in(name: str) -> Template:
    return next(t for t in load_templates(TEMPLATES_DIR) if t.name == name)


DRAFT_INTENT = _built_in("Draft Intent")
CREATE_PLAN = _built_in("Create Plan")
IMPLEMENT = _built_in("Implement Immediately")
TEST_CASE_STEP_BY_STEP = _built_in("Test Case Step by Step")
TEST_CASE = _built_in("Test Case Immediately")
TEST_CASE_GOALS = {
    "Test Case Step by Step": (
        "# Goal: a test case, step by step "
        "(the plan, the test and the documentation will be written in {language})"
    ),
    "Test Case Immediately": (
        "# Goal: a test case (the test and the documentation will be written in {language})"
    ),
}


@pytest.fixture
def custom_dir(tmp_path: Path) -> Path:
    """The custom templates folder of the tests; it does not exist until a test makes it."""
    return tmp_path / "custom-instructions"


@pytest.fixture
def open_dialog(qtbot, custom_dir: Path):
    """Opens the dialog on the built-in templates and ``custom_dir``, never on the real
    custom templates of the machine."""

    def open_(text: str = "") -> InstructionsDialog:
        dialog = InstructionsDialog(text, template_dirs=(TEMPLATES_DIR, custom_dir))
        qtbot.addWidget(dialog)
        return dialog

    return open_


def _combo_items(combo: QComboBox) -> list[str]:
    return [combo.itemText(i) for i in range(combo.count())]


def _record_questions(dialog: InstructionsDialog, answer: dict[str, bool]) -> list[str]:
    """Replace both confirmations with ones that note the question and give ``answer``."""
    asked: list[str] = []

    def confirm_replace(template):
        asked.append(template.name)
        return answer["value"]

    def confirm_clear():
        asked.append(CUSTOM)
        return answer["value"]

    dialog.confirm_replace = confirm_replace
    dialog.confirm_clear = confirm_clear
    return asked


def test_combo_lists_custom_and_the_built_in_templates_with_tooltips(open_dialog):
    dialog = open_dialog()
    built_in = load_templates(TEMPLATES_DIR)
    assert _combo_items(dialog.template_combo) == [
        CUSTOM,
        "Draft Intent",
        "Create Plan",
        "Implement Immediately",
        "Test Case Step by Step",
        "Test Case Immediately",
    ]
    combo = dialog.template_combo
    tooltips = [combo.itemData(i, Qt.ItemDataRole.ToolTipRole) for i in range(combo.count())]
    assert tooltips[1:] == [t.tooltip for t in built_in]
    assert all(tooltips[1:])
    assert "own" in tooltips[0]


def test_a_file_added_to_the_custom_folder_shows_up_at_the_next_open(open_dialog, custom_dir):
    first = open_dialog()
    assert _combo_items(first.template_combo) == [
        CUSTOM,
        "Draft Intent",
        "Create Plan",
        "Implement Immediately",
        "Test Case Step by Step",
        "Test Case Immediately",
    ]
    custom_dir.mkdir()
    (custom_dir / "50-code-review.md").write_text(
        "# Goal: a code review (the review will be written in {language})\n", encoding="utf-8"
    )
    second = open_dialog()
    assert _combo_items(second.template_combo) == [
        CUSTOM,
        "Draft Intent",
        "Create Plan",
        "Implement Immediately",
        "Test Case Step by Step",
        "Test Case Immediately",
        "Code Review",
    ]
    second.select_language("Czech")
    assert second.select_template("Code Review")
    assert second.instructions() == "# Goal: a code review (the review will be written in Czech)"


def test_the_dialog_reads_custom_instructions_in_the_state_folder_by_default(qtbot):
    custom = custom_templates_dir()  # in the test's own state folder (conftest)
    custom.mkdir(parents=True)
    (custom / "my-review.md").write_text("Review it.\n", encoding="utf-8")
    dialog = InstructionsDialog("")
    qtbot.addWidget(dialog)
    assert _combo_items(dialog.template_combo)[:2] == [CUSTOM, "Draft Intent"]
    assert _combo_items(dialog.template_combo)[-1] == "My Review"


def test_language_combo_lists_the_top_languages_a_separator_and_all(open_dialog):
    dialog = open_dialog()
    combo = dialog.language_combo
    items = _combo_items(combo)
    assert items[:2] == ["English", "Czech"]
    assert items[2] == ""
    assert combo.itemData(2, Qt.ItemDataRole.AccessibleDescriptionRole) == "separator"
    assert tuple(items[3:]) == ALL_LANGUAGES
    assert dialog.selected_language() == "English"
    assert combo.currentIndex() == 0


def test_language_combo_is_enabled_on_custom_and_leaves_the_text_alone(open_dialog):
    dialog = open_dialog("my own words")
    asked = _record_questions(dialog, {"value": True})
    assert dialog.selected_template() == CUSTOM
    assert dialog.language_combo.isEnabled()
    dialog.select_language("Czech")
    assert dialog.selected_language() == "Czech"
    assert dialog.text_edit.toPlainText() == "my own words"
    assert dialog.selected_template() == CUSTOM
    assert asked == []


def test_empty_box_opens_on_custom_and_english(open_dialog):
    dialog = open_dialog("")
    assert dialog.template_combo.currentText() == CUSTOM
    assert dialog.selected_language() == "English"


def test_other_text_opens_on_custom_and_english(open_dialog):
    dialog = open_dialog("my own words")
    assert dialog.template_combo.currentText() == CUSTOM
    assert dialog.selected_language() == "English"


def test_a_templates_text_opens_on_that_template_without_asking(open_dialog, monkeypatch):
    def never(*_args):
        raise AssertionError("opening the dialog must not ask")

    monkeypatch.setattr(InstructionsDialog, "confirm_replace", never)
    monkeypatch.setattr(InstructionsDialog, "confirm_clear", never)
    text = "\n" + CREATE_PLAN.render("English").strip() + "\n\n"
    dialog = open_dialog(text)
    assert dialog.template_combo.currentText() == "Create Plan"
    assert dialog.selected_language() == "English"
    assert dialog.text_edit.toPlainText() == text


def test_a_czech_create_plan_opens_on_create_plan_and_czech(open_dialog):
    stored = normalize_instructions(CREATE_PLAN.render("Czech"))
    dialog = open_dialog(stored)
    assert dialog.selected_template() == "Create Plan"
    assert dialog.selected_language() == "Czech"
    assert dialog.language_combo.currentIndex() == 1, "the Czech at the top"
    assert dialog.text_edit.toPlainText() == stored


def test_a_template_in_a_language_from_the_full_list_is_recognised(open_dialog):
    dialog = open_dialog(DRAFT_INTENT.render("Norwegian Bokmål"))
    assert dialog.selected_template() == "Draft Intent"
    assert dialog.selected_language() == "Norwegian Bokmål"


def test_picking_a_template_fills_an_empty_box_without_asking(open_dialog):
    dialog = open_dialog("")
    asked = _record_questions(dialog, {"value": False})
    assert dialog.select_template("Create Plan")
    assert asked == []
    assert dialog.text_edit.toPlainText() == CREATE_PLAN.render("English")
    assert dialog.template_combo.currentText() == "Create Plan"
    assert "implementation plan" in dialog.instructions()


def test_picking_a_template_in_the_combo_fills_the_box(open_dialog):
    dialog = open_dialog("")
    dialog.template_combo.setCurrentIndex(dialog.template_combo.findText("Draft Intent"))
    assert dialog.text_edit.toPlainText() == DRAFT_INTENT.render("English")


def test_template_texts_say_what_the_ai_must_do():
    assert "formal brief" in DRAFT_INTENT.text and "ask me whether" in DRAFT_INTENT.text
    assert "Do not implement" in CREATE_PLAN.text
    assert "do not ask me" in IMPLEMENT.text
    assert all(len(t.text) < 1000 for t in (DRAFT_INTENT, CREATE_PLAN, IMPLEMENT))


def test_the_lists_show_at_most_ten_rows_and_scroll(open_dialog, qtbot):
    dialog = open_dialog()
    dialog.show()
    qtbot.waitExposed(dialog)
    assert MAX_VISIBLE_ITEMS == 10
    for combo, scrolls in ((dialog.language_combo, True), (dialog.template_combo, False)):
        assert combo.maxVisibleItems() == MAX_VISIBLE_ITEMS
        combo.showPopup()
        view = combo.view()
        qtbot.waitUntil(view.isVisible)
        bar = view.verticalScrollBar()
        bottom_row = view.indexAt(QPoint(1, view.viewport().height() - 1)).row()
        if scrolls:
            assert combo.count() > MAX_VISIBLE_ITEMS
            assert bottom_row == MAX_VISIBLE_ITEMS - 1, "ten rows, the separator is one of them"
            assert bar.maximum() > 0 and bar.isVisible()
        else:
            assert bottom_row == combo.count() - 1, "every row fits"
            assert bar.maximum() == 0 and not bar.isVisible()
        combo.hidePopup()


def test_the_rows_of_a_list_keep_room_around_the_text(open_dialog):
    dialog = open_dialog()
    combo = dialog.language_combo
    text_height = combo.fontMetrics().height()
    assert combo.view().sizeHintForRow(0) >= text_height + 8
    assert combo.view().sizeHintForRow(2) < text_height, "the separator stays a thin line"
    assert combo.itemData(2, Qt.ItemDataRole.SizeHintRole) is None


def test_test_case_step_by_step_plans_first_and_then_describes_the_test_case():
    text = TEST_CASE_STEP_BY_STEP.text
    plan, _, rest = text.partition("## Step 2: the test case")
    assert "## Step 1: the plan" in plan
    for word in (
        "Do not create or change any file yet",
        "**What will be tested:**",
        "**Preconditions:**",
        "**Acceptance:** what it means that the test passed",
        "**Not fully automated:**",
        "**Open questions:**",
        "default",
        "wait for my approval",
    ):
        assert word in plan, word
    assert "After my approval" in rest
    shared = TEST_CASE.text.partition("\n\n")[2]  # everything under the goal line
    assert shared.startswith("Process the recording")
    assert rest.endswith(shared), "the same description as Test Case Immediately"


@pytest.mark.parametrize("template", [TEST_CASE_STEP_BY_STEP, TEST_CASE], ids=lambda t: t.name)
def test_test_case_template_describes_the_test_cases_folder(template: Template):
    text = template.text
    assert text.splitlines()[0] == TEST_CASE_GOALS[template.name]
    assert "{include:" not in text
    assert text.count("{language}") == 1
    assert text.count("English") == 1  # only: code, names and run.log are always English
    for word in (
        "test-cases",
        "scripts/",
        "tests/<test>/test.md",
        "docs/<test>/documentation.md",
        "logs/<test>/",
        "README.md",
        "run.log",
        "report.md",
    ):
        assert word in text, word
    assert "mimosa" not in text.lower()


@pytest.mark.parametrize("template", [TEST_CASE_STEP_BY_STEP, TEST_CASE], ids=lambda t: t.name)
def test_test_case_template_fits_the_instructions_limit(template: Template):
    longest = max(ALL_LANGUAGES, key=len)
    for language in ("English", longest):
        rendered = template.render(language)
        assert len(rendered.strip()) <= MAX_INSTRUCTIONS_CHARS
        assert normalize_instructions(rendered) == rendered.strip()  # stored uncut


@pytest.mark.parametrize("name", list(TEST_CASE_GOALS))
def test_test_case_in_czech_is_stored_and_recognised_again(open_dialog, name: str):
    dialog = open_dialog()
    dialog.select_language("Czech")
    assert dialog.select_template(name)
    stored = dialog.instructions()
    assert stored.splitlines()[0] == TEST_CASE_GOALS[name].replace("{language}", "Czech")
    assert "{language}" not in stored
    again = open_dialog(stored)
    assert again.selected_template() == name
    assert again.selected_language() == "Czech"


def test_draft_intent_in_czech_names_the_language_in_the_goal(open_dialog):
    dialog = open_dialog("")
    dialog.select_language("Czech")
    assert dialog.select_template("Draft Intent")
    first_line = dialog.instructions().splitlines()[0]
    assert first_line == "# Goal: a formal brief only (the draft intent will be written in Czech)"


def test_create_plan_in_czech_names_the_language_in_the_goal(open_dialog):
    dialog = open_dialog("")
    dialog.select_language("Czech")
    assert dialog.select_template("Create Plan")
    first_line = dialog.instructions().splitlines()[0]
    assert first_line == "# Goal: an implementation plan (the plan will be written in Czech)"


def test_implement_in_czech_keeps_code_in_english_and_the_interface_in_czech(open_dialog):
    dialog = open_dialog("")
    dialog.select_language("Czech")
    assert dialog.select_template("Implement Immediately")
    lines = dialog.instructions().splitlines()
    assert lines[0] == "# Goal: implement everything"
    assert "- The default language of a user interface in the output is Czech." in lines
    assert (
        "- The implementation language and the language of comments in the source code "
        "is English." in lines
    )


def test_changing_the_language_of_a_template_rewrites_it_without_asking(open_dialog):
    dialog = open_dialog("")
    asked = _record_questions(dialog, {"value": False})
    assert dialog.select_template("Create Plan")
    dialog.select_language("Czech")
    assert dialog.text_edit.toPlainText() == CREATE_PLAN.render("Czech")
    assert dialog.selected_template() == "Create Plan"
    dialog.select_language("German")
    assert dialog.text_edit.toPlainText() == CREATE_PLAN.render("German")
    assert dialog.selected_template() == "Create Plan"
    assert asked == []


def test_select_language_takes_the_top_item_and_rejects_unknown_names(open_dialog):
    dialog = open_dialog("")
    dialog.select_language("German")
    dialog.select_language("Czech")
    assert dialog.language_combo.currentIndex() == 1
    with pytest.raises(ValueError):
        dialog.select_language("Klingon")
    with pytest.raises(ValueError):
        dialog.select_language("")


def test_replacing_other_text_asks_first(open_dialog):
    dialog = open_dialog("my own words")
    answer = {"value": False}
    asked = _record_questions(dialog, answer)
    assert not dialog.select_template("Implement Immediately")
    assert asked == ["Implement Immediately"]
    assert dialog.text_edit.toPlainText() == "my own words", "No keeps the text"
    assert dialog.template_combo.currentText() == CUSTOM, "No puts the combo back"
    answer["value"] = True
    assert dialog.select_template("Implement Immediately")
    assert dialog.text_edit.toPlainText() == IMPLEMENT.render("English")
    assert dialog.template_combo.currentText() == "Implement Immediately"
    assert dialog.apply_template(IMPLEMENT)  # the same template again: no question
    assert asked == ["Implement Immediately", "Implement Immediately"]


def test_switching_between_templates_asks_and_no_goes_back(open_dialog):
    dialog = open_dialog(DRAFT_INTENT.render("English"))
    answer = {"value": False}
    asked = _record_questions(dialog, answer)
    assert not dialog.select_template("Create Plan")
    assert asked == ["Create Plan"]
    assert dialog.template_combo.currentText() == "Draft Intent"
    assert dialog.text_edit.toPlainText() == DRAFT_INTENT.render("English")
    answer["value"] = True
    assert dialog.select_template("Create Plan")
    assert dialog.text_edit.toPlainText() == CREATE_PLAN.render("English")


def test_custom_clears_the_box_after_yes(open_dialog):
    dialog = open_dialog(IMPLEMENT.render("English"))
    asked = _record_questions(dialog, {"value": True})
    assert dialog.select_template(CUSTOM)
    assert asked == [CUSTOM]
    assert dialog.text_edit.toPlainText() == ""
    assert dialog.template_combo.currentText() == CUSTOM


def test_custom_with_no_keeps_the_template_and_its_text(open_dialog):
    dialog = open_dialog(IMPLEMENT.render("English"))
    asked = _record_questions(dialog, {"value": False})
    assert not dialog.select_template(CUSTOM)
    assert asked == [CUSTOM]
    assert dialog.text_edit.toPlainText() == IMPLEMENT.render("English")
    assert dialog.template_combo.currentText() == "Implement Immediately"


def test_custom_on_an_empty_box_asks_nothing(open_dialog):
    dialog = open_dialog("")
    asked = _record_questions(dialog, {"value": True})
    dialog._set_combo("Draft Intent")  # a template selected over an empty box
    assert dialog.select_template(CUSTOM)
    assert asked == []
    assert dialog.text_edit.toPlainText() == ""
    assert dialog.template_combo.currentText() == CUSTOM


def test_editing_a_templates_text_by_hand_switches_to_custom(open_dialog):
    dialog = open_dialog("")
    asked = _record_questions(dialog, {"value": True})
    dialog.select_language("Czech")
    assert dialog.select_template("Draft Intent")
    assert dialog.template_combo.currentText() == "Draft Intent"
    dialog.text_edit.moveCursor(QTextCursor.MoveOperation.End)
    dialog.text_edit.insertPlainText("Also check the logs.\n")
    assert dialog.template_combo.currentText() == CUSTOM
    assert dialog.selected_language() == "Czech", "the language stays"
    assert asked == []
    assert dialog.text_edit.toPlainText() == DRAFT_INTENT.render("Czech") + "Also check the logs.\n"
    dialog.select_language("English")
    assert dialog.text_edit.toPlainText() == DRAFT_INTENT.render("Czech") + "Also check the logs.\n"


# Application icon -------------------------------------------------------------------


def test_app_icon_has_every_size(qtbot):
    icon = app_icon()
    sizes = {size.width() for size in icon.availableSizes()}
    assert set(APP_ICON_SIZES) <= sizes
    image = icon.pixmap(64, 64).toImage()
    assert image.pixelColor(32, 2).name() == "#1f6fd0"  # the blue background


# Waveform -------------------------------------------------------------------------


def test_fit_button_stretches_the_waveform_to_the_loudest_sound(editor, qtbot):
    timeline = editor.timeline
    qtbot.waitUntil(lambda: timeline.fit_button_rect() is not None, timeout=5000)
    assert not timeline.audio_fit and timeline.waveform_gain() == 1.0
    rect = timeline.fit_button_rect()
    assert rect.right() < 70 and timeline.audio_rect().contains(rect)
    qtbot.mouseClick(timeline, Qt.MouseButton.LeftButton, pos=rect.center())
    assert timeline.audio_fit
    # The sine in the test WAV peaks at 12000 / 32768.
    assert timeline.waveform_gain() == pytest.approx(32768 / 12000, rel=0.01)
    assert editor.model.playhead_ms == 0, "the toggle does not move the playhead"
    qtbot.mouseClick(timeline, Qt.MouseButton.LeftButton, pos=rect.center())
    assert not timeline.audio_fit


# Screen dots -------------------------------------------------------------------------


def test_screen_dot_tooltip_names_the_screen_and_its_size(editor):
    view = editor.list_view
    index = view.model().index(1, 0)  # row 0 is the default folder's header
    line = QFontMetrics(view.font()).lineSpacing()
    first, second = view.delegate.dot_rects(view.visualRect(index), 2, line)
    assert view.dot_tooltip(first.center()) == "screen1 320x200"
    assert view.dot_tooltip(second.center()) == "screen2 160x100"
    assert view.dot_tooltip(QPoint(first.left() - 40, first.center().y())) is None


# Context menu: delete and open folder ------------------------------------------------


def _select_rows(editor, rows: list[int]) -> None:
    selection = editor.list_view.selectionModel()
    selection.clearSelection()
    for row in rows:
        selection.select(editor.recordings.index(row), QItemSelectionModel.SelectionFlag.Select)


def test_delete_one_recording_after_confirmation(editor, folder, qtbot):
    asked: list[int] = []
    editor._confirm_delete = lambda items: asked.append(len(items)) or True
    item = editor.recordings.item(3)  # the oldest, not the one shown
    assert editor.delete_recordings([item]) == [OLDER]
    assert asked == [1]
    assert not (folder / "default" / OLDER).exists()
    assert [i.session_id for i in editor.recordings.items] == [THIRD, NEWEST]
    assert editor.recording.session_id == THIRD


def test_declined_confirmation_deletes_nothing(editor, folder):
    editor._confirm_delete = lambda items: False
    assert editor.delete_recordings([editor.recordings.item(2)]) == []
    assert (folder / "default" / NEWEST).exists() and len(editor.recordings.items) == 3


def test_delete_several_selected_including_the_shown_one(editor, folder, qtbot):
    editor._confirm_delete = lambda items: True
    _select_rows(editor, [1, 2])
    items = editor.selected_items()
    assert [i.session_id for i in items] == [THIRD, NEWEST]
    assert sorted(editor.delete_recordings(items)) == sorted([THIRD, NEWEST])
    assert not (folder / "default" / THIRD).exists()
    assert not (folder / "default" / NEWEST).exists()
    _wait_loaded(qtbot, editor, OLDER)  # the list refreshed and shows what is left


def test_recording_in_use_is_kept(editor, folder, monkeypatch):
    editor._confirm_delete = lambda items: True
    reported: list[list[str]] = []
    editor._report_delete_failures = reported.append
    paths = SessionPaths(folder, OLDER)
    paths.work_dir.mkdir(parents=True)
    state = SessionState(session_id=OLDER, status=Status.EDITING, recording_folder=str(folder))
    write_state(paths.state_path, state)  # the pid is this (running) process
    assert editor.delete_recordings([editor.recordings.item(3)]) == []
    assert (folder / "default" / OLDER).exists()
    assert len(reported) == 1 and retention.IN_USE_REASON in reported[0][0]


def test_open_folder_location_opens_the_recording_folder(editor, folder, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(
        "watch_me.editor.window.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    assert editor.open_folder_location(editor.recordings.item(2))
    assert Path(opened[0]) == folder / "default" / NEWEST


def test_shift_click_selects_several_rows_and_shows_the_clicked_one(editor, qtbot):
    view = editor.list_view
    first = view.visualRect(editor.recordings.index(1)).center()
    last = view.visualRect(editor.recordings.index(3)).center()
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=first)
    qtbot.mouseClick(
        view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, last
    )
    assert len(editor.selected_items()) == 3
    _wait_loaded(qtbot, editor, OLDER)
