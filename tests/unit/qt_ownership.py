"""Finds Qt objects that Python owns although Qt gave them a parent.

Such an object is deleted twice when Python's cyclic collector frees it together with
its parent off the GUI thread (see ``watch_me.editor.workers``). A widget ends up like
that when it is put into a layout that has no widget yet: Qt makes it a child of the
window once the layout is attached, but PySide does not hand its ownership over.

The objects are found through the collector's own list. ``QObject.findChildren`` must
not be used for this: PySide hands ownership to C++ for everything it returns, so a
check made through it always passes.
"""

from __future__ import annotations

import gc

import shiboken6
from PySide6.QtCore import QObject


def owned_by_python_under(root: QObject) -> list[str]:
    """Descriptions of the objects below ``root`` that Python still owns."""
    found = []
    for candidate in gc.get_objects():
        if not isinstance(candidate, QObject) or not shiboken6.isValid(candidate):
            continue
        if candidate is root or not shiboken6.ownedByPython(candidate):
            continue
        parent = candidate.parent()
        while parent is not None and parent is not root:
            parent = parent.parent()
        if parent is root:
            found.append(_describe(candidate))
    return sorted(found)


def _describe(item: QObject) -> str:
    text = ""
    for name in ("text", "title", "toolTip"):
        getter = getattr(item, name, None)
        if callable(getter):
            text = str(getter())
            if text:
                break
    return f"{type(item).__name__} {item.objectName() or text!r}"
