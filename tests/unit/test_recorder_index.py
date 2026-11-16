"""Recorder unit tests with a fake platform and grabber: the tick index, keypoints and
the clipboard."""

from __future__ import annotations

import json
import time
from pathlib import Path

from watch_me.capture import recorder as recorder_mod
from watch_me.capture.recorder import KEYPOINT_MIN_GAP_MS, Recorder
from watch_me.capture.screen_grabber import RawFrame
from watch_me.core.config import Config
from watch_me.core.manifest import read_manifest, write_manifest
from watch_me.core.screens import RawScreen
from watch_me.core.session import SessionPaths
from watch_me.core.tick_index import INDEX_NAME, TickIndex
from watch_me.platform.base import Platform, SupportStatus


class FakePlatform(Platform):
    name = "fake"

    def prepare_process(self) -> None:
        pass

    def support_status(self) -> SupportStatus:
        return SupportStatus(True)

    def list_screens(self):
        return [RawScreen(0, 0, 8, 6, primary=True)]

    def cursor_position(self):
        return (3, 2)


class FakeGrabber:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def grab(self, screen) -> RawFrame:
        size = screen.width * screen.height * 4
        return RawFrame(screen.id, screen.width, screen.height, bytes(size))


def _record(
    tmp_path: Path, monkeypatch, clipboard_values: list[str | None]
) -> tuple[SessionPaths, list[int]]:
    monkeypatch.setattr(recorder_mod, "ScreenGrabber", FakeGrabber)
    cfg = Config(recording_folder=tmp_path, capture_interval_ms=20, image_format="png")
    paths = SessionPaths(tmp_path, "20260101-120000")
    recorder = Recorder(cfg, FakePlatform(), paths, record_audio=False)
    queue = list(clipboard_values)

    def provider() -> str | None:
        return queue.pop(0) if queue else None

    recorder.clipboard_provider = provider
    recorder.grid_provider = lambda: {"screen1": 16}
    recorder.start()
    deadline = time.monotonic() + 3.0
    while recorder.frame_count < 6 and time.monotonic() < deadline:
        time.sleep(0.01)
    first = recorder.add_keypoint()
    assert first is not None
    assert recorder.add_keypoint() is None  # inside the three second gap
    assert KEYPOINT_MIN_GAP_MS == 3000
    monkeypatch.setattr(recorder_mod, "KEYPOINT_MIN_GAP_MS", 0)  # pretend time passed
    time.sleep(0.03)
    second = recorder.add_keypoint()
    assert second is not None and second > first
    summary = recorder.stop()
    write_manifest(paths.manifest_path(paths.work_dir), summary.to_manifest(cfg, "fake"))
    paths.finalize()
    return paths, summary.keypoints


def test_index_stores_the_clipboard_once_and_the_manifest_the_keypoints(tmp_path, monkeypatch):
    paths, keypoints = _record(tmp_path, monkeypatch, ["copied text"])
    final = paths.final_dir
    info = paths.frames_info_dir(final)
    assert [p.name for p in info.iterdir()] == [INDEX_NAME]  # one file, no file per frame
    ticks = TickIndex.load(info)
    assert len(ticks) >= 6 and ticks.screens == ["screen1"]
    images = sorted(p.name for p in paths.frames_dir(final).iterdir())
    assert len(images) == len(ticks)  # one image per screen and tick
    values = [s.clipboard for s in ticks.states]
    assert values.count("copied text") == 1  # the first tick after the change, nowhere else
    assert all(v is None for v in values if v != "copied text")
    assert ticks.states[0].drawings == []
    assert all(s.drawing_now is None for s in ticks.states)  # no overlay connected
    # Ctrl held: that screen's grid spacing.
    assert all(s.for_screen("screen1")["grid"] == 16 for s in ticks.states)
    assert all(s.failed == () for s in ticks.states)  # every grab worked
    manifest = read_manifest(paths.manifest_path(final))
    assert manifest.keypoints == sorted(keypoints) and len(manifest.keypoints) == 2
    raw = json.loads(paths.manifest_path(final).read_text(encoding="utf-8"))
    assert raw["frames"]["info"] == INDEX_NAME
    assert raw["frames"]["ticks"] == len(ticks) == raw["frames"]["count"]
    assert raw["keypoints"] == [
        {"index": 1, "time_ms": manifest.keypoints[0]},
        {"index": 2, "time_ms": manifest.keypoints[1]},
    ]
    assert "Keypoint button" in raw["keypoints_note"]


def test_add_keypoint_needs_a_running_recorder(tmp_path):
    recorder = Recorder(
        Config(recording_folder=tmp_path),
        FakePlatform(),
        SessionPaths(tmp_path, "20260101-120001"),
        record_audio=False,
    )
    assert recorder.add_keypoint() is None and recorder.keypoints == []
