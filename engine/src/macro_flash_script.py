"""Build a short macro-flash narration script from a PMI snapshot.

Chapters: hook → facts → why → window → close.
Metaphor tone is configurable; facts always follow snapshot numbers.
"""

from __future__ import annotations

from typing import Any, Literal

Tone = Literal["neutral", "caution"]

CHAPTER_IDS = ("hook", "facts", "why", "window", "close")

CHAPTER_LABELS_ZH = {
    "hook": "开场",
    "facts": "数据",
    "why": "解读",
    "window": "验证窗口",
    "close": "收束",
}

CHAPTER_LABELS_EN = {
    "hook": "Hook",
    "facts": "Facts",
    "why": "Why",
    "window": "Window",
    "close": "Close",
}

DISCLAIMER = "数据来源于网络，不构成投资建议。"


def _fmt_val(v: Any, *, digits: int = 1) -> str:
    if v is None:
        return "暂无"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "暂无"
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x))}" if digits == 0 else f"{x:.{digits}f}".rstrip("0").rstrip(".")
    return f"{x:.{digits}f}"


def _fmt_pct_index(v: Any) -> str:
    """PMI-style index spoken/written as e.g. 49.2%."""
    s = _fmt_val(v, digits=1)
    if s == "暂无":
        return s
    return f"{s}%"


def _fmt_mom(v: Any) -> str:
    if v is None:
        return ""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return ""
    sign = "+" if x > 0 else ""
    return f"{sign}{_fmt_val(x, digits=1)}个百分点"


def _month_cn(month: str) -> str:
    """2026-07 → 2026年7月"""
    try:
        y, m = month.split("-", 1)
        return f"{int(y)}年{int(m)}月"
    except (TypeError, ValueError):
        return month


def _next_month_cn(month: str | None, forward: str | None) -> str:
    if forward:
        return _month_cn(str(forward))
    if not month or "-" not in month:
        return "下一月"
    y, m = month.split("-", 1)
    yi, mi = int(y), int(m)
    mi += 1
    if mi > 12:
        mi = 1
        yi += 1
    return f"{yi}年{mi}月"


def _hook_metaphor(*, tone: Tone, sync: bool) -> str:
    if tone == "caution":
        if sync:
            return "制造业与服务业景气同步落入收缩区间，宏观温度明显转冷"
        return "制造业景气跌破荣枯线，宏观温度转冷"
    if sync:
        return "制造业与服务业景气同步回落至荣枯线之下"
    return "制造业景气回落至荣枯线之下"


def _metric_rows(snap: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("manufacturing", "nonManufacturing", "composite"):
        m = snap.get(key)
        if isinstance(m, dict) and m.get("value") is not None:
            rows.append(m)
    for d in snap.get("details") or []:
        if isinstance(d, dict) and d.get("value") is not None:
            # Prefer core trio + new/export orders on facts screen
            if d.get("id") in ("new_orders", "export_orders"):
                rows.append(d)
    return rows


def build_macro_flash_script(
    snap: dict[str, Any],
    *,
    tone: Tone = "neutral",
    brand: str = "ETF-68 宏观快评",
) -> dict[str, Any]:
    if not snap.get("ok"):
        return {"ok": False, "error": snap.get("error") or "bad_snapshot", "chapters": []}

    month = str(snap.get("month") or "")
    month_cn = _month_cn(month)
    window_cn = _next_month_cn(month, snap.get("forwardWindowMonth"))
    mfg = snap.get("manufacturing") or {}
    nm = snap.get("nonManufacturing") or {}
    comp = snap.get("composite") if isinstance(snap.get("composite"), dict) else None
    flags = snap.get("flags") or {}
    sync = bool(flags.get("syncContract"))
    metaphor = _hook_metaphor(tone=tone, sync=sync)

    mfg_s = _fmt_pct_index(mfg.get("value"))
    mfg_prev = _fmt_pct_index(mfg.get("prev"))
    mfg_mom = _fmt_mom(mfg.get("momPp"))
    nm_s = _fmt_pct_index(nm.get("value"))
    comp_s = _fmt_pct_index(comp.get("value")) if comp else None

    details_by_id = {
        str(d.get("id")): d for d in (snap.get("details") or []) if isinstance(d, dict)
    }
    new_orders = details_by_id.get("new_orders") or {}
    export_orders = details_by_id.get("export_orders") or {}

    hook_nar = (
        f"{month_cn}，国家统计局公布采购经理指数。"
        f"制造业PMI报{mfg_s}"
        + (f"，较上月{mfg_mom}" if mfg_mom else "")
        + f"。{metaphor}。"
    )
    if sync and nm.get("value") is not None:
        hook_nar += f"非制造业商务活动指数同步报{nm_s}。"
    if comp_s:
        hook_nar += f"综合PMI产出指数为{comp_s}。"
    hook_nar += f"荣枯线是五十：高于扩张，低于收缩。{window_cn}将是验证窗口。"

    facts_bits = [
        f"制造业从{mfg_prev}到{mfg_s}" if mfg.get("prev") is not None else f"制造业{mfg_s}",
        f"非制造业{nm_s}" if nm.get("value") is not None else "",
    ]
    if new_orders.get("value") is not None:
        mom = _fmt_mom(new_orders.get("momPp"))
        facts_bits.append(
            f"新订单{_fmt_pct_index(new_orders.get('value'))}" + (f"，{mom}" if mom else "")
        )
    if export_orders.get("value") is not None:
        facts_bits.append(f"出口新订单{_fmt_pct_index(export_orders.get('value'))}")
    if comp_s:
        facts_bits.append(f"综合产出{comp_s}")
    facts_nar = "看核心读数：" + "；".join(b for b in facts_bits if b) + "。"
    if new_orders.get("note"):
        facts_nar += f"新订单脚注：{new_orders['note']}。"

    interp = [str(x) for x in (snap.get("interpretation") or []) if str(x).strip()]
    if not interp:
        interp = [
            "季节性淡季与天气扰动可解释部分回落",
            "需求端指标走弱时，不能只归因于季节",
            "产业结构上扩张与收缩并存，均值会掩盖分化",
        ]
    why_nar = "如何理解这次回落？" + "".join(f"{i + 1}，{t}。" for i, t in enumerate(interp[:3]))

    signals = [s for s in (snap.get("signals") or []) if isinstance(s, dict)]
    if not signals:
        signals = [
            {"label": f"{window_cn}PMI", "value": "是否回到五十以上", "note": "区分季节与趋势"},
            {"label": "外需", "value": "出口是否明显降温", "note": "制造业支撑"},
            {"label": "地产链条", "value": "建筑与房价节奏", "note": "居民端信心"},
        ]
    window_nar = f"{window_cn}是关键验证窗口。关注："
    for i, s in enumerate(signals[:3], 1):
        window_nar += f"{i}，{s.get('label')}——{s.get('value')}。"
        if s.get("note"):
            window_nar += f"{s['note']}。"
    window_nar += "答案会影响下半年政策节奏与市场风险偏好的讨论，但不构成操作建议。"

    close_nar = f"{brand}本期到这里。{DISCLAIMER}"

    chapters: list[dict[str, Any]] = []
    payloads = [
        (
            "hook",
            hook_nar,
            {
                "metaphor": metaphor,
                "tags": [f"PMI {mfg_s}", f"{window_cn}验证"],
                "headline": metaphor,
                "subhead": (
                    f"{month_cn}制造业{mfg_s}"
                    + (f"，非制造业{nm_s}" if nm.get("value") is not None else "")
                    + (f"，综合{comp_s}" if comp_s else "")
                ),
            },
        ),
        (
            "facts",
            facts_nar,
            {
                "metrics": _metric_rows(snap),
                "quote": "需求侧指标走弱时，生产意愿再高也难独自撑起景气。",
            },
        ),
        (
            "why",
            why_nar,
            {
                "points": interp[:3],
                "quote": "季节扰动与结构压力可能叠加，均值会掩盖行业冰火两重天。",
                "splitMetrics": [
                    d
                    for d in (snap.get("details") or [])
                    if isinstance(d, dict) and d.get("id") in (
                        "hi_tech",
                        "equipment",
                        "consumer",
                        "energy_heavy",
                        "construction",
                    )
                ],
            },
        ),
        (
            "window",
            window_nar,
            {
                "windowMonth": window_cn,
                "signals": signals[:3],
                "quote": f"{window_cn}将区分季节回升与趋势确认。",
            },
        ),
        (
            "close",
            close_nar,
            {"disclaimer": DISCLAIMER, "brand": brand},
        ),
    ]

    for cid, narration, body in payloads:
        chapters.append(
            {
                "id": cid,
                "title": CHAPTER_LABELS_ZH[cid],
                "titleEn": CHAPTER_LABELS_EN[cid],
                "kicker": f"{CHAPTER_IDS.index(cid) + 1}/{len(CHAPTER_IDS)}",
                "narration": narration,
                "body": body,
            }
        )

    title = f"{month_cn}PMI快评：{metaphor}"
    return {
        "ok": True,
        "kind": "macro-flash",
        "month": month,
        "tone": tone,
        "brand": brand,
        "title": title,
        "titleSuggest": title,
        "hashtags": ["#pmi", "#经济", "#宏观快评"],
        "disclaimer": DISCLAIMER,
        "watermark": "小哈的一天快乐",
        "chapters": chapters,
        "source": {
            "asOf": snap.get("asOf"),
            "source": snap.get("source"),
            "sourceUrl": snap.get("sourceUrl"),
        },
    }
