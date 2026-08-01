#!/usr/bin/env python3
"""Validate vertical MP4 metadata and prove sampled frames change."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run(*command: str) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--min-duration", type=float, default=10.0)
    parser.add_argument("--max-duration", type=float, default=16.0)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    args = parser.parse_args()
    if not args.video.is_file():
        raise SystemExit(f"Missing video: {args.video}")

    probe = json.loads(run(
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(args.video)
    ))
    video_streams = [s for s in probe["streams"] if s["codec_type"] == "video"]
    audio_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    if len(video_streams) != 1:
        raise SystemExit(f"Expected one video stream, got {len(video_streams)}")
    # Silent AAC is required for Cursor/QuickTime preview continuity; reject extra tracks.
    if len(audio_streams) > 1:
        raise SystemExit(f"Expected at most one audio stream, got {len(audio_streams)}")
    if audio_streams and audio_streams[0].get("codec_name") not in ("aac", "mp3"):
        raise SystemExit(
            f"Unexpected audio codec={audio_streams[0].get('codec_name')!r}; use silent AAC"
        )
    stream = video_streams[0]
    duration = float(stream.get("duration") or probe["format"]["duration"])
    expected = {
        "codec_name": "h264",
        "width": args.width,
        "height": args.height,
        "pix_fmt": "yuv420p",
    }
    for key, value in expected.items():
        if stream.get(key) != value:
            raise SystemExit(f"Expected {key}={value!r}, got {stream.get(key)!r}")
    # color_space may be missing on some encoders; prefer bt709 when present
    color_space = stream.get("color_space")
    if color_space not in (None, "bt709", "unknown"):
        raise SystemExit(f"Unexpected color_space={color_space!r}")
    if stream.get("r_frame_rate") != "30/1":
        raise SystemExit(f"Expected 30fps, got {stream.get('r_frame_rate')}")
    if not args.min_duration <= duration <= args.max_duration:
        raise SystemExit(f"Duration {duration:.3f}s is outside accepted range")

    frame_md5 = run(
        "ffmpeg", "-v", "error", "-i", str(args.video), "-vf", "fps=1", "-f", "framemd5", "-"
    )
    hashes = {
        line.rsplit(",", 1)[-1].strip()
        for line in frame_md5.splitlines()
        if line and not line.startswith("#") and "," in line
    }
    if len(hashes) < 3:
        raise SystemExit(f"Only {len(hashes)} unique sampled frames; animation may be frozen")

    atoms = args.video.read_bytes()
    moov, mdat = atoms.find(b"moov"), atoms.find(b"mdat")
    if moov < 0 or mdat < 0 or moov > mdat:
        raise SystemExit("MP4 is not fast-start optimized (moov must precede mdat)")

    print(json.dumps({
        "status": "ok",
        "video": str(args.video),
        "duration": duration,
        "frames": int(stream.get("nb_frames", 0)),
        "uniqueOneSecondSamples": len(hashes),
        "codec": stream["codec_name"],
        "pixelFormat": stream["pix_fmt"],
        "colorSpace": color_space,
        "fastStart": True,
        "hasSilentAudio": bool(audio_streams),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
