"""Real recording on the development machine (screens + microphone, no window)."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from watch_me.capture.recorder import Recorder
from watch_me.core.config import Config
from watch_me.core.manifest import read_manifest, write_manifest
from watch_me.core.naming import frame_base, parse_frame_filename
from watch_me.core.session import SessionPaths, new_session_id
from watch_me.core.tick_index import INDEX_NAME, TickIndex
from watch_me.platform import get_platform

pytestmark = pytest.mark.integration


def _record(tmp_path: Path, seconds: float, **cfg_changes) -> tuple[SessionPaths, object, Config]:
    import time

    cfg = Config(recording_folder=tmp_path, **cfg_changes)
    platform = get_platform()
    paths = SessionPaths(cfg.recording_folder, new_session_id(cfg.recording_folder))
    recorder = Recorder(cfg, platform, paths)
    recorder.start()
    time.sleep(seconds)
    summary = recorder.stop()
    write_manifest(paths.manifest_path(paths.work_dir), summary.to_manifest(cfg, platform.name))
    paths.finalize()
    return paths, summary, cfg


def test_two_second_recording_produces_frames_tick_index_and_audio(tmp_path: Path):
    paths, summary, cfg = _record(tmp_path, 2.0, capture_interval_ms=250, image_format="png")
    final = paths.final_dir
    assert final.is_dir() and not paths.work_dir.joinpath("frames").exists()
    manifest = read_manifest(paths.manifest_path(final))
    screens = {s.id for s in manifest.screens}
    assert screens, "at least one screen"

    frames = sorted(p for p in paths.frames_dir(final).iterdir() if p.suffix == ".png")
    assert all(p.suffix == ".png" for p in paths.frames_dir(final).iterdir())
    assert [p.name for p in paths.frames_info_dir(final).iterdir()] == [INDEX_NAME]
    ticks = TickIndex.load(paths.frames_info_dir(final))
    assert set(ticks.screens) == screens and manifest.frames.ticks == len(ticks)
    assert paths.audio_path(final).is_file()
    assert len(frames) >= 5 * len(screens), f"expected >= 5 frames per screen, got {len(frames)}"
    grabbed = {
        frame_base(state.time_ms, screen_id)
        for state in ticks.states
        for screen_id in ticks.screens
        if screen_id not in state.failed
    }
    assert {p.stem for p in frames} == grabbed, "every grabbed screen of a tick has an image"

    per_screen: dict[str, list[int]] = {}
    for frame in frames:
        parsed = parse_frame_filename(frame.name)
        assert parsed is not None and parsed.screen_id in screens
        per_screen.setdefault(parsed.screen_id, []).append(parsed.time_ms)
        state = ticks.exact(parsed.time_ms)
        assert state is not None and parsed.screen_id not in state.failed
        assert state.drawings == []  # no overlay in a headless recording
        assert state.zoom == []
        assert state.background is None  # not drawing
        cursor = state.cursor
        if cursor is not None:
            assert cursor["screen"] in screens
            target = next(s for s in manifest.screens if s.id == cursor["screen"])
            assert 0 <= cursor["x"] < target.image_width and 0 <= cursor["y"] < target.image_height
    for times in per_screen.values():
        assert times == sorted(times) and len(set(times)) == len(times)
        gaps = [b - a for a, b in zip(times, times[1:], strict=False)]
        assert all(200 <= g <= 400 for g in gaps), gaps

    with wave.open(str(paths.audio_path(final)), "rb") as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        duration_ms = wav.getnframes() * 1000 / wav.getframerate()
    assert 1500 <= duration_ms <= 3500, duration_ms
    assert abs(summary.recorded_duration_ms - 2000) < 400
    assert manifest.frames.count == len(frames)

    # What the computer played: a second track at the microphone's rate, as long as the
    # microphone (it is kept on the recording clock even while nothing plays).
    from watch_me.capture.computer_audio import computer_audio_support

    if computer_audio_support().supported:
        computer = paths.computer_audio_path(final)
        assert computer.is_file() and manifest.computer_audio is not None
        with wave.open(str(computer), "rb") as wav:
            assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
            assert wav.getframerate() == manifest.audio.sample_rate
            computer_ms = wav.getnframes() * 1000 / wav.getframerate()
        assert abs(computer_ms - duration_ms) < 300, (computer_ms, duration_ms)
    else:
        assert manifest.computer_audio is None


def test_jpeg_format_and_auto_stop(tmp_path: Path):
    paths, summary, _ = _record(
        tmp_path, 1.0, capture_interval_ms=100, image_format="jpeg", jpeg_quality=50
    )
    frames = [p for p in paths.frames_dir(paths.final_dir).iterdir() if p.suffix == ".jpg"]
    assert frames and all(p.read_bytes()[:2] == b"\xff\xd8" for p in frames)
    assert summary.auto_stopped is False
