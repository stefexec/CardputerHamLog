#!/bin/sh
DIR="$(cd "$(dirname "$0")" && pwd)"
exec /usr/bin/python3 "$DIR/main.py" "$@"
