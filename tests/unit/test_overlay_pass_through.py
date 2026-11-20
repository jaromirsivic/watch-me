"""Drawing layer: the Pass through button (P) and what the layer shows (offscreen Qt)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QPixmap  # noqa: E402

from watch_me.ui.overlay import MIN_ZOOM, DrawingOverlay  # noqa: E402

START = QColor("#123456")  # the screen as it was when drawing started
LIVE = QColor("#00AA00")  # the live screen grabbed when zooming in


def _filled(window, color: QColor) -> QPixmap:
    pixmap = QPixmap(window.size())
    pixmap.fill(color)
    return pixmap


@pytest.fixture
def overlay(qtbot):
    overlay = DrawingOverlay()
    overlay.show()
    for window in overlay.windows:
        qtbot.addWidget(window)
        window.set_snapshot(_filled(window, START))
    toolbar = overlay._toolbar
    area = QGuiApplication.primaryScreen().geometry()
    toolbar.move(area.bottomRight() - QPoint(toolbar.width(), toolbar.height()))
    toolbar.user_moved = True
    overlay.grabs = []

    def grab(window):
        overlay.grabs.append(window.screen_index)
        return _filled(window, LIVE)

    overlay._live_grabber = grab
    yield overlay
    overlay.close()


def _shown(window) -> QColor:
    """The color painted in the middle of the window (no shapes there)."""
    image = window.grab().toImage()
    return image.pixelColor(image.width() // 2, image.height() // 2)


def _same(a: QColor, b: QColor) -> bool:
    return a.rgb() == b.rgb()


def test_on_by_default_and_the_live_screen_shows_at_100_percent(overlay):
    window = overlay.windows[0]
    assert overlay.pass_through and overlay._toolbar.pass_through_button.isChecked()
    assert overlay.pass_through_state() is True
    assert window.picture() is None
    assert _shown(window).alpha() <= 1  # nothing painted: the live desktop shows through
    assert overlay.grabs == []  # nothing grabbed at 100 %


def test_off_shows_the_start_picture(overlay):
    window = overlay.windows[0]
    overlay._toolbar.pass_through_button.click()
    assert not overlay.pass_through and not overlay._toolbar.pass_through_button.isChecked()
    assert overlay.pass_through_state() is False
    assert window.picture() is window._snapshot
    assert _same(_shown(window), START)


def test_zooming_in_freezes_the_live_screen_and_zooming_out_shows_it_live_again(overlay):
    window = overlay.windows[0]
    overlay.set_pass_through(True)
    window.set_zoom(2.0)
    assert overlay.grabs == [0] and window.has_live_snapshot()
    assert _same(_shown(window), LIVE)
    window.set_zoom(3.0)  # still zoomed: the same frozen picture
    assert overlay.grabs == [0]
    window.set_zoom(MIN_ZOOM)
    assert not window.has_live_snapshot() and window.picture() is None
    window.set_zoom(2.0)  # a new zoom freezes the screen as it is now
    assert overlay.grabs == [0, 0]


def test_releasing_pass_through_brings_back_the_start_picture(overlay):
    window = overlay.windows[0]
    overlay.set_pass_through(True)
    window.set_zoom(2.0)
    overlay.set_pass_through(False)
    assert not window.has_live_snapshot()
    assert window.zoom == 2.0  # the zoom and its region stay
    assert _same(_shown(window), START)
    window.set_zoom(MIN_ZOOM)
    assert _same(_shown(window), START)


def test_pressing_pass_through_while_zoomed_freezes_the_live_screen_at_once(overlay):
    window = overlay.windows[0]
    overlay.set_pass_through(False)
    window.set_zoom(2.0)
    assert overlay.grabs == [] and _same(_shown(window), START)
    overlay.set_pass_through(True)
    assert overlay.grabs == [0] and _same(_shown(window), LIVE)


def test_a_failed_live_grab_falls_back_to_the_start_picture(overlay):
    window = overlay.windows[0]
    overlay._live_grabber = lambda _window: None
    overlay.set_pass_through(True)
    window.set_zoom(2.0)
    assert window.zoom == 2.0 and _same(_shown(window), START)


def test_p_toggles_and_is_blocked_while_frozen(overlay):
    window = overlay.windows[0]
    shortcut = next(s for s in overlay._shortcuts if s.key().toString() == "P")
    shortcut.activated.emit()
    assert not overlay.pass_through
    blocked = []
    overlay.blocked.connect(lambda: blocked.append(True))
    overlay.set_frozen(True)
    assert not overlay._toolbar.pass_through_button.isEnabled()
    shortcut.activated.emit()
    assert not overlay.pass_through and blocked == [True]
    overlay.set_frozen(False)
    window.setFocus()
    shortcut.activated.emit()
    assert overlay.pass_through


def test_every_drawing_starts_with_pass_through_on(overlay, qtbot):
    overlay.set_pass_through(False)
    overlay.leave()
    assert overlay.pass_through_state() is None  # the index says "not drawing"
    qtbot.waitUntil(lambda: not overlay.leaving, timeout=3000)
    overlay.show()
    assert overlay.pass_through and overlay._toolbar.pass_through_button.isChecked()
    assert overlay.grabs == []  # back at 100 %: nothing frozen


def test_the_live_grab_holds_the_recorders_capture_lock(overlay, monkeypatch):
    window = overlay.windows[0]
    lock = threading.Lock()
    overlay.set_capture_lock(lock)
    held = []

    def grab_screen(_screen):
        held.append(lock.locked())
        return _filled(window, LIVE)

    monkeypatch.setattr(overlay, "_grab_screen", grab_screen)
    pixmap = overlay._grab_live_screen(window)
    assert pixmap is not None and held and all(held)
    assert not lock.locked()
    assert not overlay._grabbing_live


def test_the_layer_paints_nothing_while_the_live_screen_is_grabbed(overlay):
    window = overlay.windows[0]
    overlay.set_pass_through(False)  # the start picture is painted otherwise
    overlay._grabbing_live = True
    try:
        assert _shown(window).alpha() <= 1
    finally:
        overlay._grabbing_live = False
    assert _same(_shown(window), START)


def test_shortcut_context_is_application_wide(overlay):
    shortcut = next(s for s in overlay._shortcuts if s.key().toString() == "P")
    assert shortcut.context() == Qt.ShortcutContext.ApplicationShortcut
