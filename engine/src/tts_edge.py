"""Edge TTS helper: natural Chinese speech with per-clause prosody variation.

Current ``edge-tts`` does not reliably parse SSML (tags may be spoken aloud).
Prosody is applied via ``Communicate(rate=..., pitch=...)`` per clause, then
concatenated with short gaps.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_VOICE = os.environ.get("ETF68_TTS_VOICE", "zh-CN-XiaoxiaoNeural")
DEFAULT_RATE = os.environ.get("ETF68_TTS_RATE", "+0%")
DEFAULT_PITCH = os.environ.get("ETF68_TTS_PITCH", "+0Hz")

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？；…，,])")
_RETRY_SLEEP_S = 0.45

_PROSODY = (
    {"rate": "+8%", "pitch": "+4Hz"},
    {"rate": "-6%", "pitch": "-2Hz"},
    {"rate": "+3%", "pitch": "+6Hz"},
    {"rate": "-2%", "pitch": "+1Hz"},
    {"rate": "+10%", "pitch": "-1Hz"},
    {"rate": "+0%", "pitch": "+3Hz"},
)


def _gap_s(clause: str) -> float:
    """Short natural pause after a clause; longer after numbers / sentence end."""
    if re.search(r"\d", clause):
        return 0.18
    if clause[-1:] in "。！？…":
        return 0.16
    return 0.11


def _split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", "", text.strip())
    cleaned = cleaned.replace("…", "。").replace("...", "。")
    if not cleaned:
        return []
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(cleaned) if p and p.strip()]
    # Drop punctuation-only fragments; merge ultra-short bits into neighbors.
    merged: list[str] = []
    for p in parts:
        core = re.sub(r"[。！？；…：:；;，,\s]+", "", p)
        if not core:
            continue
        # Keep titles with "：" intact as one clause (no split on colon).
        if len(core) < 4 and merged:
            merged[-1] = merged[-1] + p
        else:
            merged.append(p)
    return merged or [cleaned]


def _speakable(text: str) -> str:
    """Normalize symbols Edge TTS often rejects (+4.05% / -1300)."""
    t = text
    # +1.23% → 正1.23%； -1.23% → 负1.23%
    t = re.sub(r"\+(\d+(?:\.\d+)?)%", r"正\1%", t)
    t = re.sub(r"-(\d+(?:\.\d+)?)%", r"负\1%", t)
    # lone signed lots: -1300手 → 负1300手
    t = re.sub(r"(?<![正负])-(\d+)手", r"负\1手", t)
    return t


def _pick_prosody(sentence: str, index: int, *, rate: str, pitch: str) -> tuple[str, str]:
    """Blend base rate/pitch with clause-level contour and gain/loss cues."""
    base = _PROSODY[index % len(_PROSODY)]
    clause_rate, clause_pitch = base["rate"], base["pitch"]
    if any(k in sentence for k in ("涨", "利好", "加多", "正")):
        clause_rate, clause_pitch = "+8%", "+7Hz"
    elif any(k in sentence for k in ("跌", "利空", "加空", "负")):
        clause_rate, clause_pitch = "-6%", "-4Hz"
    if rate not in ("+0%", "0%", "-8%"):
        clause_rate = rate
    if pitch not in ("+0Hz", "0Hz"):
        clause_pitch = pitch
    return clause_rate, clause_pitch


def build_ssml(
    text: str,
    *,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    break_ms: int = 280,
) -> str:
    """Deprecated compatibility helper — returns plain text (no SSML)."""
    del voice, rate, pitch, break_ms
    return re.sub(r"\s+", "", text.strip())


async def _synth_clause(edge_tts, text: str, out: Path, voice: str, rate: str, pitch: str) -> bool:
    """Synthesize one clause; retry on transient Edge / network failures."""
    spoken = _speakable(text)
    attempts = (
        (rate, pitch),
        ("+0%", pitch if pitch not in ("+0Hz", "0Hz") else "+0Hz"),
        ("+0%", "+0Hz"),
        ("-5%", "+0Hz"),
        ("+5%", "+0Hz"),
    )
    for attempt, (r, p) in enumerate(attempts):
        try:
            if out.exists():
                out.unlink(missing_ok=True)
            await edge_tts.Communicate(spoken, voice, rate=r, pitch=p).save(str(out))
            if out.exists() and out.stat().st_size >= 200:
                return True
        except Exception:
            if out.exists():
                out.unlink(missing_ok=True)
            await asyncio.sleep(_RETRY_SLEEP_S * (1 + 0.35 * attempt))
            continue
        await asyncio.sleep(_RETRY_SLEEP_S)
    return False


async def synthesize_to_file(
    text: str,
    out_path: Path,
    *,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> dict[str, Any]:
    try:
        import edge_tts
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("edge_tts_missing: pip install edge-tts") from exc

    clauses = _split_sentences(text)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        wavs: list[Path] = []
        kept = 0
        skipped: list[str] = []
        for i, clause in enumerate(clauses):
            cr, cp = _pick_prosody(clause, i, rate=rate, pitch=pitch)
            mp3 = td_path / f"{i:03d}.mp3"
            ok = await _synth_clause(edge_tts, clause, mp3, voice, cr, cp)
            if not ok:
                skipped.append(clause)
                print(f"tts skip clause: {clause!r}")
                continue
            wav = td_path / f"{i:03d}.wav"
            subprocess.check_call(
                ["ffmpeg", "-y", "-i", str(mp3), "-ac", "1", "-ar", "24000", str(wav)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if wavs:
                gap = td_path / f"{i:03d}_gap.wav"
                prev = clauses[i - 1] if i > 0 else clause
                subprocess.check_call(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=r=24000:cl=mono",
                        "-t",
                        f"{_gap_s(prev):.3f}",
                        str(gap),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                wavs.append(gap)
            wavs.append(wav)
            kept += 1

        if skipped and kept == 0:
            # Whole-text fallback
            mp3 = td_path / "all.mp3"
            ok = await _synth_clause(edge_tts, re.sub(r"\s+", "", text.strip()), mp3, voice, "+0%", "+0Hz")
            if not ok:
                raise RuntimeError("tts_empty_audio")
            wav = td_path / "all.wav"
            subprocess.check_call(
                ["ffmpeg", "-y", "-i", str(mp3), "-ac", "1", "-ar", "24000", str(wav)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            wavs = [wav]
            kept = 1
        elif skipped:
            # Partial skips still risk incomplete VO — try whole-text rescue once
            print(f"tts warning: skipped {len(skipped)} clause(s), retrying whole chapter")
            mp3 = td_path / "all.mp3"
            ok = await _synth_clause(edge_tts, re.sub(r"\s+", "", text.strip()), mp3, voice, "+0%", "+0Hz")
            if ok:
                wav = td_path / "all.wav"
                subprocess.check_call(
                    ["ffmpeg", "-y", "-i", str(mp3), "-ac", "1", "-ar", "24000", str(wav)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                wavs = [wav]
                kept = 1

        if not wavs:
            raise RuntimeError("tts_empty_audio")

        lst = td_path / "list.txt"
        lst.write_text("".join(f"file '{w}'\n" for w in wavs), encoding="utf-8")
        # Prefer wav out; if caller asked mp3, write wav then ffmpeg encode.
        tmp_wav = td_path / "joined.wav"
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
                str(tmp_wav),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if out_path.suffix.lower() == ".wav":
            tmp_wav.replace(out_path)
        else:
            subprocess.check_call(
                ["ffmpeg", "-y", "-i", str(tmp_wav), str(out_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    size = out_path.stat().st_size if out_path.exists() else 0
    if size < 256:
        raise RuntimeError("tts_empty_audio")
    return {
        "ok": True,
        "path": str(out_path),
        "bytes": size,
        "voice": voice,
        "rate": rate,
        "pitch": pitch,
        "clauses": kept,
    }


def synthesize(
    text: str,
    out_path: Path,
    *,
    voice: str | None = None,
    rate: str | None = None,
    pitch: str | None = None,
) -> dict[str, Any]:
    return asyncio.run(
        synthesize_to_file(
            text,
            out_path,
            voice=voice or DEFAULT_VOICE,
            rate=rate or DEFAULT_RATE,
            pitch=pitch or DEFAULT_PITCH,
        )
    )


def cache_key(text: str, voice: str, rate: str, pitch: str) -> str:
    raw = f"{voice}|{rate}|{pitch}|expr-v2|{text}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]
