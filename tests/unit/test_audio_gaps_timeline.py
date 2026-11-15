"""Outages of the audio devices (manifest ``gaps``) in the text timeline."""

from __future__ import annotations

from typing import Any

from watch_me.core.crop import Crop
from watch_me.host import events


def _lines(manifest: dict[str, Any], window: Crop, counts: dict[str, int]) -> list[str]:
    return [e.text for e in events._gap_events(manifest, window, counts)]


def _manifest(gaps: Any, computer_gaps: Any = None) -> dict[str, Any]:
    return {
        "recorded_duration_ms": 120_000,
        "audio": {"gaps": gaps},
        "computer_audio": None if computer_gaps is None else {"gaps": computer_gaps},
    }


HEADSET = {
    "from_ms": 66_000,
    "to_ms": 78_000,
    "reason": "no sound from the device",
    "device": "Headset",
    "restored_device": "Pole mikrofonu",
}


def test_mic_gap_inside_the_window_that_came_back():
    counts: dict[str, int] = {}
    lines = _lines(_manifest([HEADSET]), Crop(0, 120_000), counts)
    assert lines == [
        '66000 MIC LOST (no sound from "Headset"; silence until 78000)',
        '78000 MIC BACK ("Pole mikrofonu")',
    ]
    assert counts["audio_gaps"] == 1


def test_gap_that_began_before_the_window():
    counts: dict[str, int] = {}
    lines = _lines(_manifest([HEADSET]), Crop(70_000, 120_000), counts)
    assert lines == [
        '70000 MIC LOST (no sound from "Headset" since 66000; silence until 78000)',
        '78000 MIC BACK ("Pole mikrofonu")',
    ]
    assert counts["audio_gaps"] == 1


def test_gap_to_the_end_of_the_recording():
    gaps = [
        {"from_ms": 10_000, "to_ms": 120_000, "device": "Headset"},
        {"from_ms": 20_000, "to_ms": None, "device": "Headset"},
    ]
    counts: dict[str, int] = {}
    lines = _lines(_manifest(gaps), Crop(0, 120_000), counts)
    assert lines == [
        '10000 MIC LOST (no sound from "Headset"; silence to the end of the recording)',
        '20000 MIC LOST (no sound from "Headset"; silence to the end of the recording)',
    ]
    assert not any("BACK" in line for line in lines)
    assert counts["audio_gaps"] == 2


def test_computer_audio_gap():
    gap = {"from_ms": 5000, "to_ms": 9000, "device": "Speakers", "restored_device": "Speakers"}
    counts: dict[str, int] = {}
    lines = _lines(_manifest([], [gap]), Crop(0, 120_000), counts)
    assert lines == [
        '5000 PC AUDIO LOST (no sound from "Speakers"; silence until 9000)',
        '9000 PC AUDIO BACK ("Speakers")',
    ]
    assert counts["audio_gaps"] == 1


def test_gap_without_device_names():
    counts: dict[str, int] = {}
    lines = _lines(_manifest([{"from_ms": 5000, "to_ms": 9000}]), Crop(0, 120_000), counts)
    assert lines == ["5000 MIC LOST (no sound; silence until 9000)", "9000 MIC BACK"]


def test_gap_wholly_outside_the_window():
    counts: dict[str, int] = {}
    assert _lines(_manifest([HEADSET]), Crop(0, 60_000), counts) == []
    assert _lines(_manifest([HEADSET]), Crop(80_000, 120_000), counts) == []
    assert counts["audio_gaps"] == 0


def test_old_and_malformed_manifests():
    window = Crop(0, 120_000)
    old = {"recorded_duration_ms": 120_000, "audio": {"device": "Headset"}, "computer_audio": None}
    counts: dict[str, int] = {}
    assert _lines(old, window, counts) == []
    assert counts["audio_gaps"] == 0
    assert _lines({}, window, {}) == []
    assert _lines({"audio": "x", "computer_audio": 3}, window, {}) == []
    assert _lines(_manifest("x"), window, {}) == []
    malformed = [{"to_ms": 9000, "device": "Headset"}, "gap", None, 7, {"from_ms": "1"}]
    counts = {}
    assert _lines(_manifest(malformed, malformed), window, counts) == []
    assert counts["audio_gaps"] == 0


def test_legend_mentions_lost_audio():
    assert "MIC LOST" in events.LEGEND and "PC AUDIO BACK" in events.LEGEND
