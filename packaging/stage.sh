#!/usr/bin/env bash
set -euo pipefail

# Install python scripts into apps folder
cp *.py "$STAGE/usr/share/APPLaunch/apps/hamlog/"

# Copy assets
cp -r assets "$STAGE/usr/share/APPLaunch/apps/hamlog/"
cp -r fonts "$STAGE/usr/share/APPLaunch/apps/hamlog/"

# Create wrapper script in bin
tmp=$(mktemp)
cat >"$tmp" <<'EOF'
#!/bin/sh
exec python3 /usr/share/APPLaunch/apps/hamlog/main.py "$@"
EOF
install -D -m 0755 "$tmp" "$STAGE/usr/share/APPLaunch/bin/run.sh"
rm -f "$tmp"
chmod 0755 "$STAGE/usr/share/APPLaunch/bin/run.sh"
