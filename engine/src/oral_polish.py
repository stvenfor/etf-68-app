"""Rule-based oral polish for ETF-68 narration (huashu-script-polish adapted).

Goals: shorter spoken cadence, less broadcast stiff openers, light connectors.
Guardrails: preserve numbers / % / 手 / headlines / PMI facts; never invent codes.
"""

from __future__ import annotations

import re
from typing import Any, Literal

Kind = Literal["review", "macro"]

# Tokens that must survive polish unchanged (facts + product-critical phrases).
_FACT_RE = re.compile(
    r"(?:"
    r"[+-]?\d+(?:\.\d+)?%"  # +6.50% / 49.2%
    r"|百分之\d+(?:\.\d+)?"
    r"|\d+(?:\.\d+)?个百分点"
    r"|\d+手"
    r"|净加[多空]\d+手"
    r"|持平"
    r"|本月总体净[多空]\d+手"
    r"|\d{4}-\d{2}-\d{2}"
    r"|\d{4}年\d{1,2}月"
    r"|荣枯线"
    r"|不构成投资建议"
    r"|仅供参考"
    r")"
)

# Stiff → spoken (order matters; longer patterns first).
_REVIEW_REPLACEMENTS: list[tuple[str, str]] = [
    ("复盘结束。数据来源于网络，仅供参考。", "好，今天就聊到这儿。数据来自网络，仅供参考。"),
    ("数据来源于网络，仅供参考。", "数据来自网络，仅供参考。"),
    ("ETF六十八市场复盘。数据日期", "嗨，来看ETF六十八市场复盘啊，数据日期"),
    ("市场温度百分之", "今天市场温度差不多百分之"),
    ("板块均涨跌。", "先瞅一眼板块均涨跌。"),
    ("涨幅前三：", "涨得最猛的三个是："),
    ("跌幅前三：", "跌得最多的三个是："),
    ("暂无板块收益数据。", "今天暂时没有板块收益数据。"),
    ("持仓量变动。", "再说说持仓量变动。"),
    ("实质消息。", "消息面扫一眼。"),
    ("利好：", "利好这边："),
    ("利空：", "利空这边："),
]

_MACRO_REPLACEMENTS: list[tuple[str, str]] = [
    ("数据来源于网络，不构成投资建议。", "数据来自网络，不构成投资建议。"),
    ("看核心读数：", "先看核心读数："),
    ("如何理解这次回落？", "怎么理解这次回落？"),
    ("是关键验证窗口。关注：", "是关键验证窗口，重点看："),
    ("新订单脚注：", "新订单这边补充："),
    ("本期到这里。", "好，本期到这里。"),
    ("但不构成操作建议。", "不过这不构成操作建议。"),
]


def fact_tokens(text: str) -> list[str]:
    """Extract fact-like spans that polish must not drop."""
    return _FACT_RE.findall(text or "")


def _apply_replacements(text: str, pairs: list[tuple[str, str]]) -> str:
    out = text
    for old, new in pairs:
        out = out.replace(old, new)
    return out


def _split_long_clauses(text: str, *, max_chars: int = 28) -> str:
    """Prefer shorter spoken beats: turn long顿号/逗号 runs into periods when safe."""
    # Only split on Chinese commas inside very long sentences; keep titles intact.
    parts: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in "。！？":
            parts.append(buf)
            buf = ""
    if buf:
        parts.append(buf)

    rebuilt: list[str] = []
    for sent in parts:
        if len(sent) <= max_chars or "利好" in sent or "利空" in sent:
            rebuilt.append(sent)
            continue
        # Soft-split on ； when sentence is long
        if "；" in sent and len(sent) > max_chars:
            chunks = [c for c in sent.rstrip("。").split("；") if c]
            if len(chunks) > 1:
                rebuilt.append("。".join(chunks) + ("。" if sent.endswith("。") else ""))
                continue
        rebuilt.append(sent)
    return "".join(rebuilt)


def polish_narration(
    text: str,
    *,
    kind: Kind = "review",
    chapter_id: str | None = None,
) -> str:
    """Polish one chapter narration. Returns original if facts would be lost."""
    raw = (text or "").strip()
    if not raw:
        return raw

    required = fact_tokens(raw)
    # News headlines after markers — keep whole titles by not rewriting insides.
    pairs = _REVIEW_REPLACEMENTS if kind == "review" else _MACRO_REPLACEMENTS
    out = _apply_replacements(raw, pairs)

    # Chapter-local tweaks (avoid touching news titles / mid-string collisions).
    if kind == "review" and chapter_id == "candidates":
        if out.startswith("技术候选。今日暂无技术候选。"):
            out = "技术候选这边。今天暂时没有技术候选。" + out[
                len("技术候选。今日暂无技术候选。") :
            ]
        elif out.startswith("技术候选。"):
            out = "技术候选这边。" + out[len("技术候选。") :]
        out = out.replace("当日", "当天").replace("五日", "近五日")
    if kind == "macro" and chapter_id == "hook" and "国家统计局公布" in out:
        out = out.replace("国家统计局公布采购经理指数。", "国家统计局刚公布采购经理指数。", 1)

    out = _split_long_clauses(out)

    # Guard: every prior fact token must still appear
    for tok in required:
        if tok and tok not in out:
            return raw
    return out


def polish_chapters(
    chapters: list[dict[str, Any]],
    *,
    kind: Kind,
) -> list[dict[str, Any]]:
    """Return a shallow-copied chapter list with polished narrations."""
    out: list[dict[str, Any]] = []
    for ch in chapters:
        item = dict(ch)
        nar = str(item.get("narration") or "")
        item["narration"] = polish_narration(
            nar, kind=kind, chapter_id=str(item.get("id") or "") or None
        )
        out.append(item)
    return out


def polish_script(script: dict[str, Any], *, kind: Kind) -> dict[str, Any]:
    """Polish in-place copy of a script JSON; recompute fullNarration when present."""
    if not script.get("ok"):
        return script
    chapters = script.get("chapters")
    if not isinstance(chapters, list):
        return script
    polished = dict(script)
    polished["chapters"] = polish_chapters(chapters, kind=kind)
    polished["fullNarration"] = "".join(
        str(c.get("narration") or "") for c in polished["chapters"]
    )
    polished["oralPolish"] = True
    return polished
