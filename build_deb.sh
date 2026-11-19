#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

PKG="hamlog"
VER="0.1.0"
ARCH="arm64"
STAGE="build/staging-${PKG}"
DEB_OUT="build/${PKG}_${VER}_${ARCH}.deb"

rm -rf "$STAGE"
mkdir -p \
  "$STAGE/DEBIAN" \
  "$STAGE/usr/share/APPLaunch/applications" \
  "$STAGE/usr/share/APPLaunch/bin" \
  "$STAGE/usr/share/APPLaunch/share/images" \
  "$STAGE/usr/share/APPLaunch/apps/${PKG}/assets" \
  "$STAGE/usr/share/APPLaunch/apps/${PKG}/fonts"

cat > "$STAGE/DEBIAN/control" <<'EOF'
Package: hamlog
Version: 0.1.0
Architecture: arm64
Maintainer: Stefan <stefan@gurk.dev>
Section: utils
Priority: optional
Depends: python3, python3-pygame, python3-cryptography
Homepage: https://github.com/stefexec/CardputerHamLog
Description: Portable Ham Radio QSO logger for Cardputer Zero
 Ham Radio logger with ADIF export, band statistics, multi-language UI,
 country flags, and HamDB/QRZ callsign lookup.
EOF

cat > "$STAGE/usr/share/APPLaunch/applications/hamlog.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=HamLog
Comment=Portable Ham Radio Logger with ADIF Export & Callsign Lookup
Exec=/usr/share/APPLaunch/bin/hamlog
Icon=share/images/hamlog.png
Terminal=false
Categories=Utility;
StartupNotify=false
EOF
chmod 0644 "$STAGE/usr/share/APPLaunch/applications/hamlog.desktop"

cat > "$STAGE/usr/share/APPLaunch/bin/hamlog" <<'EOF'
#!/bin/sh
cd "${HOME:-/tmp}" 2>/dev/null || cd /tmp
exec /usr/bin/python3 /usr/share/APPLaunch/apps/hamlog/main.py "$@"
EOF
chmod 0755 "$STAGE/usr/share/APPLaunch/bin/hamlog"

install -m 0644 assets/hamlog.png "$STAGE/usr/share/APPLaunch/share/images/hamlog.png"

PY_FILES=(
  config_manager.py
  encryption_utils.py
  export_utils.py
  flag_utils.py
  font_util.py
  language.py
  logger.py
  lookup_utils.py
  main.py
  paths.py
  theme.py
  ui_components.py
)

for f in "${PY_FILES[@]}"; do
  install -m 0644 "$f" "$STAGE/usr/share/APPLaunch/apps/${PKG}/$f"
done

install -m 0644 assets/flags16.png "$STAGE/usr/share/APPLaunch/apps/${PKG}/assets/flags16.png"
install -m 0644 fonts/DejaVuSansNerdBold.ttf "$STAGE/usr/share/APPLaunch/apps/${PKG}/fonts/DejaVuSansNerdBold.ttf"
install -m 0644 "fonts/卓特清雅体.ttf" "$STAGE/usr/share/APPLaunch/apps/${PKG}/fonts/卓特清雅体.ttf"

dpkg-deb --root-owner-group -b "$STAGE" "$DEB_OUT"
rm -rf "$STAGE"
echo "Built $DEB_OUT"
