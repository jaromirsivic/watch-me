"""How much of the screen changes between the frames of finished recordings.

Every tick stores a whole image of every screen (review finding B3). Before that is
changed, this answers what a change would save, for each screen of each recording:

* how many frames are byte for byte the same as the frame before them (what "store an
  image only when the screen changed" would leave out);
* how many frames differ only in the few places that change at most ticks (a clock, the
  recorder's own window, a progress indicator), and where those places are;
* how much of the screen changes at a tick (tiles of 32x32 pixels) - what "store only
  the changed parts" would have to keep.

    uv run python scripts/frame_changes.py REC_DIR [REC_DIR ...]

``REC_DIR`` is a recording folder (with ``frames/``) or a folder of recordings. On
three recordings of 20 to 76 s (16 Nov 2026): the primary screen had 0-7 % identical
frames, the second one 38-49 %; the median changed area was below 1 % of the screen.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from watch_me.core.naming import parse_frame_filename

TILE = 32
THRESHOLD = 24  # a difference of a colour channel above the noise of JPEG
BUSY_SHARE = 0.25  # a place is "busy" when it changes at more than this share of ticks


def _load(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def _groups(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    """Connected groups of tiles as ``(x0, y0, x1, y1, tiles)`` in pixels, largest first."""
    seen = np.zeros_like(mask, dtype=bool)
    found = []
    for y, x in zip(*np.nonzero(mask), strict=True):
        if seen[y, x]:
            continue
        stack, cells = [(y, x)], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            cells.append((cy, cx))
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                inside = 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1]
                if inside and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        ys, xs = [c[0] for c in cells], [c[1] for c in cells]
        found.append(
            (min(xs) * TILE, min(ys) * TILE, (max(xs) + 1) * TILE, (max(ys) + 1) * TILE, len(cells))
        )
    return sorted(found, key=lambda group: -group[4])


def measure_screen(files: list[Path]) -> dict[str, object]:
    """The figures of one screen; ``files`` are its frames in time order."""
    previous = _load(files[0])
    previous_hash = hashlib.sha1(files[0].read_bytes()).digest()
    height, width = previous.shape[:2]
    rows, cols = -(-height // TILE), -(-width // TILE)
    counts = np.zeros((rows, cols), dtype=int)
    changed_tiles: list[np.ndarray] = []
    identical = 0
    kept_bytes = files[0].stat().st_size
    for path in files[1:]:
        digest = hashlib.sha1(path.read_bytes()).digest()
        if digest == previous_hash:
            identical += 1
            changed_tiles.append(np.zeros((rows, cols), dtype=bool))
            continue
        kept_bytes += path.stat().st_size
        current = _load(path)
        changed = np.abs(current - previous).max(axis=2) > THRESHOLD
        padded = np.zeros((rows * TILE, cols * TILE), dtype=bool)
        padded[:height, :width] = changed
        tiles = padded.reshape(rows, TILE, cols, TILE).any(axis=(1, 3))
        changed_tiles.append(tiles)
        counts += tiles
        previous, previous_hash = current, digest
    pairs = len(changed_tiles)
    busy = counts > BUSY_SHARE * pairs
    share = [float(tiles.mean()) for tiles in changed_tiles]
    return {
        "size": (width, height),
        "frames": len(files),
        "bytes": sum(f.stat().st_size for f in files),
        "pairs": pairs,
        "identical": identical,
        "kept_bytes": kept_bytes,
        "calm": sum(1 for tiles in changed_tiles if not (tiles & ~busy).any()),
        "median_share": float(np.median(share)) if share else 0.0,
        "mean_share": float(np.mean(share)) if share else 0.0,
        "busy": [
            (
                *group[:4],
                int(
                    counts[
                        group[1] // TILE : group[3] // TILE, group[0] // TILE : group[2] // TILE
                    ].max()
                ),
            )
            for group in _groups(busy)[:5]
        ],
    }


def recordings(root: Path) -> list[Path]:
    if (root / "frames").is_dir():
        return [root]
    return sorted(p for p in root.rglob("frames") if p.is_dir() and p.parent.is_dir())


def report(recording: Path) -> None:
    by_screen: dict[str, list[tuple[int, Path]]] = {}
    for path in (recording / "frames").iterdir():
        name = parse_frame_filename(path.name)
        if name is not None:
            by_screen.setdefault(name.screen_id, []).append((name.time_ms, path))
    for screen, entries in sorted(by_screen.items()):
        files = [path for _time, path in sorted(entries)]
        if len(files) < 2:
            continue
        m = measure_screen(files)
        pairs = m["pairs"]
        width, height = m["size"]
        print(
            f"{recording.name} {screen} {width}x{height}: {m['frames']} frames, "
            f"{m['bytes'] / 1e6:.1f} MB\n"
            f"    identical to the frame before: {m['identical']}/{pairs} "
            f"({100 * m['identical'] / pairs:.0f} %), the rest is "
            f"{100 * m['kept_bytes'] / m['bytes']:.0f} % of the bytes\n"
            f"    unchanged outside the busy places: {m['calm']}/{pairs} "
            f"({100 * m['calm'] / pairs:.0f} %)\n"
            f"    changed area per tick: median {100 * m['median_share']:.2f} %, "
            f"mean {100 * m['mean_share']:.2f} % of the screen"
        )
        for x0, y0, x1, y1, hits in m["busy"]:
            print(
                f"    busy place {x0},{y0} - {x1},{y1} ({x1 - x0}x{y1 - y0}): "
                f"changes at up to {hits} of {pairs} ticks"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folders", nargs="+", type=Path, help="recording folders")
    args = parser.parse_args(argv)
    found = [
        frames.parent if frames.name == "frames" else frames
        for root in args.folders
        for frames in recordings(root)
    ]
    if not found:
        print("no recording with frames/ found", file=sys.stderr)
        return 1
    for recording in found:
        report(recording)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
