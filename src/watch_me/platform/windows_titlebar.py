"""Dark or light title bars of windows on Windows (DWM, through ctypes).

The title bar of every Watch Me window contrasts with the theme: dark in the light
theme, light in the dark theme (:func:`title_bar_dark_for`). Qt alone follows the system
colour scheme, so the frame stayed light at start and turned dark only after the theme
was switched. :func:`set_title_bar_dark` sets ``DWMWA_USE_IMMERSIVE_DARK_MODE`` of one
window explicitly; elsewhere than on Windows it does nothing.

The DWM does not always draw what the attribute says. Now and then a window that opens
maximized shows a light title bar with white Minimize, Maximize and Close buttons on it
(they cannot be seen) although the attribute reads dark. Setting the same value again,
``SWP_FRAMECHANGED``, ``RedrawWindow`` with ``RDW_FRAME``, ``WM_NCACTIVATE`` or a change
of the z-order do not repaint it; only a real change of the value does. So ``redraw``
(once after a window is shown, see ``TitleBars``) sets the opposite value and the wanted
one right after it (measured on Windows 11, user's report 2026-11-17).
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)

DWMWA_USE_IMMERSIVE_DARK_MODE = 20  # Windows 10 20H1 and newer, Windows 11
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19  # Windows 10 1809 to 1909

_warned: set[int] = set()  # windows whose refusal is in the log already


def title_bar_dark_for(theme_dark: bool) -> bool:
    """The title bar contrasts with the theme: dark for the light theme and light for
    the dark one."""
    return not theme_dark


def _api():
    """``(dwmapi, user32)``; a function so that tests can replace them."""
    import ctypes

    return ctypes.windll.dwmapi, ctypes.windll.user32


def _set(dwmapi, hwnd: int, attribute: int, dark: bool) -> bool:
    import ctypes
    from ctypes import wintypes

    value = ctypes.c_int(1 if dark else 0)
    result = dwmapi.DwmSetWindowAttribute(
        wintypes.HWND(hwnd),
        wintypes.DWORD(attribute),
        ctypes.byref(value),
        wintypes.DWORD(ctypes.sizeof(value)),
    )
    return result == 0  # S_OK


def set_title_bar_dark(hwnd: int, dark: bool, redraw: bool = False) -> bool:
    """Make the title bar of the window ``hwnd`` dark (``True``) or light; ``False``
    when it cannot be done (not Windows, no such attribute, no window).

    ``redraw`` makes the DWM draw a window that is on screen anew: the value goes to
    the opposite one and back (see the module docstring)."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        from ctypes import wintypes

        dwmapi, user32 = _api()
        for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
            if not _set(dwmapi, hwnd, attribute, dark):
                continue  # try the attribute of older Windows 10
            if redraw and user32.IsWindowVisible(wintypes.HWND(hwnd)):
                _set(dwmapi, hwnd, attribute, not dark)
                _set(dwmapi, hwnd, attribute, dark)
            return True
        if hwnd not in _warned:  # once per window, not for every theme event
            _warned.add(hwnd)
            log.warning("cannot set the title bar colour of window %s (DWM refused)", hwnd)
    except (AttributeError, OSError) as exc:
        log.debug("cannot set the title bar colour: %s", exc)
    return False


__all__ = [
    "DWMWA_USE_IMMERSIVE_DARK_MODE",
    "DWMWA_USE_IMMERSIVE_DARK_MODE_OLD",
    "set_title_bar_dark",
    "title_bar_dark_for",
]
