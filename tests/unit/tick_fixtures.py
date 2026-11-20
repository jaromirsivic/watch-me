"""Writes the tick index of a test recording.

Test recordings describe a tick the way a frame's sidecar used to: one dict per screen
with ``cursor``, ``drawings``, ``drawing_now``, ``zoom``, ``background``, ``grid``
(that screen's spacing), ``grid_source`` and ``clipboard``. :class:`IndexBuilder`
collects those dicts and writes them as ``frames_info/index.jsonl``, the one file a
recording keeps them in (:mod:`watch_me.core.tick_index`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from watch_me.core.tick_index import TickIndexWriter, index_path


def _screen_order(screen_id: str) -> int:
    digits = "".join(ch for ch in screen_id if ch.isdigit())
    return int(digits) if digits else 0


class IndexBuilder:
    """Collects what each screen showed at each tick; :meth:`write` stores the index."""

    def __init__(
        self,
        info_dir: Path,
        *,
        interval_ms: int = 500,
        image_format: str = "png",
        screens: list[str] | None = None,
    ) -> None:
        self.info_dir = info_dir
        self.interval_ms = interval_ms
        self.image_format = image_format
        self.screens = screens
        self._ticks: dict[int, dict[str, dict[str, Any]]] = {}

    def add(self, time_ms: int, screen: str, data: dict[str, Any] | None = None) -> None:
        """What ``screen`` showed at ``time_ms`` (the keys of a sidecar; all optional)."""
        self._ticks.setdefault(int(time_ms), {})[screen] = dict(data or {})

    def write(self) -> Path:
        """Write ``index.jsonl``; a screen without an entry at a tick counts as not
        grabbed there (``failed``)."""
        seen = {screen for by_screen in self._ticks.values() for screen in by_screen}
        screens = self.screens or sorted(seen, key=_screen_order)
        path = index_path(self.info_dir)
        writer = TickIndexWriter(
            path,
            {
                "interval_ms": self.interval_ms,
                "image_format": self.image_format,
                "screens": screens,
            },
        )
        for time_ms in sorted(self._ticks):
            by_screen = self._ticks[time_ms]
            present = [screen for screen in screens if screen in by_screen]
            first = by_screen[present[0]] if present else {}
            grid = {
                screen: by_screen[screen]["grid"]
                for screen in present
                if isinstance(by_screen[screen].get("grid"), int)
            }
            writer.write(
                time_ms,
                cursor=first.get("cursor"),
                drawings=first.get("drawings") or [],
                drawing_now=first.get("drawing_now"),
                zoom=first.get("zoom") or [],
                background=first.get("background"),
                grid=grid or None,
                grid_source=first.get("grid_source"),
                pass_through=first.get("pass_through"),
                clipboard=first.get("clipboard"),
                failed=[screen for screen in screens if screen not in by_screen],
            )
        writer.close()
        return path


__all__ = ["IndexBuilder"]
