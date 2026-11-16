"""Thinning of a brush stroke while it is drawn.

The mouse reports a position up to a thousand times a second and every one of them
used to become a point of the stroke. A stroke keeps at most one point in
:data:`MIN_GAP_MS` plus the position the pointer is at right now: a new position
replaces the last point while both the last point and the one before it are younger
than that, otherwise it is added. The first point (the press) is never replaced, and
the position of the release is always the last point.
"""

from __future__ import annotations

MIN_GAP_MS = 20.0


def add_point[P](
    points: list[P], times: list[float], position: P, now_ms: float, min_gap_ms: float = MIN_GAP_MS
) -> None:
    """Take ``position`` into the stroke ``points`` (``times``: when each point came, in
    milliseconds of any steady clock; both lists are changed in place).

    Points without a time (a stroke started elsewhere) count as made right now.
    """
    while len(times) < len(points):
        times.append(now_ms)
    del times[len(points) :]
    if len(points) >= 2 and now_ms - times[-1] <= min_gap_ms and now_ms - times[-2] <= min_gap_ms:
        points[-1] = position
        times[-1] = now_ms
    else:
        points.append(position)
        times.append(now_ms)


__all__ = ["MIN_GAP_MS", "add_point"]
