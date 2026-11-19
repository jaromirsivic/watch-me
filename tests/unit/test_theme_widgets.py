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
def dwm_calls(monkeypatch):
    """The calls to the DWM, twice: (window handle, dark) and (handle, dark, redraw)."""
    pairs: list[tuple[int, bool]] = []
    triples: list[tuple[int, bool, bool]] = []

    def record(hwnd, dark, redraw=False):
        pairs.append((hwnd, dark))
        triples.append((hwnd, dark, redraw))
        return True

    monkeypatch.setattr(theme, "set_title_bar_dark", record)
    return pairs, triples


@pytest.fixture
def title_bars(dwm_calls):
    """The calls to the DWM: (window handle, dark)."""
    return dwm_calls[0]


@pytest.fixture
def redraws(dwm_calls):
    """The calls to the DWM: (window handle, dark, redraw)."""
    return dwm_calls[1]


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
def test_title_bar_is_drawn_anew_after_the_window_is_on_screen(qtbot, redraws):
    """The DWM may draw a light bar with white buttons although the value reads dark:
    shortly after Show (not at once, that is too early) it is made to draw the bar anew."""
    assert theme.REDRAW_AFTER_SHOW_MS[0] > 0
    theme.apply_theme(False)
    dialog = QDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    hwnd = int(dialog.winId())
    assert (hwnd, True, False) in redraws and (hwnd, True, True) not in redraws  # at once
    wanted = len(theme.REDRAW_AFTER_SHOW_MS)
    timeout = max(theme.REDRAW_AFTER_SHOW_MS) + 2000
    qtbot.waitUntil(lambda: redraws.count((hwnd, True, True)) == wanted, timeout=timeout)
    assert all(dark for h, dark, _ in redraws if h == hwnd)
    redraws.clear()
    theme.apply_theme(True)  # a theme switch changes the value: the DWM draws it anyway
    qtbot.waitUntil(lambda: redraws.count((hwnd, False, False)) >= 2, timeout=1000)
    assert (hwnd, False, True) not in redraws


class _FakeDwm:
    """DwmSetWindowAttribute of one window and IsWindowVisible."""

    def __init__(self, visible: bool = True, refuse=()):
        self.visible = visible
        self.refuse = set(refuse)
        self.values: list[tuple[int, bool]] = []  # (attribute, dark) in the order set

    def DwmSetWindowAttribute(self, hwnd, attribute, pointer, size):  # noqa: N802
        if attribute.value in self.refuse:
            return 1
        self.values.append((attribute.value, bool(pointer._obj.value)))
        return 0

    def IsWindowVisible(self, hwnd):  # noqa: N802
        return self.visible


@pytest.fixture
def fake_dwm(monkeypatch):
    from watch_me.platform import windows_titlebar as wt

    def install(**kwargs) -> _FakeDwm:
        fake = _FakeDwm(**kwargs)
        monkeypatch.setattr(wt.sys, "platform", "win32")
        monkeypatch.setattr(wt, "_api", lambda: (fake, fake))
        monkeypatch.setattr(wt, "_warned", set())
        return fake

    return install


@pytest.mark.parametrize(
    "dark, visible, redraw, values",
    [
        (True, True, False, [True]),  # a plain set
        (True, True, True, [True, False, True]),  # on screen: the opposite and back
        (False, True, True, [False, True, False]),
        (True, False, True, [True]),  # not on screen yet: nothing to draw anew
    ],
)
def test_set_title_bar_dark_draws_the_bar_anew_on_request(fake_dwm, dark, visible, redraw, values):
    from watch_me.platform import windows_titlebar as wt

    fake = fake_dwm(visible=visible)
    assert wt.set_title_bar_dark(1234, dark, redraw=redraw) is True
    assert fake.values == [(wt.DWMWA_USE_IMMERSIVE_DARK_MODE, v) for v in values]


def test_set_title_bar_dark_falls_back_and_logs_a_refusal_once(fake_dwm, caplog):
    from watch_me.platform import windows_titlebar as wt

    fake = fake_dwm(refuse={wt.DWMWA_USE_IMMERSIVE_DARK_MODE})
    assert wt.set_title_bar_dark(1, True) is True  # Windows 10 1809-1909: the old attribute
    assert fake.values == [(wt.DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, True)]
    fake.refuse.add(wt.DWMWA_USE_IMMERSIVE_DARK_MODE_OLD)
    with caplog.at_level("WARNING", logger=wt.__name__):
        assert wt.set_title_bar_dark(2, True) is False
        assert wt.set_title_bar_dark(2, False) is False
    assert [r.getMessage() for r in caplog.records] == [
        "cannot set the title bar colour of window 2 (DWM refused)"
    ]


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
