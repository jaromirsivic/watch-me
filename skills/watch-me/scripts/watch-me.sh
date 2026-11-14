#!/usr/bin/env sh
# Watch Me launcher (Linux, macOS). Runs the plugin through uv from the repository root.
# The root is WATCH_ME_ROOT, else three levels above this script, else the same three
# levels behind the symlink the skill is registered with (the host hands the agent the
# link path): first the logical path (-L), then the physical one (-P). One level per cd,
# because Git Bash resolves a Windows junction only when it is the last path component.
set -e
WM_HERE=$(dirname -- "$0")
WM_ROOT=
if [ -n "${WATCH_ME_ROOT:-}" ] && [ -f "$WATCH_ME_ROOT/pyproject.toml" ]; then
  WM_ROOT=$WATCH_ME_ROOT
fi
for WM_MODE in -L -P; do
  if [ -z "$WM_ROOT" ]; then
    WM_TRY=$(CDPATH=; cd "$WM_MODE" -- "$WM_HERE" 2>/dev/null && cd "$WM_MODE" .. && cd "$WM_MODE" .. && cd "$WM_MODE" .. && pwd "$WM_MODE") || WM_TRY=
    if [ -n "$WM_TRY" ] && [ -f "$WM_TRY/pyproject.toml" ]; then
      WM_ROOT=$WM_TRY
    fi
  fi
done
if [ -z "$WM_ROOT" ]; then
  printf '%s\n' '{"ok":false,"code":"ROOT_NOT_FOUND","message":"Watch Me root not found: no pyproject.toml three levels above this launcher, also not behind its junction or symlink. Register the skill again with scripts/install-hosts or set WATCH_ME_ROOT to the Watch Me directory."}' >&2
  exit 21
fi

export WM_ROOT
exec sh "$WM_ROOT/scripts/launch.sh" "$@"
