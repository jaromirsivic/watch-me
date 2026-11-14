#!/usr/bin/env sh
# WM_ROOT is resolved by the H1 launcher, never from the caller's project.
if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' '{"ok":false,"code":"UV_MISSING","message":"Install uv, then retry this launcher."}' >&2
  exit 20
fi
WM_PYTHON="$WM_ROOT/.venv/bin/python"
if [ ! -x "$WM_PYTHON" ]; then
  printf '%s\n' '{"ok":false,"code":"PYTHON_MISSING","message":"Prepare the project environment with uv sync --locked."}' >&2
  exit 22
fi
WM_BOOT_MARKER=$(mktemp "${TMPDIR:-/tmp}/watch-me-boot.XXXXXXXX") || exit 22
rm -f "$WM_BOOT_MARKER"
export WM_BOOT_MARKER
"$WM_PYTHON" -I "$WM_ROOT/scripts/bootstrap.py" "$@"
WM_EXIT=$?
if [ ! -f "$WM_BOOT_MARKER" ]; then
  printf '%s\n' '{"ok":false,"code":"PYTHON_MISSING","message":"The project Python could not start its bootstrap."}' >&2
  exit 22
fi
rm -f "$WM_BOOT_MARKER"
exit "$WM_EXIT"
