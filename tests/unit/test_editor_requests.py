"""Instruction templates, app icon, waveform fit, screen dot tooltips and the recordings
context menu (open folder, delete) of the editor (offscreen Qt)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import QItemSelectionModel, QPoint, Qt  # noqa: E402
from PySide6.QtGui import QFontMetrics, QTextCursor  # noqa: E402
from test_editor import NEWEST, OLDER, _wait_loaded, make_recording  # noqa: E402

from watch_me.core.config import Config  # noqa: E402
from watch_me.core.session import (  # noqa: E402
    SessionPaths,
    SessionState,
    Status,
    write_state,
)
from watch_me.editor.instructions_dialog import (  # noqa: E402
    CREATE_PLAN,
    CUSTOM,
    DRAFT_INTENT,
    EXPLANATION,
    IMPLEMENT,
    TEMPLATES,
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


def _combo_items(dialog: InstructionsDialog) -> list[str]:
    combo = dialog.template_combo
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


def test_combo_lists_custom_and_the_three_templates_with_tooltips(qtbot):
    dialog = InstructionsDialog("")
    qtbot.addWidget(dialog)
    assert _combo_items(dialog) == [CUSTOM, "Draft Intent", "Create Plan", "Implement"]
    assert CUSTOM not in [t.name for t in TEMPLATES]
    combo = dialog.template_combo
    tooltips = [combo.itemData(i, Qt.ItemDataRole.ToolTipRole) for i in range(combo.count())]
    assert tooltips[1:] == [t.tooltip for t in TEMPLATES]
    assert "own" in tooltips[0]


def test_empty_box_opens_on_custom(qtbot):
    dialog = InstructionsDialog("")
    qtbot.addWidget(dialog)
    assert dialog.template_combo.currentText() == CUSTOM


def test_other_text_opens_on_custom(qtbot):
    dialog = InstructionsDialog("my own words")
    qtbot.addWidget(dialog)
    assert dialog.template_combo.currentText() == CUSTOM


def test_a_templates_text_opens_on_that_template_without_asking(qtbot, monkeypatch):
    def never(*_args):
        raise AssertionError("opening the dialog must not ask")

    monkeypatch.setattr(InstructionsDialog, "confirm_replace", never)
    monkeypatch.setattr(InstructionsDialog, "confirm_clear", never)
    dialog = InstructionsDialog("\n" + CREATE_PLAN.text.strip() + "\n\n")
    qtbot.addWidget(dialog)
    assert dialog.template_combo.currentText() == "Create Plan"
    assert dialog.text_edit.toPlainText() == "\n" + CREATE_PLAN.text.strip() + "\n\n"


def test_picking_a_template_fills_an_empty_box_without_asking(qtbot):
    dialog = InstructionsDialog("")
    qtbot.addWidget(dialog)
    asked = _record_questions(dialog, {"value": False})
    assert dialog.select_template("Create Plan")
    assert asked == []
    assert dialog.text_edit.toPlainText() == CREATE_PLAN.text
    assert dialog.template_combo.currentText() == "Create Plan"
    assert "implementation plan" in dialog.instructions()


def test_picking_a_template_in_the_combo_fills_the_box(qtbot):
    dialog = InstructionsDialog("")
    qtbot.addWidget(dialog)
    dialog.template_combo.setCurrentIndex(dialog.template_combo.findText("Draft Intent"))
    assert dialog.text_edit.toPlainText() == DRAFT_INTENT.text


def test_template_texts_say_what_the_ai_must_do():
    assert "formal brief" in DRAFT_INTENT.text and "ask me whether" in DRAFT_INTENT.text
    assert "Do not implement" in CREATE_PLAN.text
    assert "do not ask me" in IMPLEMENT.text
    assert all(len(t.text) < 1000 for t in TEMPLATES)


def test_replacing_other_text_asks_first(qtbot):
    dialog = InstructionsDialog("my own words")
    qtbot.addWidget(dialog)
    answer = {"value": False}
    asked = _record_questions(dialog, answer)
    assert not dialog.select_template("Implement")
    assert asked == ["Implement"]
    assert dialog.text_edit.toPlainText() == "my own words", "No keeps the text"
    assert dialog.template_combo.currentText() == CUSTOM, "No puts the combo back"
    answer["value"] = True
    assert dialog.select_template("Implement")
    assert dialog.text_edit.toPlainText() == IMPLEMENT.text
    assert dialog.template_combo.currentText() == "Implement"
    assert dialog.apply_template(IMPLEMENT)  # the same template again: no question
    assert asked == ["Implement", "Implement"]


def test_switching_between_templates_asks_and_no_goes_back(qtbot):
    dialog = InstructionsDialog(DRAFT_INTENT.text)
    qtbot.addWidget(dialog)
    answer = {"value": False}
    asked = _record_questions(dialog, answer)
    assert not dialog.select_template("Create Plan")
    assert asked == ["Create Plan"]
    assert dialog.template_combo.currentText() == "Draft Intent"
    assert dialog.text_edit.toPlainText() == DRAFT_INTENT.text
    answer["value"] = True
    assert dialog.select_template("Create Plan")
    assert dialog.text_edit.toPlainText() == CREATE_PLAN.text


def test_custom_clears_the_box_after_yes(qtbot):
    dialog = InstructionsDialog(IMPLEMENT.text)
    qtbot.addWidget(dialog)
    asked = _record_questions(dialog, {"value": True})
    assert dialog.select_template(CUSTOM)
    assert asked == [CUSTOM]
    assert dialog.text_edit.toPlainText() == ""
    assert dialog.template_combo.currentText() == CUSTOM


def test_custom_with_no_keeps_the_template_and_its_text(qtbot):
    dialog = InstructionsDialog(IMPLEMENT.text)
    qtbot.addWidget(dialog)
    asked = _record_questions(dialog, {"value": False})
    assert not dialog.select_template(CUSTOM)
    assert asked == [CUSTOM]
    assert dialog.text_edit.toPlainText() == IMPLEMENT.text
    assert dialog.template_combo.currentText() == "Implement"


def test_custom_on_an_empty_box_asks_nothing(qtbot):
    dialog = InstructionsDialog("")
    qtbot.addWidget(dialog)
    asked = _record_questions(dialog, {"value": True})
    dialog._set_combo("Draft Intent")  # a template selected over an empty box
    assert dialog.select_template(CUSTOM)
    assert asked == []
    assert dialog.text_edit.toPlainText() == ""
    assert dialog.template_combo.currentText() == CUSTOM


def test_editing_a_templates_text_by_hand_switches_to_custom(qtbot):
    dialog = InstructionsDialog("")
    qtbot.addWidget(dialog)
    asked = _record_questions(dialog, {"value": True})
    assert dialog.select_template("Draft Intent")
    assert dialog.template_combo.currentText() == "Draft Intent"
    dialog.text_edit.moveCursor(QTextCursor.MoveOperation.End)
    dialog.text_edit.insertPlainText("Also check the logs.\n")
    assert dialog.template_combo.currentText() == CUSTOM
    assert asked == []
    assert dialog.text_edit.toPlainText() == DRAFT_INTENT.text + "Also check the logs.\n"


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
