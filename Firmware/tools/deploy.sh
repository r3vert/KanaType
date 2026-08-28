#!/bin/sh
# macOS/Linux deploy: copy Firmware/src -> the CIRCUITPY drive.
# Non-destructive (no --delete): device-side lib/ installs are never removed.
set -e
DST=""
for d in /Volumes/CIRCUITPY /media/*/CIRCUITPY /run/media/*/CIRCUITPY; do
    [ -d "$d" ] && DST="$d" && break
done
if [ -z "$DST" ]; then
    echo "CIRCUITPY drive not found - is the Feather plugged in?" >&2
    exit 1
fi
SRC="$(cd "$(dirname "$0")/../src" && pwd)"
rsync -r --exclude '__pycache__' --exclude '.DS_Store' "$SRC/" "$DST/"
echo "Deployed src/ to $DST (device auto-reloads)."
