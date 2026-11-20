"""The index of a recording: what was on the screens at every tick, in one file.

``frames_info/index.jsonl`` is JSON Lines. The first line is a header; every further
line is one capture tick and holds its time ``t`` and only what changed since the tick
before it:

``cursor``       ``{screen, x, y}`` or null (outside every screen)
``shapes``       finished shapes that are new or changed, each with all its geometry -
                 a shape is written once, however long it stays on the screen
``visible``      the ids of the finished shapes on the screens, in drawing order
``drawing_now``  the shape being drawn (no geometry) or null
``zoom``         the magnified regions of the drawing canvas
``background``   ``screen`` / ``sketch`` / null (not drawing)
``grid``         ``{screen id: spacing}`` while the points snap to a grid, else null
`grid_source`  `toggle` / `ctrl` / null
`pass_through` true (the live screens show through the drawing layer) / false /
                 null (not drawing)
``clipboard``    a text copied since the tick before - in that one tick only
``failed``       the screens that could not be grabbed at this tick - never carried on

A tick at which nothing changed is ``{"t": 12500}``. The images are not listed here:
the image of a screen at a time is the latest file in ``frames/`` at or before it.

The recorder appends a line per tick from its capture thread (:class:`TickIndexWriter`)
and flushes it; a reader skips a last line that was cut off (:class:`TickIndex`).
"""

from __future__ import annotations

import bisect
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

log = logging.getLogger(__name__)

INDEX_NAME = "index.jsonl"
INDEX_VERSION = 3
INDEX_KIND = "watch-me tick index"
NO_INDEX = "NO_INDEX"

# State that stays as it is until a line says otherwise, and what it is before the first.
_CARRIED: dict[str, Any] = {
    "cursor": None,
    "drawing_now": None,
    "zoom": [],
    "background": None,
    "grid": None,
    "grid_source": None,
    "pass_through": None,
}


class NoIndexError(RuntimeError):
    """The recording has no ``index.jsonl`` (made by an older version, or damaged)."""

    code = NO_INDEX

    def __init__(self, path: Path) -> None:
        super().__init__(
            f"the recording has no index ({path}): it was made by an older version of "
            "Watch Me or is damaged"
        )
        self.path = path


def index_path(info_dir: Path) -> Path:
    return info_dir / INDEX_NAME


@dataclass(slots=True)
class TickState:
    """Everything known about one tick (the values are shared between ticks: read only)."""

    time_ms: int
    cursor: dict[str, Any] | None = None
    drawings: list[dict[str, Any]] = field(default_factory=list)
    drawing_now: dict[str, Any] | None = None
    zoom: list[dict[str, Any]] = field(default_factory=list)
    background: str | None = None
    grid: dict[str, int] | None = None
    grid_source: str | None = None
    pass_through: bool | None = None
    clipboard: str | None = None
    failed: tuple[str, ...] = ()

    def for_screen(self, screen_id: str) -> dict[str, Any]:
        """The state as seen from one screen: ``grid`` is that screen's spacing."""
        grid = (self.grid or {}).get(screen_id)
        return {
            "time_ms": self.time_ms,
            "screen": screen_id,
            "cursor": self.cursor,
            "drawings": self.drawings,
            "drawing_now": self.drawing_now,
            "zoom": self.zoom,
            "background": self.background,
            "grid": grid,
            "grid_source": self.grid_source if self.grid else None,
            "pass_through": self.pass_through,
            "clipboard": self.clipboard,
        }


class TickIndexWriter:
    """Appends one line per tick; not thread safe (the capture thread owns it)."""

    def __init__(self, path: Path, header: dict[str, Any] | None = None) -> None:
        self.path = path
        self.ticks = 0
        self._carried: dict[str, Any] = dict(_CARRIED)
        self._shapes: dict[Any, dict[str, Any]] = {}
        self._visible: list[Any] = []
        self._drawings: list[dict[str, Any]] | None = None  # shapes without ids
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file: TextIO | None = open(path, "w", encoding="utf-8", newline="\n")  # noqa: SIM115
        self._line({"v": INDEX_VERSION, "kind": INDEX_KIND, **(header or {})})

    def _line(self, data: dict[str, Any]) -> None:
        assert self._file is not None
        self._file.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._file.flush()

    def write(
        self,
        time_ms: int,
        *,
        cursor: dict[str, Any] | None = None,
        drawings: list[dict[str, Any]] | None = None,
        drawing_now: dict[str, Any] | None = None,
        zoom: list[dict[str, Any]] | None = None,
        background: str | None = None,
        grid: dict[str, int] | None = None,
        grid_source: str | None = None,
        pass_through: bool | None = None,
        clipboard: str | None = None,
        failed: list[str] | tuple[str, ...] = (),
    ) -> None:
        """Append the tick at ``time_ms`` (``OSError`` when the file cannot be written)."""
        line: dict[str, Any] = {"t": int(time_ms)}
        grid = dict(grid) if grid else None
        state = {
            "cursor": cursor,
            "drawing_now": drawing_now,
            "zoom": list(zoom or []),
            "background": background,
            "grid": grid,
            "grid_source": grid_source if grid else None,
            "pass_through": pass_through,
        }
        for key, value in state.items():
            if value != self._carried[key]:
                line[key] = value
                self._carried[key] = value
        self._drawings_into(line, list(drawings or []))
        if clipboard is not None:
            line["clipboard"] = clipboard
        if failed:
            line["failed"] = list(failed)
        self._line(line)
        self.ticks += 1

    def _drawings_into(self, line: dict[str, Any], drawings: list[dict[str, Any]]) -> None:
        if not all(isinstance(shape, dict) and "id" in shape for shape in drawings):
            # Shapes that cannot be told apart: the whole list, when it changed.
            if drawings != self._drawings:
                line["drawings"] = drawings
                self._drawings = drawings
                self._visible = []
            return
        if self._drawings is not None:  # back from a list without ids
            self._drawings = None
            self._visible = []
            if not drawings:
                line["visible"] = []
        changed = []
        for shape in drawings:
            if self._shapes.get(shape["id"]) != shape:
                self._shapes[shape["id"]] = dict(shape)
                changed.append(shape)
        if changed:
            line["shapes"] = changed
        visible = [shape["id"] for shape in drawings]
        if visible != self._visible:
            line["visible"] = visible
            self._visible = visible

    def close(self) -> None:
        file, self._file = self._file, None
        if file is not None:
            file.close()


class TickIndex:
    """The ticks of a recording, read from ``index.jsonl`` in one pass."""

    def __init__(self, header: dict[str, Any], states: list[TickState]) -> None:
        self.header = header
        self.states = states
        self.times = [state.time_ms for state in states]

    @classmethod
    def load(cls, info_dir: Path) -> TickIndex:
        """Read the index in ``info_dir`` (:class:`NoIndexError` when there is none)."""
        path = index_path(info_dir)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise NoIndexError(path) from None
        return cls.parse(text, str(path))

    @classmethod
    def parse(cls, text: str, name: str = INDEX_NAME) -> TickIndex:
        header: dict[str, Any] = {}
        states: list[TickState] = []
        carried: dict[str, Any] = dict(_CARRIED)
        shapes: dict[Any, dict[str, Any]] = {}
        drawings: list[dict[str, Any]] = []
        for number, raw in enumerate(text.split("\n"), start=1):
            if not raw.strip():
                continue
            try:
                line = json.loads(raw)
            except ValueError:
                # The last line of a recording that ended abruptly; anywhere else the
                # tick is lost, the ticks around it are not.
                log.warning("%s: line %d cannot be read, skipped", name, number)
                continue
            if not isinstance(line, dict):
                continue
            if "t" not in line:
                if not states and not header:
                    header = line
                continue
            for key in _CARRIED:
                if key in line:
                    carried[key] = line[key]
            if "drawings" in line:
                drawings = list(line["drawings"] or [])
            else:
                for shape in line.get("shapes") or []:
                    if isinstance(shape, dict) and "id" in shape:
                        shapes[shape["id"]] = shape
                if "visible" in line:
                    drawings = [shapes[i] for i in line["visible"] or [] if i in shapes]
                elif line.get("shapes"):
                    # A shape on the screen changed: the list holds the new one.
                    drawings = [shapes.get(shape.get("id"), shape) for shape in drawings]
            states.append(
                TickState(
                    time_ms=int(line["t"]),
                    cursor=carried["cursor"],
                    drawings=drawings,
                    drawing_now=carried["drawing_now"],
                    zoom=carried["zoom"] or [],
                    background=carried["background"],
                    grid=carried["grid"],
                    grid_source=carried["grid_source"],
                    pass_through=carried["pass_through"],
                    clipboard=line.get("clipboard"),
                    failed=tuple(line.get("failed") or ()),
                )
            )
        states.sort(key=lambda state: state.time_ms)
        return cls(header, states)

    # The header --------------------------------------------------------------

    @property
    def screens(self) -> list[str]:
        return [str(s) for s in self.header.get("screens") or []]

    @property
    def interval_ms(self) -> int | None:
        value = self.header.get("interval_ms")
        return int(value) if isinstance(value, int | float) else None

    # Ticks ---------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.states)

    def position(self, time_ms: int) -> int | None:
        """Index of the latest tick at or before ``time_ms`` (``None``: before the first)."""
        found = bisect.bisect_right(self.times, time_ms) - 1
        return found if found >= 0 else None

    def at(self, time_ms: int) -> TickState | None:
        """The latest tick at or before ``time_ms``; the first tick for an earlier time
        (``None`` only when the recording has no tick at all)."""
        if not self.states:
            return None
        found = self.position(time_ms)
        return self.states[found if found is not None else 0]

    def exact(self, time_ms: int) -> TickState | None:
        """The tick at exactly ``time_ms``."""
        found = self.position(time_ms)
        if found is not None and self.times[found] == time_ms:
            return self.states[found]
        return None

    def clipboard_changes(self) -> list[tuple[int, str]]:
        """``(time_ms, text)`` of every tick that carries a copied text."""
        return [(s.time_ms, s.clipboard) for s in self.states if s.clipboard is not None]

    def owner(self, state: TickState) -> str | None:
        """The screen a tick is read through where one screen stands for all: the first
        one that was grabbed at that tick."""
        for screen_id in self.screens:
            if screen_id not in state.failed:
                return screen_id
        return None


__all__ = [
    "INDEX_KIND",
    "INDEX_NAME",
    "INDEX_VERSION",
    "NO_INDEX",
    "NoIndexError",
    "TickIndex",
    "TickIndexWriter",
    "TickState",
    "index_path",
]
