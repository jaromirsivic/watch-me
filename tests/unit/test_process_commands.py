"""Child Python commands are isolated (``-I``): no module of the caller can shadow ours."""

from __future__ import annotations

import json
import os
import subprocess

from watch_me.platform.process import python_command


def test_python_command_is_isolated():
    worker = python_command("-m", "x")
    window = python_command("-m", "x", gui=True, utf8=False)
    assert worker[1] == "-I"
    assert worker[2:4] == ["-X", "utf8"]
    assert worker[-2:] == ["-m", "x"]
    assert window[1] == "-I"
    assert "-X" not in window
    assert window[-2:] == ["-m", "x"]


def test_child_ignores_shadowing_module_in_cwd_and_pythonpath(tmp_path):
    (tmp_path / "argparse.py").write_text('raise SystemExit("shadowed")\n', encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(tmp_path)
    result = subprocess.run(
        python_command("-m", "watch_me", "version"),
        cwd=tmp_path,
        env=env,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert json.loads(result.stdout.decode("utf-8"))["ok"] is True


def test_no_hand_built_child_command_outside_process_module():
    """``python_command`` is the only place that picks the interpreter of a child: a
    command built elsewhere would run without ``-I``."""
    import re
    from pathlib import Path

    import watch_me

    package = Path(watch_me.__file__).parent
    pattern = re.compile(r"\b(gui_python|console_python)\s*\(|sys\.executable\s*,")
    found = []
    for path in sorted(package.rglob("*.py")):
        if path.relative_to(package).as_posix() == "platform/process.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                found.append(f"{path.relative_to(package).as_posix()}:{number}: {line.strip()}")
    assert not found, "\n".join(found)


def test_detached_process_does_not_keep_the_callers_directory(tmp_path, monkeypatch):
    """A window runs in the user's home folder, so the directory it was started from (the
    agent's project, a worktree) can be deleted or renamed while the window is open."""
    import sys
    import time
    from pathlib import Path

    from watch_me.platform.process import neutral_cwd, spawn_detached

    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    out = tmp_path / "cwd.txt"
    code = "import os, sys; open(sys.argv[1], 'w', encoding='utf-8').write(os.getcwd())"
    spawn_detached([sys.executable, "-I", "-c", code, str(out)], tmp_path / "child.log")
    deadline = time.monotonic() + 30
    while not out.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.1)
    assert neutral_cwd() == Path.home()
    assert Path(out.read_text(encoding="utf-8")) == Path.home()
