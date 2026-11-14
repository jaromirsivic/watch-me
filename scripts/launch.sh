#!/usr/bin/env sh
# WM_ROOT is resolved by the H1 launcher, never from the caller's project (WM_HELP: its
# recovery guide). uv is needed to repair the environment, not to start: it is looked for
# only when the interpreter of the environment is missing.

WM_WINDOWS=
case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) WM_WINDOWS=1 ;;
esac

# A path as a JSON string body; on Git Bash in the form Windows tools take too (D:/...).
wm_json_path() {
  if [ -n "$WM_WINDOWS" ] && command -v cygpath >/dev/null 2>&1; then
    set -- "$(cygpath -m "$1" 2>/dev/null || printf '%s' "$1")"
  fi
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

# wm_fail CODE EXIT MESSAGE: one JSON object on stderr with the code root and the guide.
wm_fail() {
  WM_JSON="{\"ok\":false,\"code\":\"$1\",\"message\":\"$3\",\"root\":\"$(wm_json_path "$WM_ROOT")\""
  if [ -n "${WM_HELP:-}" ]; then
    WM_JSON="$WM_JSON,\"help\":\"$(wm_json_path "$WM_HELP")\""
  fi
  printf '%s}\n' "$WM_JSON" >&2
  exit "$2"
}

WM_PYTHON="$WM_ROOT/.venv/bin/python"
if [ ! -x "$WM_PYTHON" ] && [ -n "$WM_WINDOWS" ] && [ -f "$WM_ROOT/.venv/Scripts/python.exe" ]; then
  WM_PYTHON="$WM_ROOT/.venv/Scripts/python.exe"  # a Windows environment run from Git Bash
fi
if [ ! -x "$WM_PYTHON" ]; then
  if ! command -v uv >/dev/null 2>&1; then
    wm_fail UV_MISSING 20 "Install uv, then retry this launcher."
  fi
  wm_fail PYTHON_MISSING 22 "Prepare the project environment with uv sync --locked."
fi
WM_BOOT_MARKER=$(mktemp "${TMPDIR:-/tmp}/watch-me-boot.XXXXXXXX") ||
  wm_fail PYTHON_MISSING 22 "The launcher could not create its start marker."
rm -f "$WM_BOOT_MARKER"
export WM_BOOT_MARKER
"$WM_PYTHON" -I "$WM_ROOT/scripts/bootstrap.py" "$@"
WM_EXIT=$?
if [ ! -f "$WM_BOOT_MARKER" ]; then
  wm_fail PYTHON_MISSING 22 "The project Python could not start its bootstrap."
fi
rm -f "$WM_BOOT_MARKER"
exit "$WM_EXIT"
