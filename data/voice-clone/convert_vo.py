#!/usr/bin/env python3
"""Convert Xiaoxiao VO wavs to reference speaker tone via OpenVoice V2."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent
OV = ROOT / "OpenVoice"
sys.path.insert(0, str(OV))

from openvoice.api import ToneColorConverter  # noqa: E402


def device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


def main() -> int:
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    ref = Path(os.environ.get("ETF68_VO_REF", str(ROOT / "reference.wav")))
    if not ref.exists():
        raise SystemExit(f"missing reference wav: {ref}")
    src_dir = Path(
        os.environ.get(
            "ETF68_VO_SRC",
            "/Users/mac/Desktop/work/videos/etf68-daily-review/assets/vo",
        )
    )
    out_dir = Path(os.environ.get("ETF68_VO_OUT", str(ROOT / "converted")))
    out_dir.mkdir(parents=True, exist_ok=True)

    ckpt_cfg = OV / "checkpoints_v2" / "converter" / "config.json"
    ckpt = OV / "checkpoints_v2" / "converter" / "checkpoint.pth"
    if not ckpt.exists():
        raise SystemExit(f"missing checkpoint: {ckpt}")

    dev = device()
    print(f"device={dev}")
    converter = ToneColorConverter(str(ckpt_cfg), device=dev, enable_watermark=False)
    converter.load_ckpt(str(ckpt))

    print(f"extract target SE from {ref}")
    se_path = Path(os.environ.get("ETF68_VO_SE", str(ROOT / "target_se.pth")))
    tgt_se = converter.extract_se([str(ref)], se_save_path=str(se_path))

    chapters_env = os.environ.get("ETF68_VO_CHAPTERS", "").strip()
    if chapters_env:
        chapters = [c.strip() for c in chapters_env.split(",") if c.strip()]
    else:
        chapters = ["open", "sectors", "movers", "citic", "news", "candidates", "close"]
    for name in chapters:
        src = src_dir / f"{name}.wav"
        if not src.exists():
            print(f"skip missing {src}")
            continue
        dst = out_dir / f"{name}.wav"
        print(f"convert {src.name} -> {dst}")
        # Source speaker embedding from the Xiaoxiao clip itself.
        src_se = converter.extract_se([str(src)])
        converter.convert(
            audio_src_path=str(src),
            src_se=src_se,
            tgt_se=tgt_se,
            output_path=str(dst),
            tau=float(os.environ.get("ETF68_VO_TAU", "0.75")),
            message="@etf68",
        )
        print(f"  wrote {dst} ({dst.stat().st_size} bytes)")

    print("done", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
