#!/usr/bin/env bash
# Remotion --muted MP4s often stop ~2s in Cursor/QuickTime HTML5 preview.
# Rebuild with exact-length silent AAC + faststart so A/V durations match.
set -euo pipefail
src="${1:?usage: remux_previewable.sh <mp4>}"
tmp="${src%.mp4}.preview-tmp.mp4"
dur="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$src")"
ffmpeg -y -i "$src" -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
  -map 0:v:0 -map 1:a:0 -t "$dur" \
  -c:v copy \
  -c:a aac -b:a 128k -ar 48000 -ac 2 \
  -movflags +faststart \
  "$tmp"
mv "$tmp" "$src"
echo "remuxed silent AAC (${dur}s) + faststart -> $src"
