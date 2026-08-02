#!/usr/bin/env python3
"""Expressive Xiaoxiao (per-clause rate/pitch) + OpenVoice convert to reference timbre.

Note: current edge-tts does not honor SSML when passed as text (it reads tags aloud).
We synthesize clause-by-clause with Communicate(rate=..., pitch=...) and concat.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent
META = Path("/Users/mac/Desktop/work/videos/etf68-daily-review/audio_meta.json")
VOICE = "zh-CN-XiaoxiaoNeural"
EXPR_DIR = ROOT / "expressive_src"
OUT_DIR = ROOT / "converted"

_STYLES = [
    {"rate": "+8%", "pitch": "+4Hz"},
    {"rate": "-6%", "pitch": "-2Hz"},
    {"rate": "+3%", "pitch": "+6Hz"},
    {"rate": "-2%", "pitch": "+1Hz"},
    {"rate": "+10%", "pitch": "-1Hz"},
    {"rate": "+0%", "pitch": "+3Hz"},
]


def split_clauses(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", "", (text or "").strip())
    if not cleaned:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[。！？；…：:；;，,])", cleaned) if p and p.strip()]
    out: list[str] = []
    for p in parts or [cleaned]:
        # Drop punctuation-only / too-short fragments that Edge TTS rejects.
        core = re.sub(r"[。！？；…：:；;，,\s\.…]+", "", p)
        if len(core) < 2:
            continue
        out.append(p)
    return out or [cleaned]


def pick_prosody(sent: str, i: int) -> dict[str, str]:
    base = dict(_STYLES[i % len(_STYLES)])
    if any(k in sent for k in ("涨", "利好", "加多", "+")) and not any(
        k in sent for k in ("跌", "利空")
    ):
        return {"rate": "+8%", "pitch": "+7Hz"}
    if any(k in sent for k in ("跌", "利空")):
        return {"rate": "-6%", "pitch": "-4Hz"}
    return base


async def synth_clause(text: str, out: Path, rate: str, pitch: str) -> None:
    try:
        await edge_tts.Communicate(text, VOICE, rate=rate, pitch=pitch).save(str(out))
    except Exception:
        # Fallback: default prosody (some clauses reject extreme rate/pitch).
        await edge_tts.Communicate(text, VOICE, rate="+0%", pitch="+0Hz").save(str(out))
    if not out.exists() or out.stat().st_size < 200:
        raise RuntimeError(f"no audio for clause: {text!r}")


async def synth_chapter(text: str, out_wav: Path) -> None:
    clauses = split_clauses(text)
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        parts: list[Path] = []
        for i, clause in enumerate(clauses):
            pros = pick_prosody(clause, i)
            mp3 = td_path / f"{i:03d}.mp3"
            await synth_clause(clause, mp3, pros["rate"], pros["pitch"])
            parts.append(mp3)
            # short breath between clauses
            silence = td_path / f"{i:03d}_gap.wav"
            subprocess.check_call(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=24000:cl=mono",
                    "-t",
                    "0.28",
                    str(silence),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            parts.append(silence)

        # concat list
        lst = td_path / "list.txt"
        wavs: list[Path] = []
        for p in parts:
            if p.suffix == ".mp3":
                w = p.with_suffix(".wav")
                subprocess.check_call(
                    ["ffmpeg", "-y", "-i", str(p), "-ac", "1", "-ar", "24000", str(w)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                wavs.append(w)
            else:
                wavs.append(p)
        # drop trailing gap
        if wavs and wavs[-1].name.endswith("_gap.wav"):
            wavs = wavs[:-1]
        lst.write_text("".join(f"file '{w}'\n" for w in wavs), encoding="utf-8")
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        subprocess.check_call(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(lst),
                "-c",
                "copy",
                str(out_wav),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


async def synth_all(voices: list[dict]) -> None:
    EXPR_DIR.mkdir(parents=True, exist_ok=True)
    for v in voices:
        wav = EXPR_DIR / f"{v['id']}.wav"
        print(f"tts {v['id']} ({len(split_clauses(v['text']))} clauses)…")
        await synth_chapter(v["text"], wav)
        dur = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(wav),
            ],
            text=True,
        ).strip()
        print(f"  {wav.name} {dur}s")


def convert_all(voices: list[dict]) -> None:
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    sys.path.insert(0, str(ROOT / "OpenVoice"))
    import torch
    from openvoice.api import ToneColorConverter

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    cfg = ROOT / "OpenVoice/checkpoints_v2/converter/config.json"
    ckpt = ROOT / "OpenVoice/checkpoints_v2/converter/checkpoint.pth"
    conv = ToneColorConverter(str(cfg), device=dev, enable_watermark=False)
    conv.load_ckpt(str(ckpt))
    tgt = conv.extract_se([str(ROOT / "reference.wav")])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for v in voices:
        src = EXPR_DIR / f"{v['id']}.wav"
        dst = OUT_DIR / f"{v['id']}.wav"
        print(f"vc {v['id']}…")
        src_se = conv.extract_se([str(src)])
        conv.convert(str(src), src_se, tgt, output_path=str(dst), tau=0.65)
        print(f"  -> {dst.stat().st_size} bytes")


def main() -> int:
    voices = json.loads(META.read_text(encoding="utf-8"))["voices"]
    asyncio.run(synth_all(voices))
    convert_all(voices)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
