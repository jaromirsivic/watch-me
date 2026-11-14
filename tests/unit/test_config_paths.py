"""Paths of the configuration mean the same place from every working directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from watch_me.core import config as cfg
from watch_me.host import cli


def test_relative_paths_are_taken_from_the_folder_of_the_config_file(tmp_path, monkeypatch):
    home = tmp_path / "state"
    home.mkdir()
    file = home / "config.json"
    file.write_text(
        json.dumps({"recording_folder": "recordings", "ffmpeg_path": "bin/ffmpeg.exe"}),
        encoding="utf-8",
    )
    loaded = []
    for name in ("a", "b"):
        where = tmp_path / name
        where.mkdir()
        monkeypatch.chdir(where)
        loaded.append(cfg.load_config(file))
    assert loaded[0] == loaded[1]
    assert loaded[0].recording_folder == home / "recordings"
    assert loaded[0].ffmpeg_path == home / "bin" / "ffmpeg.exe"
    assert loaded[0].whisper_model_path is None  # an unset path stays unset


def test_absolute_paths_are_kept(tmp_path):
    folder = tmp_path / "elsewhere" / "recordings"
    file = tmp_path / "config.json"
    file.write_text(json.dumps({"recording_folder": str(folder)}), encoding="utf-8")
    assert cfg.load_config(file).recording_folder == folder


def test_config_option_and_variable_become_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli._config_file(argparse.Namespace(config="sub/config.json")) == (
        tmp_path / "sub" / "config.json"
    )
    assert cli._config_file(argparse.Namespace(config=None)) is None
    monkeypatch.setenv(cfg.CONFIG_PATH_ENV, "other.json")
    assert cfg.config_path() == Path(tmp_path) / "other.json"
