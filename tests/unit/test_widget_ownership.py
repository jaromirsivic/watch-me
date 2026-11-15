"""No window keeps owning in Python what Qt made its child.

An object owned by both is deleted twice when Python's cyclic collector frees it with
its window off the GUI thread, and the process ends (see ``watch_me.editor.workers``).
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget  # noqa: E402
from qt_ownership import owned_by_python_under  # noqa: E402
from test_editor import NEWEST, make_recording  # noqa: E402

from watch_me.core.config import Config  # noqa: E402
from watch_me.core.transcript import Segment  # noqa: E402
from watch_me.editor import player as player_mod  # noqa: E402
from watch_me.editor.folder_dialogs import CreateFolderDialog, MoveToFolderDialog  # noqa: E402
from watch_me.editor.instructions_dialog import InstructionsDialog  # noqa: E402
from watch_me.editor.mouse_details_dialog import MouseDetailsDialog  # noqa: E402
from watch_me.editor.preview import PreviewPanel  # noqa: E402
from watch_me.editor.render_dialog import RenderVideoDialog  # noqa: E402
from watch_me.editor.subtitle_dialog import SubtitleDialog  # noqa: E402
from watch_me.editor.window import EditorWindow  # noqa: E402
from watch_me.ui.settings_dialog import SettingsDialog  # noqa: E402
from watch_me.ui.stop_dialog import StopDialog  # noqa: E402


def test_the_check_sees_a_widget_left_to_python(qtbot):
    """The pattern the other tests guard against, and what makes the check blind."""
    window = QWidget()
    qtbot.addWidget(window)
    outer = QVBoxLayout(window)
    row = QHBoxLayout()
    button = QPushButton("late")
    row.addWidget(button)  # the row has no window yet: Python keeps the button
    outer.addLayout(row)
    assert button.parent() is window
    assert owned_by_python_under(window) == ["QPushButton 'late'"]
    window.findChildren(QWidget)  # hands everything it returns over to C++
    assert owned_by_python_under(window) == []


def _dialogs(tmp_path: Path):
    return {
        "preview": lambda: PreviewPanel(),
        "instructions": lambda: InstructionsDialog("text", None),
        "mouse details": lambda: MouseDetailsDialog(),
        "render": lambda: RenderVideoDialog(
            [("screen1", "screen1")], "screen1", lambda sid: tmp_path / f"{sid}.mp4"
        ),
        "subtitle": lambda: SubtitleDialog(Segment(0, 1000, "hello"), duration_ms=3000),
        "create folder": lambda: CreateFolderDialog(["default"], movable=2),
        "move to folder": lambda: MoveToFolderDialog(["Clients", "Zeta"], 3),
        "settings": lambda: SettingsDialog(Config(recording_folder=tmp_path)),
        "stop": lambda: StopDialog(),
    }


@pytest.mark.parametrize(
    "name",
    [
        "preview",
        "instructions",
        "mouse details",
        "render",
        "subtitle",
        "create folder",
        "move to folder",
        "settings",
        "stop",
    ],
)
def test_python_owns_nothing_below_a_panel_or_dialog(name: str, qtbot, tmp_path: Path):
    widget = _dialogs(tmp_path)[name]()
    qtbot.addWidget(widget)
    assert owned_by_python_under(widget) == []


def test_python_owns_nothing_below_the_editor_window(qtbot, tmp_path: Path, monkeypatch):
    """With a recording loaded and the Mouse window open."""
    monkeypatch.setattr(player_mod, "_load_sounddevice", lambda: None)
    make_recording(tmp_path, NEWEST)
    window = EditorWindow(Config(recording_folder=tmp_path))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(
        lambda: window.recording is not None and window.recording.session_id == NEWEST,
        timeout=10_000,
    )
    window.show_mouse_details()
    assert owned_by_python_under(window) == []
