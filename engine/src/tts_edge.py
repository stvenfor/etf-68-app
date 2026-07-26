"""Edge TTS helper: natural Chinese speech with light prosody via SSML."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

DEFAULT_VOICE = os.environ.get("ETF68_TTS_VOICE", "zh-CN-XiaoxiaoNeural")
DEFAULT_RATE = os.environ.get("ETF68_TTS_RATE", "-8%")
DEFAULT_PITCH = os.environ.get("ETF68_TTS_PITCH", "+0Hz")

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？；…])")


def _split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", "", text.strip())
    if not cleaned:
        return []
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(cleaned) if p and p.strip()]
    return parts or [cleaned]


def build_ssml(
    text: str,
    *,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    break_ms: int = 320,
) -> str:
    """Wrap plain Chinese into SSML with short pauses between sentences."""
    sentences = _split_sentences(text)
    body_parts: list[str] = []
    for i, sentence in enumerate(sentences):
        body_parts.append(escape(sentence))
        if i < len(sentences) - 1:
            body_parts.append(f'<break time="{break_ms}ms"/>')
    inner = "".join(body_parts)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">'
        f'<voice name="{escape(voice)}">'
        f'<prosody rate="{escape(rate)}" pitch="{escape(pitch)}">{inner}</prosody>'
        "</voice></speak>"
    )


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

    ssml = build_ssml(text, voice=voice, rate=rate, pitch=pitch)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(ssml, voice)
    await communicate.save(str(out_path))
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
    raw = f"{voice}|{rate}|{pitch}|{text}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]
