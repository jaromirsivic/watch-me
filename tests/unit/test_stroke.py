"""Thinning of brush strokes: at most one point in 20 ms plus where the pointer is now;
the press and the release are always kept."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from watch_me.core.stroke import MIN_GAP_MS, add_point  # noqa: E402


def _draw(interval_ms: float, duration_ms: float) -> tuple[list[int], list[float]]:
    """A stroke whose pointer reports a new position every ``interval_ms``; the press
    stores its position twice, as the drawing layer does."""
    points, times = [0, 0], [0.0, 0.0]
    step = 1
    now = interval_ms
    while now <= duration_ms:
        add_point(points, times, step, now)
        step += 1
        now += interval_ms
    return points, times


@pytest.mark.parametrize("interval_ms", [1.0, 8.0])  # a 1000 Hz and a 125 Hz mouse
def test_a_fast_mouse_leaves_at_most_one_point_in_20_ms(interval_ms: float):
    points, times = _draw(interval_ms, 1000.0)
    reported = int(1000.0 / interval_ms)
    # A point is kept once the one before it is older than 20 ms: with positions every
    # ``interval_ms`` that is one point in the largest multiple of the interval below
    # 20 ms (16 ms for a 125 Hz mouse), plus the press and the latest position.
    spacing = (MIN_GAP_MS // interval_ms) * interval_ms
    assert len(points) <= 1000.0 / spacing + 3
    assert len(points) <= reported / 2 + 2
    assert points[0] == 0  # the press
    assert points[-1] == reported  # the position reported last
    kept = times[1:-1]
    gaps = [b - a for a, b in zip(kept, kept[1:], strict=False)]
    assert min(gaps) >= MIN_GAP_MS - interval_ms  # no two kept points closer than that
    assert max(gaps) <= MIN_GAP_MS + 2 * interval_ms  # and none left out for long


def test_a_slow_stroke_keeps_every_point():
    points, _times = _draw(50.0, 1000.0)
    assert points == [0, 0, *range(1, 21)]


def test_the_press_is_never_replaced():
    points, times = [7, 7], [100.0, 100.0]
    add_point(points, times, 8, 101.0)
    add_point(points, times, 9, 102.0)
    assert points == [7, 9] and times == [100.0, 102.0]
    points, times = [7], [100.0]  # a stroke that starts with one point
    add_point(points, times, 8, 101.0)
    assert points == [7, 8]


def test_the_release_is_always_the_last_point():
    points, times = _draw(1.0, 30.0)
    add_point(points, times, "released", 30.5)
    assert points[0] == 0 and points[-1] == "released"


def test_points_without_a_time_count_as_made_now():
    points: list[int] = [1, 2, 3]
    times: list[float] = []
    add_point(points, times, 4, 500.0)
    assert points == [1, 2, 4] and times == [500.0, 500.0, 500.0]


def test_the_drawing_layer_thins_a_brush_stroke(qtbot, monkeypatch):
    """A hundred positions within a few milliseconds become a handful of points; the
    press and the release stay where they were."""
    from test_overlay import _park_toolbar, drag

    import watch_me.ui.overlay as overlay_mod
    from watch_me.ui.overlay import DrawingOverlay, Tool

    now = [1000.0]

    def clock() -> float:
        now[0] += 1.0  # a 1000 Hz mouse
        return now[0]

    monkeypatch.setattr(overlay_mod, "_stroke_clock_ms", clock)
    overlay = DrawingOverlay()
    overlay.show()
    for window in overlay.windows:
        qtbot.addWidget(window)
    _park_toolbar(overlay)
    try:
        overlay.set_tool(Tool.BRUSH)
        path = [(10 + i, 10 + (i * 7) % 40) for i in range(100)]
        drag(overlay.windows[0], path)
        (shape,) = overlay.shapes()
        assert 4 <= len(shape.points) <= 8  # 100 ms of drawing
        assert (shape.points[0].x(), shape.points[0].y()) == path[0]
        assert (shape.points[-1].x(), shape.points[-1].y()) == path[-1]
        assert len(shape.point_times) == len(shape.points)
    finally:
        overlay.close()
