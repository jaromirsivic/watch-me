"""Shared pytest configuration."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_state_folder(tmp_path_factory, monkeypatch):
    """Every test gets its own empty state folder (``WATCH_ME_HOME``): no test may
    create or change the real ``~/.watch-me`` or the checkout's ``config.json``.
    The model and FFmpeg of the checkout are still found through the code root."""
    monkeypatch.setenv("WATCH_ME_HOME", str(tmp_path_factory.mktemp("state")))
    monkeypatch.delenv("WATCH_ME_CONFIG", raising=False)


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Skip integration tests unless WATCH_ME_INTEGRATION=1 is set."""
    if os.environ.get("WATCH_ME_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(
        reason="set WATCH_ME_INTEGRATION=1 to run tests that use real screens/audio/model"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
