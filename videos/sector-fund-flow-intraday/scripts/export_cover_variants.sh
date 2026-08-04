#!/usr/bin/env bash
# Export Douyin dual covers as JPG from the main 9:16 cover.
# Usage: bash scripts/export_cover_variants.sh out/cover.jpg
set -euo pipefail

SRC="${1:-out/cover.jpg}"
if [[ ! -f "$SRC" ]]; then
  echo "cover not found: $SRC" >&2
  exit 1
fi

DIR="$(cd "$(dirname "$SRC")" && pwd)"
BASE="$(basename "$SRC")"
STEM="${BASE%.*}"

PORT_JPG="${DIR}/${STEM}-竖3x4.jpg"
LAND_JPG="${DIR}/${STEM}-横4x3.jpg"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

ffmpeg -y -i "$SRC" \
  -vf "scale=1080:1440:force_original_aspect_ratio=increase,crop=1080:1440" \
  -frames:v 1 "$TMP_DIR/port.png" >/dev/null 2>&1
ffmpeg -y -i "$SRC" \
  -vf "crop=1080:810:0:380,scale=1440:1080" \
  -frames:v 1 "$TMP_DIR/land.png" >/dev/null 2>&1

# JFIF JPEG via sips (Douyin-friendly)
sips -s format jpeg -s formatOptions 95 "$TMP_DIR/port.png" --out "$PORT_JPG" >/dev/null
sips -s format jpeg -s formatOptions 95 "$TMP_DIR/land.png" --out "$LAND_JPG" >/dev/null

echo "cover: $SRC"
echo "port:  $PORT_JPG"
echo "land:  $LAND_JPG"
