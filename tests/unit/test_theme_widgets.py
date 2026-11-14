"""Title bars that contrast with the theme, the thicker separator line and the outlined
check box (Auto process)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QWidget  # noqa: E402

from watch_me.editor import theme  # noqa: E402
from watch_me.editor.separators import SEPARATOR_LINE_HEIGHT, SeparatorLine  # noqa: E402
from watch_me.platform.windows_titlebar import (  # noqa: E402
    set_title_bar_dark,
    title_bar_dark_for,
)
from watch_me.ui.widgets import OutlinedCheckBox  # noqa: E402


@pytest.fixture
def restore_theme(qapp):
    palette, style = qapp.palette(), qapp.style().objectName()
    yield
    qapp.setStyle(style)
    qapp.setPalette(palette)


@pytest.fixture
def title_bars(monkeypatch):
    """The calls to the DWM: (window handle, dark)."""
    calls: list[tuple[int, bool]] = []
    monkeypatch.setattr(
        theme, "set_title_bar_dark", lambda hwnd, dark: calls.append((hwnd, dark)) or True
    )
    return calls


def test_title_bar_contrasts_with_the_theme():
    assert title_bar_dark_for(False) is True  # light theme: dark title bar
    assert title_bar_dark_for(True) is False  # dark theme: light title bar


def test_set_title_bar_dark_needs_a_window():
    assert set_title_bar_dark(0, True) is False


@pytest.mark.usefixtures("restore_theme")
def test_title_bars_follow_the_theme_from_the_first_show(qtbot, title_bars):
    theme.apply_theme(False)
    dialog = QDialog()
    qtbot.addWidget(dialog)
    dialog.show()  # dark at once in the light theme
    hwnd = int(dialog.winId())
    assert (hwnd, True) in title_bars
    title_bars.clear()
    theme.apply_theme(True)  # every open window switches to the light title bar
    assert (hwnd, False) in title_bars
    qtbot.waitUntil(lambda: title_bars.count((hwnd, False)) >= 2, timeout=1000)  # and after Qt
    assert (hwnd, True) not in title_bars
    title_bars.clear()
    theme.apply_theme(False)
    assert (hwnd, True) in title_bars


@pytest.mark.usefixtures("restore_theme")
def test_windows_without_a_title_bar_are_left_alone(qtbot, title_bars):
    theme.apply_theme(False)
    bars = QApplication.instance().findChild(theme.TitleBars)
    assert bars is not None and bars is theme.TitleBars.install(QApplication.instance())
    menu = QMenu()
    frameless = QWidget(None, Qt.WindowType.FramelessWindowHint)
    hidden = QWidget()  # never shown: no native window yet
    for widget in (menu, frameless, hidden):
        qtbot.addWidget(widget)
    frameless.show()
    assert bars.update_window(menu) is False
    assert bars.update_window(frameless) is False
    assert bars.update_window(hidden) is False
    assert int(frameless.winId()) not in [hwnd for hwnd, _ in title_bars]


def test_thicker_separator_line(qtbot):
    thin, thick = SeparatorLine(), SeparatorLine(thickness=3)
    for widget in (thin, thick):
        qtbot.addWidget(widget)
        widget.resize(40, widget.height())
    assert thin.thickness == 1 and thin.height() == SEPARATOR_LINE_HEIGHT
    assert thick.thickness == 3 and thick.height() >= 5

    def painted_rows(widget: SeparatorLine) -> int:
        image = widget.grab().toImage()
        background = image.pixelColor(20, 0)
        return sum(image.pixelColor(20, y) != background for y in range(image.height()))

    assert painted_rows(thin) == 1
    assert painted_rows(thick) == 3


@pytest.mark.usefixtures("restore_theme")
@pytest.mark.parametrize("dark", [False, True])
def test_outlined_check_box_uses_the_text_colour(qtbot, dark):
    theme.apply_theme(dark)
    box = OutlinedCheckBox("Auto process")
    qtbot.addWidget(box)
    box.show()
    ink = QApplication.palette().color(QPalette.ColorRole.WindowText)
    assert box.outline_color() == ink
    image = box.grab().toImage()
    rect = box.indicator_rect()
    y = int(rect.center().y())
    # The outline (antialiased) across the box's left edge: its strongest pixel.
    edge = min(
        (image.pixelColor(x, y) for x in range(int(rect.left()), int(rect.left()) + 4)),
        key=lambda c: abs(c.lightness() - ink.lightness()),
    )
    assert abs(edge.lightness() - ink.lightness()) < 40, (edge.name(), ink.name())
    background = QColor(QApplication.palette().color(QPalette.ColorRole.Window))
    assert abs(edge.lightness() - background.lightness()) > 100
