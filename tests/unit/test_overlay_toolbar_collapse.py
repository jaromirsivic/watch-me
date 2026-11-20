"""Drawing tools: minimize to the title bar and restore (offscreen Qt)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from watch_me.ui.overlay import DrawingOverlay, Tool  # noqa: E402


@pytest.fixture
def overlay(qtbot):
    overlay = DrawingOverlay()
    overlay.show()
    for window in overlay.windows:
        qtbot.addWidget(window)
    toolbar = overlay._toolbar
    area = QGuiApplication.primaryScreen().geometry()
    toolbar.move(area.topLeft() + QPoint(40, 40))
    toolbar.user_moved = True
    yield overlay
    overlay.close()


def test_the_toolbar_starts_restored(overlay):
    toolbar = overlay._toolbar
    assert not overlay.toolbar_collapsed and not toolbar.collapsed
    assert toolbar.body.isVisibleTo(toolbar)
    assert toolbar.collapse_button.toolTip() == "Minimize the drawing tools"


def test_minimize_leaves_a_small_title_bar_and_restore_brings_everything_back(overlay):
    toolbar = overlay._toolbar
    full = toolbar.size()
    top_left = toolbar.pos()
    toolbar.collapse_button.click()
    assert overlay.toolbar_collapsed and toolbar.collapsed
    assert not toolbar.body.isVisibleTo(toolbar)
    small = toolbar.size()
    assert small.height() < full.height() / 2
    assert small.width() < full.width()
    assert toolbar.pos() == top_left  # the top-left corner stays
    assert toolbar.collapse_button.toolTip() == "Restore the drawing tools"
    assert toolbar.close_cross.isVisibleTo(toolbar)
    toolbar.collapse_button.click()
    assert not overlay.toolbar_collapsed
    assert toolbar.body.isVisibleTo(toolbar)
    assert toolbar.size() == full


def test_the_shortcuts_work_while_minimized(overlay):
    overlay.set_toolbar_collapsed(True)
    overlay.set_tool(Tool.ARROW)
    overlay.toggle_sketch()
    assert overlay.tool is Tool.ARROW and overlay.sketch


def test_minimized_stays_for_the_next_drawing_of_the_same_recording(overlay, qtbot):
    overlay.set_toolbar_collapsed(True)
    overlay.leave()
    qtbot.waitUntil(lambda: not overlay.leaving, timeout=3000)
    overlay.show()
    assert overlay.toolbar_collapsed and overlay._toolbar.collapsed
    overlay.hide()
    overlay.show()
    assert overlay._toolbar.collapsed


def test_a_new_recording_starts_restored(overlay, qtbot):
    overlay.set_toolbar_collapsed(True)
    fresh = DrawingOverlay()  # the control window creates one per recording
    try:
        fresh.show()
        for window in fresh.windows:
            qtbot.addWidget(window)
        assert not fresh.toolbar_collapsed and not fresh._toolbar.collapsed
    finally:
        fresh.close()


def test_minimize_works_while_frozen(overlay):
    overlay.set_frozen(True)
    assert overlay._toolbar.collapse_button.isEnabled()
    overlay.toggle_toolbar_collapsed()
    assert overlay.toolbar_collapsed
