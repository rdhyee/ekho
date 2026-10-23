#!/bin/sh
# Speak Chinese text in Toisanese, no install step needed.
#   ./say-toisanese.sh 一二三四五六七八九十零
#   ./say-toisanese.sh --engine clips --gap 0.2 "一 二 三"   (slower, for teaching)
# Writes $TMPDIR/toisanese.wav (or -o FILE) and plays it with afplay.
# Resolve symlinks so this works from ~/.local/bin or anywhere on PATH.
SELF="$0"
while [ -L "$SELF" ]; do SELF="$(readlink "$SELF")"; done
DIR="$(cd "$(dirname "$SELF")" && pwd)"
PY="${PYTHON:-$HOME/.pyenv/shims/python3}"
[ -x "$PY" ] || PY=python3
exec "$PY" "$DIR/tools/toisanese_say.py" "$@"
