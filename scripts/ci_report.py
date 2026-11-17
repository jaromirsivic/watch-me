"""Summarise a smoke recording for CI: GitHub annotations and the step summary.

Usage: python scripts/ci_report.py <recording_folder> [<label>]

Annotations (``::notice::``) and ``$GITHUB_STEP_SUMMARY`` are readable on the public run
page without signing in, unlike the raw job logs.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def find_session(folder: Path) -> Path | None:
    """The newest recording under ``folder``.

    A recording lies in ``<recording folder>/<folder of the user>/<session id>/`` (a new one
    in ``default``); a session directly in the recording folder is accepted as well.
    """
    manifests = [*folder.glob("*/manifest.json"), *folder.glob("*/*/manifest.json")]
    sessions = [m.parent for m in manifests if not m.parent.name.startswith(".")]
    return max(sessions, key=lambda p: p.name, default=None)  # session ids sort by time


def summarise(folder: Path) -> dict:
    session = find_session(folder)
    if session is None:
        return {"error": f"no recording in {folder}"}
    manifest = json.loads((session / "manifest.json").read_text(encoding="utf-8"))
    frames_dir = session / manifest["frames"]["dir"]
    frames = sorted(p for p in frames_dir.iterdir() if p.suffix in {".png", ".jpg"})
    report: dict = {
        "session": session.name,
        "platform": manifest.get("platform"),
        "recorded_duration_ms": manifest.get("recorded_duration_ms"),
        "screens": [
            {
                "id": s["id"],
                "bounds": s["bounds"],
                "image_size": s.get("image_size"),
                "pixel_ratio": s.get("pixel_ratio"),
                "primary": s["primary"],
            }
            for s in manifest["screens"]
        ],
        "frames": len(frames),
        "ticks": manifest["frames"].get("ticks"),
        "dropped_ticks": manifest["frames"].get("dropped_ticks"),
        "first_frames": [p.name for p in frames[:4]],
    }
    try:
        from PIL import Image

        sizes = {}
        for frame in frames[:4]:
            with Image.open(frame) as im:
                sizes[frame.name] = {"size": im.size, "extrema": im.convert("RGB").getextrema()}
        report["image_check"] = sizes
    except Exception as exc:  # pragma: no cover
        report["image_check"] = f"unavailable: {exc}"
    # What the first tick showed: the line after the header of the tick index.
    info = manifest["frames"]
    index = session / info.get("info_dir", "frames_info") / info.get("info", "index.jsonl")
    try:
        lines = index.read_text(encoding="utf-8").splitlines()
        report["index_lines"] = len(lines)
        if len(lines) > 1:
            report["first_tick"] = json.loads(lines[1])
    except (OSError, ValueError) as exc:
        report["index"] = f"unreadable: {exc}"
    return report


def main() -> int:
    folder = Path(sys.argv[1])
    label = sys.argv[2] if len(sys.argv) > 2 else folder.name
    report = summarise(folder) if folder.exists() else {"error": f"{folder} missing"}
    text = json.dumps(report, ensure_ascii=False)
    print(text)
    # One notice per report; GitHub truncates very long messages, keep it compact.
    print(f"::notice title=Watch Me smoke {label}::{text[:3800]}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## Smoke recording ({label})\n\n```json\n")
            fh.write(json.dumps(report, indent=2, ensure_ascii=False))
            fh.write("\n```\n")
    return 0 if "error" not in report else 1


if __name__ == "__main__":
    sys.exit(main())
