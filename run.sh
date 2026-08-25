#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/main.py" "$@"
