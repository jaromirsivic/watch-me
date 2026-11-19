"""Light / dark theme of the editor window (the button above **Edit** toggles it).

The recorder and the editor share one theme, ``theme`` in ``config.json`` (light by
default): the recorder's Settings and the editor's sun / moon button change it. It is
applied to the whole application with the Fusion style and a palette built here.

The title bars of the windows contrast with the theme (Windows): dark in the light
theme, light in the dark one, from the moment a window opens (:class:`TitleBars`); once
a window is on screen the DWM is made to draw its title bar anew, so that the caption
buttons (Minimize, Maximize, Close) are drawn in the colour of the bar they sit on.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from watch_me.platform.windows_titlebar import set_title_bar_dark, title_bar_dark_for

DARK = "dark"
LIGHT = "light"
PROCESS_GREEN = "#1e9e3e"  # the Process button; the open padlock in the light theme


def system_prefers_dark(app: QApplication | None = None) -> bool:
    """True when the palette Qt started with is a dark one."""
    app = app or QApplication.instance()  # type: ignore[assignment]
    if app is None:
        return True
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def dark_palette() -> QPalette:
    p = QPalette()
    window = QColor("#2b2b2b")
    base = QColor("#1f1f1f")
    text = QColor("#e6e6e6")
    disabled = QColor("#7a7a7a")
    highlight = QColor("#3b7dd8")
    for group in (
        QPalette.ColorGroup.Active,
        QPalette.ColorGroup.Inactive,
        QPalette.ColorGroup.Disabled,
    ):
        p.setColor(group, QPalette.ColorRole.Window, window)
        p.setColor(group, QPalette.ColorRole.WindowText, text)
        p.setColor(group, QPalette.ColorRole.Base, base)
        p.setColor(group, QPalette.ColorRole.AlternateBase, QColor("#262626"))
        p.setColor(group, QPalette.ColorRole.ToolTipBase, QColor("#3a3a3a"))
        p.setColor(group, QPalette.ColorRole.ToolTipText, text)
        p.setColor(group, QPalette.ColorRole.Text, text)
        p.setColor(group, QPalette.ColorRole.PlaceholderText, disabled)
        p.setColor(group, QPalette.ColorRole.Button, QColor("#3a3a3a"))
        p.setColor(group, QPalette.ColorRole.ButtonText, text)
        p.setColor(group, QPalette.ColorRole.BrightText, QColor("#ff6060"))
        p.setColor(group, QPalette.ColorRole.Highlight, highlight)
        p.setColor(group, QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        p.setColor(group, QPalette.ColorRole.Link, QColor("#6ea8ff"))
        p.setColor(group, QPalette.ColorRole.Light, QColor("#4a4a4a"))
        p.setColor(group, QPalette.ColorRole.Midlight, QColor("#404040"))
        p.setColor(group, QPalette.ColorRole.Mid, QColor("#353535"))
        p.setColor(group, QPalette.ColorRole.Dark, QColor("#1a1a1a"))
        p.setColor(group, QPalette.ColorRole.Shadow, QColor("#101010"))
    dis = QPalette.ColorGroup.Disabled
    p.setColor(dis, QPalette.ColorRole.WindowText, disabled)
    p.setColor(dis, QPalette.ColorRole.Text, disabled)
    p.setColor(dis, QPalette.ColorRole.ButtonText, disabled)
    p.setColor(dis, QPalette.ColorRole.Highlight, QColor("#505050"))
    p.setColor(dis, QPalette.ColorRole.HighlightedText, disabled)
    return p


def light_palette() -> QPalette:
    p = QPalette()
    window = QColor("#f3f3f3")
    base = QColor("#ffffff")
    text = QColor("#1e1e1e")
    disabled = QColor("#9a9a9a")
    highlight = QColor("#2f6fd0")
    for group in (
        QPalette.ColorGroup.Active,
        QPalette.ColorGroup.Inactive,
        QPalette.ColorGroup.Disabled,
    ):
        p.setColor(group, QPalette.ColorRole.Window, window)
        p.setColor(group, QPalette.ColorRole.WindowText, text)
        p.setColor(group, QPalette.ColorRole.Base, base)
        p.setColor(group, QPalette.ColorRole.AlternateBase, QColor("#f7f7f7"))
        p.setColor(group, QPalette.ColorRole.ToolTipBase, QColor("#ffffdc"))
        p.setColor(group, QPalette.ColorRole.ToolTipText, text)
        p.setColor(group, QPalette.ColorRole.Text, text)
        p.setColor(group, QPalette.ColorRole.PlaceholderText, disabled)
        p.setColor(group, QPalette.ColorRole.Button, QColor("#e9e9e9"))
        p.setColor(group, QPalette.ColorRole.ButtonText, text)
        p.setColor(group, QPalette.ColorRole.BrightText, QColor("#d02020"))
        p.setColor(group, QPalette.ColorRole.Highlight, highlight)
        p.setColor(group, QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        p.setColor(group, QPalette.ColorRole.Link, QColor("#1f5fc0"))
        p.setColor(group, QPalette.ColorRole.Light, QColor("#ffffff"))
        p.setColor(group, QPalette.ColorRole.Midlight, QColor("#f0f0f0"))
        p.setColor(group, QPalette.ColorRole.Mid, QColor("#c8c8c8"))
        p.setColor(group, QPalette.ColorRole.Dark, QColor("#a0a0a0"))
        p.setColor(group, QPalette.ColorRole.Shadow, QColor("#707070"))
    dis = QPalette.ColorGroup.Disabled
    p.setColor(dis, QPalette.ColorRole.WindowText, disabled)
    p.setColor(dis, QPalette.ColorRole.Text, disabled)
    p.setColor(dis, QPalette.ColorRole.ButtonText, disabled)
    p.setColor(dis, QPalette.ColorRole.Highlight, QColor("#c8c8c8"))
    p.setColor(dis, QPalette.ColorRole.HighlightedText, disabled)
    return p


def apply_theme(dark: bool, app: QApplication | None = None) -> None:
    """Switch the whole application to the dark or the light palette, and every title
    bar to the contrasting colour (see :class:`TitleBars`)."""
    app = app or QApplication.instance()  # type: ignore[assignment]
    if app is None:
        return
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")  # the only style that honours a custom palette everywhere
    app.setPalette(dark_palette() if dark else light_palette())
    TitleBars.install(app).update_all()


# Title bars ---------------------------------------------------------------------

# Windows that have no title bar of their own: menus, tooltips, the drawing overlay.
_NO_TITLE_BAR = (
    Qt.WindowType.Popup,
    Qt.WindowType.ToolTip,
    Qt.WindowType.SplashScreen,
    Qt.WindowType.Desktop,
)
_TITLE_BAR_EVENTS = (
    QEvent.Type.Show,
    QEvent.Type.WinIdChange,
    QEvent.Type.ThemeChange,
    QEvent.Type.ApplicationPaletteChange,
)
# When the DWM draws a shown window's title bar anew (ms after the Show event). It must
# happen after the window was first drawn on screen: done at once it changed nothing,
# done 50 ms to 1 s later it repaired the bar every time (measured on Windows 11 with
# the maximized editor, 2026-11-17). The second time is for a slow start.
REDRAW_AFTER_SHOW_MS = (150, 1000)


class TitleBars(QObject):
    """Keeps the title bar of every top-level window in the colour that contrasts with
    the theme: dark in the light theme, light in the dark one (Windows only; elsewhere
    the window manager draws the frame).

    An event filter on the application sets it when a window is shown or gets its
    native handle, and again after Qt handled the event (Qt follows the system colour
    scheme and would otherwise overwrite it); shortly after a Show the DWM is also made
    to draw the title bar anew. :func:`apply_theme` installs it and updates the windows
    already open.
    """

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._app = app

    @classmethod
    def install(cls, app: QApplication) -> TitleBars:
        existing = app.findChild(TitleBars)
        if existing is not None:
            return existing
        bars = cls(app)
        app.installEventFilter(bars)
        return bars

    @property
    def dark(self) -> bool:
        """True for a dark title bar (the light theme is on)."""
        return title_bar_dark_for(system_prefers_dark(self._app))

    def update_all(self) -> None:
        """Every open window now, and once more after Qt handled the change."""
        for widget in self._app.topLevelWidgets():
            self.update_window(widget)
        QTimer.singleShot(0, self._update_all_now)

    def _update_all_now(self) -> None:
        for widget in self._app.topLevelWidgets():
            self.update_window(widget)

    def update_window(self, widget: QWidget, redraw: bool = False) -> bool:
        """Set the title bar of ``widget``; False when it has none or is not created.
        ``redraw`` makes the DWM draw it anew (see ``set_title_bar_dark``)."""
        if not widget.isWindow() or widget.windowType() in _NO_TITLE_BAR:
            return False
        if widget.windowFlags() & Qt.WindowType.FramelessWindowHint:
            return False
        if not widget.testAttribute(Qt.WidgetAttribute.WA_WState_Created):
            return False  # no native window yet: set when it is shown
        return set_title_bar_dark(int(widget.winId()), self.dark, redraw=redraw)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() in _TITLE_BAR_EVENTS and isinstance(watched, QWidget):
            if watched.isWindow():
                self.update_window(watched)
                # Set ours once more after Qt handled the event: Qt may set its own
                # colour meanwhile.
                QTimer.singleShot(0, lambda w=watched: self._update_later(w))
                if event.type() == QEvent.Type.Show:
                    # Once the window is on screen, make the DWM draw its title bar
                    # anew: a maximized editor in the light theme often got a light bar
                    # with white buttons. Right after Show is too early; see
                    # REDRAW_AFTER_SHOW_MS.
                    for delay in REDRAW_AFTER_SHOW_MS:
                        QTimer.singleShot(delay, lambda w=watched: self._update_later(w, True))
        return False

    def _update_later(self, widget: QWidget, redraw: bool = False) -> None:
        try:
            self.update_window(widget, redraw=redraw)
        except RuntimeError:  # the widget was deleted meanwhile
            pass


__all__ = [
    "DARK",
    "LIGHT",
    "REDRAW_AFTER_SHOW_MS",
    "TitleBars",
    "apply_theme",
    "dark_palette",
    "light_palette",
    "system_prefers_dark",
]
