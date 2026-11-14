#!/usr/bin/env sh
WM_HERE=$(CDPATH= cd -P -- "$(dirname -- "$0")" && pwd -P) || exit 21
if [ "$#" -eq 0 ]; then
  set -- run
fi
exec sh "$WM_HERE/skills/watch-me/scripts/watch-me.sh" "$@" --detach
