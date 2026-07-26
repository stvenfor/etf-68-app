"""Build a compact daily market-review script from a UiBundle."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


TARGET_DURATION_S = 70.0

# Soft hints only — VO is never hard-trimmed to fit.
CHAPTER_BUDGETS = {
    "open": 6.0,
    "sectors": 14.0,
    "movers": 14.0,
    "citic": 7.0,
    "news": 16.0,
    "candidates": 22.0,
    "close": 5.0,
}


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    return x


def _fmt_pct(v: float | None, *, digits: int = 2) -> str:
    if v is None:
        return "暂无"
    return f"{v:+.{digits}f}%"


def _fmt_yi(v: float | None) -> str:
    if v is None:
        return "暂无"
    if abs(v) < 0.00005:
        return "持平"
    return f"{v:+.2f}亿"


def _etf_label(name: Any, code: Any) -> str:
    """Display ETF with both name and code (required)."""
    n = str(name or "").strip() or "未命名ETF"
    c = str(code or "").strip()
    if c:
        return f"{n}（{c}）"
    return n


def _short_title(title: str, limit: int = 18) -> str:
    t = (title or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def sector_averages(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        sector = str(row.get("sector") or "").strip() or "未分类"
        ret1 = _num(row.get("ret1"))
        if ret1 is None:
            continue
        buckets[sector].append(ret1)
    out: list[dict[str, Any]] = []
    for sector, vals in buckets.items():
        out.append(
            {
                "sector": sector,
                "avgRet1": round(sum(vals) / len(vals), 4),
                "count": len(vals),
            }
        )
    out.sort(key=lambda x: x["avgRet1"], reverse=True)
    return out


def top_bottom_sectors(avgs: list[dict[str, Any]], n: int = 3) -> dict[str, list[dict[str, Any]]]:
    if not avgs:
        return {"gainers": [], "losers": []}
    gainers = avgs[:n]
    losers = list(reversed(avgs[-n:])) if len(avgs) > n else list(reversed(avgs))
    # Avoid overlap when few sectors
    g_names = {g["sector"] for g in gainers}
    losers = [x for x in losers if x["sector"] not in g_names][:n]
    return {"gainers": gainers, "losers": losers}


def volatility_leaders(rows: list[dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for row in rows:
        ret1 = _num(row.get("ret1"))
        if ret1 is None:
            continue
        scored.append(
            {
                "code": row.get("code"),
                "name": row.get("name"),
                "sector": row.get("sector"),
                "ret1": ret1,
                "absRet1": abs(ret1),
            }
        )
    scored.sort(key=lambda x: x["absRet1"], reverse=True)
    return scored[:n]


def citic_change(bundle: dict[str, Any]) -> dict[str, Any]:
    day = str(bundle.get("dataDate") or "")
    days: list[dict[str, Any]] = []
    for month in (bundle.get("citicMonthly") or {}).get("months") or []:
        days.extend(month.get("days") or [])
    days = [d for d in days if d.get("date")]
    days.sort(key=lambda d: str(d.get("date")))
    by_date = {str(d["date"]): d for d in days}
    cur = by_date.get(day)
    if not cur:
        # nearest on or before dataDate
        prior = [d for d in days if str(d["date"]) <= day]
        cur = prior[-1] if prior else None
    if not cur:
        return {"ok": False, "error": "citic_day_missing", "date": day}
    cur_date = str(cur["date"])
    earlier = [d for d in days if str(d["date"]) < cur_date]
    prev = earlier[-1] if earlier else None
    cur_total = _num(cur.get("citicTotal"))
    prev_total = _num(prev.get("citicTotal")) if prev else None
    delta = None if cur_total is None or prev_total is None else cur_total - prev_total
    return {
        "ok": True,
        "date": cur_date,
        "prevDate": str(prev["date"]) if prev else None,
        "citicTotal": cur_total,
        "prevTotal": prev_total,
        "delta": delta,
        "stance": cur.get("stance") or "—",
        "label": cur.get("label") or "—",
    }


def _event_key(ev: dict[str, Any]) -> str:
    return str(ev.get("sourceKey") or ev.get("id") or ev.get("title") or "").strip()


def collect_news(bundle: dict[str, Any], n: int = 5) -> dict[str, list[dict[str, Any]]]:
    pos: dict[str, dict[str, Any]] = {}
    neg: dict[str, dict[str, Any]] = {}
    for row in (bundle.get("impactEvents") or {}).get("rows") or []:
        for ev in row.get("positiveEvents") or []:
            if not isinstance(ev, dict):
                continue
            key = _event_key(ev)
            title = str(ev.get("title") or "").strip()
            if not key or not title:
                continue
            cur = pos.get(key)
            if cur is None or str(ev.get("date") or "") >= str(cur.get("date") or ""):
                pos[key] = {
                    "title": title,
                    "date": ev.get("date"),
                    "impact": ev.get("impact"),
                    "sourceKey": key,
                }
        for ev in row.get("negativeEvents") or []:
            if not isinstance(ev, dict):
                continue
            key = _event_key(ev)
            title = str(ev.get("title") or "").strip()
            if not key or not title:
                continue
            cur = neg.get(key)
            if cur is None or str(ev.get("date") or "") >= str(cur.get("date") or ""):
                neg[key] = {
                    "title": title,
                    "date": ev.get("date"),
                    "impact": ev.get("impact"),
                    "sourceKey": key,
                }

    def _sort_take(items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        arr = list(items.values())
        arr.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
        # secondary dedupe by title text
        seen_titles: set[str] = set()
        out: list[dict[str, Any]] = []
        for ev in arr:
            t = str(ev["title"])
            if t in seen_titles:
                continue
            seen_titles.add(t)
            out.append(ev)
            if len(out) >= n:
                break
        return out

    return {"positive": _sort_take(pos), "negative": _sort_take(neg)}


def technical_candidates(rows: list[dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
    cands = [r for r in rows if str(r.get("action") or "") == "技术候选"]
    cands.sort(key=lambda r: (_num(r.get("ret1")) is not None, _num(r.get("ret1")) or -1e18), reverse=True)
    out: list[dict[str, Any]] = []
    for r in cands[:n]:
        out.append(
            {
                "code": r.get("code"),
                "name": r.get("name"),
                "sector": r.get("sector"),
                "ret1": _num(r.get("ret1")),
                "ret5": _num(r.get("ret5")),
                "flow1": _num(r.get("flow1")),
                "flow5": _num(r.get("flow5")),
            }
        )
    return out


def build_chapters(bundle: dict[str, Any]) -> dict[str, Any]:
    day = str(bundle.get("dataDate") or "")
    rows = list(bundle.get("rows") or [])
    breadth = _num(bundle.get("breadthPct"))
    sectors = top_bottom_sectors(sector_averages(rows), 3)
    movers = volatility_leaders(rows, 5)
    citic = citic_change(bundle)
    news = collect_news(bundle, 5)
    cands = technical_candidates(rows, 5)

    # Narration lines (compact for 45–60s)
    # 「上涨占比」= 当日上涨标的占比，比「市场宽度」更好懂
    open_line = f"ETF六十八市场复盘。数据日期{day}。"
    if breadth is not None:
        open_line += f"上涨占比百分之{breadth:.1f}。"

    g_parts = [f"{x['sector']}{_fmt_pct(x['avgRet1'])}" for x in sectors["gainers"]]
    l_parts = [f"{x['sector']}{_fmt_pct(x['avgRet1'])}" for x in sectors["losers"]]
    sector_line = "板块均涨跌。"
    if g_parts:
        sector_line += "涨幅前三：" + "，".join(g_parts) + "。"
    if l_parts:
        sector_line += "跌幅前三：" + "，".join(l_parts) + "。"
    if not g_parts and not l_parts:
        sector_line += "暂无板块收益数据。"

    if movers:
        m_parts = [f"{m['name']}{_fmt_pct(m['ret1'])}" for m in movers]
        movers_line = "波动领先。" + "，".join(m_parts) + "。"
    else:
        movers_line = "波动领先。暂无涨跌数据。"

    if citic.get("ok"):
        delta = citic.get("delta")
        if delta is None:
            delta_txt = "较前日变化暂无"
        elif delta > 0:
            delta_txt = f"较前日增加{abs(int(delta))}手"
        elif delta < 0:
            delta_txt = f"较前日减少{abs(int(delta))}手"
        else:
            delta_txt = "较前日持平"
        citic_line = (
            f"中信多空。当日净额{int(citic['citicTotal']) if citic.get('citicTotal') is not None else '暂无'}手，"
            f"{citic.get('stance') or '—'}，{delta_txt}。"
        )
    else:
        citic_line = "中信多空。暂无当日持仓数据。"

    pos_titles = [_short_title(str(e["title"]), 16) for e in news["positive"]]
    neg_titles = [_short_title(str(e["title"]), 16) for e in news["negative"]]
    news_line = "实质消息。"
    if pos_titles:
        news_line += "利好：" + "；".join(pos_titles) + "。"
    else:
        news_line += "利好暂无。"
    if neg_titles:
        news_line += "利空：" + "；".join(neg_titles) + "。"
    else:
        news_line += "利空暂无。"

    if cands:
        c_parts = []
        for c in cands:
            c_parts.append(
                f"{c['name']}当日涨跌{_fmt_pct(c['ret1'])}，五日涨跌{_fmt_pct(c['ret5'])}，"
                f"当日资金{_fmt_yi(c['flow1'])}，五日资金{_fmt_yi(c['flow5'])}"
            )
        cand_line = "技术候选资金。" + "。".join(c_parts) + "。"
    else:
        cand_line = "技术候选资金。今日暂无技术候选。"

    close_line = "复盘结束。数据仅供梳理，不构成投资建议。"

    chapters = [
        {
            "id": "open",
            "title": "开场",
            "kicker": "01 · 日期",
            "budget_s": CHAPTER_BUDGETS["open"],
            "narration": open_line,
            "caption": f"复盘 · {day}",
            "bullets": [
                f"数据日期 {day}",
                f"上涨占比 {_fmt_pct(breadth, digits=1) if breadth is not None else '暂无'}",
            ],
        },
        {
            "id": "sectors",
            "title": "板块均涨跌",
            "kicker": "02 · 板块",
            "budget_s": CHAPTER_BUDGETS["sectors"],
            "narration": sector_line,
            "caption": "板块：涨前三 / 跌前三",
            "bullets": (
                [f"↑ {x['sector']} {_fmt_pct(x['avgRet1'])}" for x in sectors["gainers"]]
                + [f"↓ {x['sector']} {_fmt_pct(x['avgRet1'])}" for x in sectors["losers"]]
            ),
        },
        {
            "id": "movers",
            "title": "波动领先",
            "kicker": "03 · 波动",
            "budget_s": CHAPTER_BUDGETS["movers"],
            "narration": movers_line,
            "caption": "波动领先 · |涨跌幅| 前五",
            "bullets": [
                f"{_etf_label(m['name'], m['code'])} {_fmt_pct(m['ret1'])}" for m in movers
            ],
        },
        {
            "id": "citic",
            "title": "中信多空",
            "kicker": "04 · 多空",
            "budget_s": CHAPTER_BUDGETS["citic"],
            "narration": citic_line,
            "caption": "中信净持仓较前日",
            "bullets": [
                f"当日 {citic.get('citicTotal', '—')} 手 · {citic.get('stance', '—')}",
                (
                    f"较前日 {int(citic['delta']):+d} 手"
                    if citic.get("ok") and citic.get("delta") is not None
                    else "较前日 暂无"
                ),
            ],
        },
        {
            "id": "news",
            "title": "实质消息",
            "kicker": "05 · 消息",
            "budget_s": CHAPTER_BUDGETS["news"],
            "narration": news_line,
            "caption": "实质利好 / 利空 各五",
            "bullets": (
                [f"利好 · {_short_title(str(e['title']), 22)}" for e in news["positive"]]
                + [f"利空 · {_short_title(str(e['title']), 22)}" for e in news["negative"]]
            ),
        },
        {
            "id": "candidates",
            "title": "技术候选资金",
            "kicker": "06 · 候选",
            "budget_s": CHAPTER_BUDGETS["candidates"],
            "narration": cand_line,
            "caption": "技术候选 · 涨跌 / 资金",
            "bullets": [
                (
                    f"{_etf_label(c['name'], c['code'])} 日{_fmt_pct(c['ret1'])}/5日{_fmt_pct(c['ret5'])} · "
                    f"资日{_fmt_yi(c['flow1'])}/5日{_fmt_yi(c['flow5'])}"
                )
                for c in cands
            ]
            or ["今日暂无技术候选"],
        },
        {
            "id": "close",
            "title": "收束",
            "kicker": "07 · 结束",
            "budget_s": CHAPTER_BUDGETS["close"],
            "narration": close_line,
            "caption": "数据梳理 · 非投资建议",
            "bullets": ["上看状态", "中看页签", "下看明细"],
        },
    ]

    full_narration = "".join(ch["narration"] for ch in chapters)
    return {
        "ok": True,
        "dataDate": day,
        "targetDurationS": TARGET_DURATION_S,
        "breadthPct": breadth,
        "sectors": sectors,
        "movers": movers,
        "citic": citic,
        "news": news,
        "candidates": cands,
        "chapters": chapters,
        "fullNarration": full_narration,
    }


def build_review_script(bundle: dict[str, Any]) -> dict[str, Any]:
    if not bundle or not bundle.get("dataDate"):
        return {"ok": False, "error": "missing_bundle"}
    return build_chapters(bundle)
