"""The tick index: one line per tick holding only what changed, read back as the whole
state of every tick."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from watch_me.core.tick_index import (
    INDEX_NAME,
    INDEX_VERSION,
    NoIndexError,
    TickIndex,
    TickIndexWriter,
    index_path,
)

A = {"id": 1, "tool": "rectangle", "from": {"screen": "screen1", "x": 1, "y": 2}}
B = {"id": 2, "tool": "brush", "path": [{"screen": "screen1", "x": i, "y": i} for i in range(400)]}
CURSOR = {"screen": "screen1", "x": 10, "y": 20}
HEADER = {"interval_ms": 500, "image_format": "jpeg", "screens": ["screen1", "screen2"]}


def _ticks() -> list[dict]:
    """A recording in which everything changes at some point (what goes into the writer)."""
    base = dict(
        cursor=None,
        drawings=[],
        drawing_now=None,
        zoom=[],
        background=None,
        grid=None,
        grid_source=None,
        clipboard=None,
        failed=[],
    )
    now = {"tool": "brush", "color": "#FF0000", "screen": "screen1", "started_ms": 900}
    zoom = [{"screen": "screen1", "factor": 2.0}]
    steps = [
        {},
        {"cursor": CURSOR},
        {"cursor": CURSOR},  # nothing changed
        {"cursor": {**CURSOR, "x": 11}, "background": "screen", "drawing_now": now},
        {"cursor": {**CURSOR, "x": 11}, "background": "screen", "drawings": [A]},
        {"background": "sketch", "drawings": [A, B], "clipboard": "copied text"},
        {"background": "sketch", "drawings": [A, B], "zoom": zoom},
        {
            "background": "sketch",
            "drawings": [B],  # A erased
            "grid": {"screen1": 16, "screen2": 8},
            "grid_source": "toggle",
        },
        {"background": "sketch", "drawings": [A, B], "failed": ["screen2"]},  # A restored
        {"drawings": [], "clipboard": ""},  # everything cleared; an empty text was copied
    ]
    return [{"time_ms": 500 * i, **base, **step} for i, step in enumerate(steps)]


def _write(path: Path, ticks: list[dict]) -> TickIndexWriter:
    writer = TickIndexWriter(path, HEADER)
    for tick in ticks:
        writer.write(tick["time_ms"], **{k: v for k, v in tick.items() if k != "time_ms"})
    writer.close()
    return writer


def _as_written(state) -> dict:
    return {
        "time_ms": state.time_ms,
        "cursor": state.cursor,
        "drawings": state.drawings,
        "drawing_now": state.drawing_now,
        "zoom": state.zoom,
        "background": state.background,
        "grid": state.grid,
        "grid_source": state.grid_source,
        "clipboard": state.clipboard,
        "failed": list(state.failed),
    }


def test_what_was_written_is_read_back_as_the_whole_state_of_every_tick(tmp_path: Path):
    ticks = _ticks()
    writer = _write(index_path(tmp_path), ticks)
    index = TickIndex.load(tmp_path)
    assert writer.ticks == len(ticks) == len(index)
    assert [_as_written(state) for state in index.states] == ticks
    assert index.times == [tick["time_ms"] for tick in ticks]
    assert index.header["v"] == INDEX_VERSION
    assert index.screens == ["screen1", "screen2"] and index.interval_ms == 500


def test_a_line_holds_only_what_changed(tmp_path: Path):
    _write(index_path(tmp_path), _ticks())
    lines = [json.loads(line) for line in index_path(tmp_path).read_text("utf-8").splitlines()]
    assert lines[0]["kind"] and "t" not in lines[0]
    assert lines[1] == {"t": 0}  # nothing yet
    assert lines[2] == {"t": 500, "cursor": CURSOR}
    assert lines[3] == {"t": 1000}  # the same as the tick before
    assert set(lines[4]) == {"t", "cursor", "background", "drawing_now"}
    assert lines[5] == {"t": 2000, "drawing_now": None, "shapes": [A], "visible": [1]}
    # (the cursor left the screens in that tick: null is a change too)
    assert set(lines[6]) == {"t", "cursor", "background", "shapes", "visible", "clipboard"}
    assert lines[6]["cursor"] is None and lines[6]["shapes"] == [B]
    assert lines[8]["visible"] == [2] and "shapes" not in lines[8]  # erased: no geometry
    assert lines[9] == {
        "t": 4000,
        "grid": None,
        "grid_source": None,
        "visible": [1, 2],
        "failed": ["screen2"],
    }
    assert lines[10]["clipboard"] == "" and lines[10]["visible"] == []


def test_a_shape_is_written_once_however_long_it_is_on_the_screen(tmp_path: Path):
    path = index_path(tmp_path)
    writer = TickIndexWriter(path, HEADER)
    for tick in range(1000):
        writer.write(500 * tick, cursor=CURSOR, drawings=[B])
    writer.close()
    text = path.read_text(encoding="utf-8")
    assert text.count('"path"') == 1
    assert len(text) < 30_000  # 1000 sidecars of this stroke were 13 MB
    index = TickIndex.load(tmp_path)
    assert all(state.drawings == [B] for state in index.states)
    assert index.states[0].drawings[0] is index.states[999].drawings[0]  # shared, not copied


def test_a_changed_shape_is_written_again(tmp_path: Path):
    moved = {**A, "from": {"screen": "screen1", "x": 5, "y": 5}}
    path = index_path(tmp_path)
    writer = TickIndexWriter(path, HEADER)
    writer.write(0, drawings=[A, B])
    writer.write(500, drawings=[moved, B])
    writer.close()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[2]) == {"t": 500, "shapes": [moved]}
    index = TickIndex.load(tmp_path)
    assert index.states[0].drawings == [A, B] and index.states[1].drawings == [moved, B]


def test_shapes_without_an_id_are_stored_as_a_list(tmp_path: Path):
    plain = [{"tool": "line"}]
    path = index_path(tmp_path)
    writer = TickIndexWriter(path, HEADER)
    writer.write(0, drawings=plain)
    writer.write(500, drawings=plain)
    writer.write(1000, drawings=[A])
    writer.write(1500, drawings=[])
    writer.close()
    lines = [json.loads(line) for line in path.read_text("utf-8").splitlines()[1:]]
    assert lines == [
        {"t": 0, "drawings": plain},
        {"t": 500},
        {"t": 1000, "shapes": [A], "visible": [1]},
        {"t": 1500, "visible": []},
    ]
    states = TickIndex.load(tmp_path).states
    assert [s.drawings for s in states] == [plain, plain, [A], []]


def test_a_line_that_was_cut_off_is_skipped(tmp_path: Path):
    """The recording ended abruptly in the middle of a write."""
    path = index_path(tmp_path)
    _write(path, _ticks())
    whole = path.read_text(encoding="utf-8")
    path.write_text(whole + '{"t": 5000, "cursor": {"scr', encoding="utf-8")
    index = TickIndex.load(tmp_path)
    assert index.times[-1] == 4500 and len(index) == len(_ticks())


def test_looking_up_a_tick(tmp_path: Path):
    _write(index_path(tmp_path), _ticks())
    index = TickIndex.load(tmp_path)
    assert index.at(1200).time_ms == 1000 and index.at(1000).time_ms == 1000
    assert index.at(-5).time_ms == 0  # before the first tick: the first one
    assert index.at(99_999).time_ms == 4500
    assert index.position(-5) is None and index.position(700) == 1
    assert index.exact(1000).time_ms == 1000 and index.exact(1001) is None
    assert index.clipboard_changes() == [(2500, "copied text"), (4500, "")]
    assert index.owner(index.at(0)) == "screen1"
    assert index.owner(index.at(4000)) == "screen1"  # only screen2 failed there


def test_the_state_seen_from_a_screen(tmp_path: Path):
    _write(index_path(tmp_path), _ticks())
    state = TickIndex.load(tmp_path).at(3500)
    one, two = state.for_screen("screen1"), state.for_screen("screen2")
    assert (one["grid"], two["grid"]) == (16, 8)
    assert one["grid_source"] == two["grid_source"] == "toggle"
    assert one["screen"] == "screen1" and one["time_ms"] == 3500
    assert one["drawings"] == [B] and one["background"] == "sketch"
    calm = TickIndex.load(tmp_path).at(0).for_screen("screen1")
    assert calm["grid"] is None and calm["grid_source"] is None


def test_a_recording_without_an_index_says_so(tmp_path: Path):
    with pytest.raises(NoIndexError) as error:
        TickIndex.load(tmp_path)
    assert error.value.code == "NO_INDEX" and INDEX_NAME in str(error.value)
    empty = TickIndex.parse("")
    assert len(empty) == 0 and empty.at(0) is None


def test_two_hours_are_read_in_a_moment(tmp_path: Path):
    """14 400 ticks with a moving cursor and 150 strokes of 40 points appearing."""
    path = index_path(tmp_path)
    writer = TickIndexWriter(path, HEADER)
    shapes: list[dict] = []
    for tick in range(14_400):
        if tick % 96 == 0 and len(shapes) < 150:
            points = [{"screen": "screen1", "x": i, "y": tick % 900} for i in range(40)]
            shapes.append({"id": len(shapes) + 1, "tool": "brush", "path": points})
        writer.write(
            500 * tick, cursor={"screen": "screen1", "x": tick % 2560, "y": 5}, drawings=shapes
        )
    writer.close()
    size = path.stat().st_size
    assert size < 2_000_000  # the sidecars of such a recording were gigabytes
    began = time.perf_counter()
    index = TickIndex.load(tmp_path)
    elapsed = time.perf_counter() - began
    assert len(index) == 14_400 and len(index.states[-1].drawings) == 150
    assert elapsed < 0.5, f"{elapsed:.2f} s for {size} bytes"
