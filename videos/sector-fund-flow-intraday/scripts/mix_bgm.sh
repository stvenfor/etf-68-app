#!/usr/bin/env bash
# Mix public/royalty-light BGM onto a rendered MP4.
# - BGM shorter than video → seamless loop until video ends
# - BGM longer than video → trim to exact video duration
# Output duration always matches the video stream.
set -euo pipefail

src="${1:?usage: mix_bgm.sh <video.mp4> [bgm.wav|mp3] [gain_db]}"
bgm="${2:-}"
# Linear volume OR "NdB" / loudnorm target. Default: loudnorm to -18 LUFS
# (this project's public bed is very quiet raw; linear 0.12 is inaudible alone).
gain="${3:-loudnorm}"

if [[ -z "$bgm" ]]; then
  for cand in \
    "$(dirname "$0")/../assets/bgm.wav" \
    "/Users/mac/Desktop/github/etf-68-app/public-music/default-bgm.wav" \
    "/Users/mac/Desktop/github/etf-68-app/public-music/sathop-down-modan.wav" \
    "/Users/mac/Desktop/work/videos/etf68-daily-review/assets/bgm-loop.wav" \
    "/Users/mac/Desktop/work/videos/etf68-daily-review/assets/bgm.wav"
  do
    if [[ -f "$cand" ]]; then
      bgm="$cand"
      break
    fi
  done
fi
[[ -f "$bgm" ]] || { echo "BGM not found"; exit 1; }

dur="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$src")"
bgm_dur="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$bgm")"
tmp="${src%.mp4}.bgm-tmp.mp4"
fade_start="$(python3 -c "print(max(0, float('${dur}')-0.6))")"

if [[ "$gain" == "loudnorm" ]]; then
  afilter="loudnorm=I=-18:TP=-1.5:LRA=11,atrim=0:${dur},asetpts=PTS-STARTPTS,afade=t=out:st=${fade_start}:d=0.6"
elif [[ "$gain" == *dB || "$gain" == *db ]]; then
  afilter="volume=${gain},atrim=0:${dur},asetpts=PTS-STARTPTS,afade=t=out:st=${fade_start}:d=0.6"
else
  afilter="volume=${gain},atrim=0:${dur},asetpts=PTS-STARTPTS,afade=t=out:st=${fade_start}:d=0.6"
fi

echo "video=${dur}s bgm=${bgm_dur}s gain=${gain} src=$(basename "$bgm")"

# Always loop BGM, then atrim to exact video length (short→loop, long→trim).
ffmpeg -y -i "$src" -stream_loop -1 -i "$bgm" \
  -filter_complex "[1:a]${afilter}[a]" \
  -map 0:v:0 -map "[a]" -t "$dur" \
  -c:v copy \
  -c:a aac -b:a 160k -ar 48000 -ac 2 \
  -movflags +faststart \
  "$tmp"

mv "$tmp" "$src"
echo "mixed BGM -> $src (duration=${dur}s)"
