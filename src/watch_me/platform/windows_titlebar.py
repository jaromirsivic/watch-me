"""Dark or light title bars of windows on Windows (DWM, through ctypes).

The title bar of every Watch Me window contrasts with the theme: dark in the light
theme, light in the dark theme (:func:`title_bar_dark_for`). Qt alone follows the system
colour scheme, so the frame stayed light at start and turned dark only after the theme
was switched. :func:`set_title_bar_dark` sets ``DWMWA_USE_IMMERSIVE_DARK_MODE`` of one
window explicitly; elsewhere than on Windows it does nothing.
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)

DWMWA_USE_IMMERSIVE_DARK_MODE = 20  # Windows 10 20H1 and newer, Windows 11
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19  # Windows 10 1809 to 1909


def title_bar_dark_for(theme_dark: bool) -> bool:
    """The title bar contrasts with the theme: dark for the light theme and light for
    the dark one."""
    return not theme_dark


def set_title_bar_dark(hwnd: int, dark: bool) -> bool:
    """Make the title bar of the window ``hwnd`` dark (``True``) or light; ``False``
    when it cannot be done (not Windows, no such attribute, no window)."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        dwmapi = ctypes.windll.dwmapi
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
            result = dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                wintypes.DWORD(attribute),
                ctypes.byref(value),
                wintypes.DWORD(ctypes.sizeof(value)),
            )
            if result == 0:  # S_OK
                return True
    except (AttributeError, OSError) as exc:
        log.debug("cannot set the title bar colour: %s", exc)
    return False


__all__ = [
    "DWMWA_USE_IMMERSIVE_DARK_MODE",
    "DWMWA_USE_IMMERSIVE_DARK_MODE_OLD",
    "set_title_bar_dark",
    "title_bar_dark_for",
]
