#!/usr/bin/env bash
# Export Douyin dual covers as JPG from the main 9:16 poster cover.
# Poster-safe: letterbox (pad), NEVER hub-crop from video freeze (old y=380 crop).
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

# Prefer Remotion-rendered portrait if present (exact 3:4 poster layout).
PORT_SRC="${DIR}/${STEM}-竖3x4-render.jpg"
if [[ -f "$PORT_SRC" ]]; then
  sips -s format jpeg -s formatOptions 95 "$PORT_SRC" --out "$PORT_JPG" >/dev/null
else
  # Fallback: letterbox full 9:16 poster into 3:4 (no content cut).
  ffmpeg -y -i "$SRC" \
    -vf "scale=1080:1440:force_original_aspect_ratio=decrease,pad=1080:1440:(ow-iw)/2:(oh-ih)/2:black" \
    -frames:v 1 "$TMP_DIR/port.png" >/dev/null 2>&1
  sips -s format jpeg -s formatOptions 95 "$TMP_DIR/port.png" --out "$PORT_JPG" >/dev/null
fi

# Landscape: letterbox full poster into 4:3 (keep date + turnover + in/out cards).
ffmpeg -y -i "$SRC" \
  -vf "scale=1440:1080:force_original_aspect_ratio=decrease,pad=1440:1080:(ow-iw)/2:(oh-ih)/2:black" \
  -frames:v 1 "$TMP_DIR/land.png" >/dev/null 2>&1
sips -s format jpeg -s formatOptions 95 "$TMP_DIR/land.png" --out "$LAND_JPG" >/dev/null

echo "cover: $SRC"
echo "port:  $PORT_JPG"
echo "land:  $LAND_JPG"
