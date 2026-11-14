"""Run the real no-install bootstrap / Windows launcher in isolated environments."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_bootstrap_missing_package_and_python_version(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "bootstrap.py"
    shutil.copyfile(ROOT / "scripts/bootstrap.py", script)
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nrequires-python = ">=3.12,<3.14"\n')
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(script), "version"], capture_output=True, text=True
    )
    assert result.returncode == 23
    assert json.loads(result.stderr)["code"] == "ENVIRONMENT_INVALID"
    project.write_text('[project]\nrequires-python = ">=99.0"\n')
    result = subprocess.run([sys.executable, "-I", str(script)], capture_output=True, text=True)
    assert result.returncode == 23
    assert json.loads(result.stderr)["requirement"] == ">=99.0"


STUB_BOOTSTRAP = (
    "import os,sys,json\nfrom pathlib import Path\n"
    'Path(os.environ["WM_BOOT_MARKER"]).touch()\n'
    "print(json.dumps(sys.argv[1:]))\nsys.exit(7)\n"
)


def _stand_in_root(tmp_path: Path, launcher: str) -> tuple[Path, Path]:
    """A code root with a space and a non-ASCII letter in its name: a real environment
    (made by uv), the real launcher and a bootstrap that only echoes its arguments."""
    uv = shutil.which("uv")
    if not uv:
        pytest.skip("uv is needed to make the stand-in environment")
    root = tmp_path / "space ž"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts" / launcher, scripts / launcher)
    subprocess.run(
        [uv, "venv", "--no-python-downloads", "--python", sys.executable, str(root / ".venv")],
        check=True,
        capture_output=True,
    )
    (scripts / "bootstrap.py").write_text(STUB_BOOTSTRAP, encoding="utf-8")
    return root, scripts / launcher


def _error(result: subprocess.CompletedProcess) -> dict:
    """The one JSON object a launcher writes to stderr, read as UTF-8."""
    return json.loads(result.stderr.decode("utf-8"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows .bat")
def test_real_bat_never_runs_uv_and_preserves_arguments(tmp_path):
    root, launcher = _stand_in_root(tmp_path, "launch.bat")
    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "uv.cmd").write_text("@echo off\nexit /b 99\n")
    system32 = Path(os.environ["SystemRoot"]) / "System32"
    powershell = system32 / "WindowsPowerShell" / "v1.0"
    guide = str(root / "skills" / "watch-me" / "references" / "agent-startup.md")
    with_uv = os.pathsep.join(map(str, (stub, system32, powershell)))
    without_uv = os.pathsep.join(map(str, (system32, powershell)))
    env = dict(os.environ, WM_ROOT=str(root), WM_HELP=guide, PATH=with_uv)
    command = f'"{os.environ["ComSpec"]}" /d /s /c ""{launcher}" version "a b""'

    def run(path: str) -> subprocess.CompletedProcess:
        return subprocess.run(command, env=dict(env, PATH=path), capture_output=True)

    # A prepared environment starts with uv on PATH (never run) and without it.
    for path in (with_uv, without_uv):
        result = run(path)
        assert result.returncode == 7, result.stderr
        assert json.loads(result.stdout) == ["version", "a b"]
    # No interpreter and no uv have distinct errors, without running another Python. Both
    # name the code root (where uv sync has to run) and the guide, in UTF-8.
    python = root / ".venv/Scripts/python.exe"
    python.rename(python.with_suffix(".saved"))
    for path, code, exit_code in ((with_uv, "PYTHON_MISSING", 22), (without_uv, "UV_MISSING", 20)):
        result = run(path)
        error = _error(result)
        assert (result.returncode, error["code"]) == (exit_code, code)
        assert error["ok"] is False and error["message"]
        assert error["root"] == str(root) and error["help"] == guide
    # Without PowerShell the same code comes as plain ASCII, without the paths.
    result = run(str(system32))
    error = _error(result)
    assert (result.returncode, error["code"]) == (20, "UV_MISSING")
    assert "root" not in error


def _posix_shell() -> str:
    """``sh`` to run the POSIX launcher with; on Windows only the one of Git (MSYS)."""
    shell = shutil.which("sh")
    if not shell:
        pytest.skip("no sh on PATH")
    if sys.platform == "win32":
        kind = subprocess.run([shell, "-c", "uname -s"], capture_output=True, text=True).stdout
        if not kind.startswith(("MINGW", "MSYS")):
            pytest.skip(f"sh is not Git Bash ({kind.strip() or 'unknown'})")
    return shell


def test_real_sh_starts_without_uv_and_names_the_root(tmp_path):
    shell = _posix_shell()
    root, launcher = _stand_in_root(tmp_path, "launch.sh")
    guide = str(root / "skills" / "watch-me" / "references" / "agent-startup.md")
    uv_dirs = {str(Path(found).parent) for found in [shutil.which("uv")] if found}
    without_uv = os.pathsep.join(
        entry for entry in os.environ["PATH"].split(os.pathsep) if entry not in uv_dirs
    )
    if shutil.which("uv", path=without_uv):
        pytest.skip("uv is installed in more than one directory of PATH")
    env = dict(os.environ, WM_ROOT=str(root), WM_HELP=guide)

    def run(path: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [shell, str(launcher), "version", "a b"], env=dict(env, PATH=path), capture_output=True
        )

    # A prepared environment starts with and without uv (on Windows: Scripts/python.exe).
    for path in (os.environ["PATH"], without_uv):
        result = run(path)
        assert result.returncode == 7, result.stderr
        assert json.loads(result.stdout) == ["version", "a b"]
    bin_dir = root / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
    bin_dir.rename(bin_dir.with_name("saved"))
    for path, code, exit_code in (
        (os.environ["PATH"], "PYTHON_MISSING", 22),
        (without_uv, "UV_MISSING", 20),
    ):
        result = run(path)
        error = _error(result)
        assert (result.returncode, error["code"]) == (exit_code, code)
        assert Path(error["root"]) == root and Path(error["help"]) == Path(guide)


def test_bootstrap_error_names_the_root_and_the_guide(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copyfile(ROOT / "scripts/bootstrap.py", scripts / "bootstrap.py")
    (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python = ">=99.0"\n')
    env = dict(os.environ, WM_HELP="guide.md")
    result = subprocess.run(
        [sys.executable, "-I", str(scripts / "bootstrap.py")], env=env, capture_output=True
    )
    error = _error(result)
    assert (result.returncode, error["code"]) == (23, "ENVIRONMENT_INVALID")
    assert Path(error["root"]) == tmp_path.resolve() and error["help"] == "guide.md"
