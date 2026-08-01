"""Build a compact daily market-review script from a UiBundle."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any


TARGET_DURATION_S = 70.0

# Soft hints only — VO is never hard-trimmed to fit.
CHAPTER_BUDGETS = {
    "open": 5.0,
    "sectors": 14.0,
    "citic": 14.0,
    "news": 28.0,  # full headline titles — do not squeeze
    "candidates": 18.0,
    "close": 4.0,
}

_CFFEX_CANDIDATES = (
    os.environ.get("ETF68_CFFEX_DIR", "").strip(),
    str(Path.home() / "Desktop/github/my_tool_project/modules/cffex-daily/work/output"),
    str(Path(__file__).resolve().parents[2] / "cffex-daily" / "work" / "output"),
)


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
    """Kept for callers/tests; no longer used in review chapters."""
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


def _stance_from_lots(v: float | None) -> str:
    if v is None:
        return "—"
    if v > 0:
        return "净加多"
    if v < 0:
        return "净加空"
    return "平"


def _daily_stance_phrase(name: str, v: Any, stance: Any = None) -> str:
    """口播/展示：名称 +（净加空xx手 | 净加多xx手 | 持平），三者互斥。"""
    n = _num(v)
    if n is None:
        return f"{name}暂无"
    lots = int(round(n))
    st = str(stance or "").strip() or _stance_from_lots(float(lots))
    if lots == 0 or st == "平":
        return f"{name}持平"
    abs_n = abs(lots)
    if st == "净加多":
        return f"{name}净加多{abs_n}手"
    if st == "净加空":
        return f"{name}净加空{abs_n}手"
    # fallback by sign
    if lots > 0:
        return f"{name}净加多{abs_n}手"
    return f"{name}净加空{abs_n}手"


def _month_net_phrase(month_net: Any) -> str:
    """本月累计：本月总体净空xx手 | 净多xx手 | 持平。"""
    n = _num(month_net)
    if n is None:
        return "本月总体暂无"
    lots = int(round(n))
    if lots > 0:
        return f"本月总体净多{lots}手"
    if lots < 0:
        return f"本月总体净空{abs(lots)}手"
    return "本月总体持平"


def _load_cffex_day(day: str) -> dict[str, Any] | None:
    """Optional enrichment: citic_total / net_buy_total from cffex-daily export."""
    stem = day.replace("-", "")
    if len(stem) != 8:
        return None
    for raw in _CFFEX_CANDIDATES:
        if not raw:
            continue
        path = Path(raw) / f"citic-net-positions-{stem}.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        return data
    return None


def citic_change(bundle: dict[str, Any]) -> dict[str, Any]:
    day = str(bundle.get("dataDate") or "")
    months = (bundle.get("citicMonthly") or {}).get("months") or []
    days: list[dict[str, Any]] = []
    for month in months:
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

    other_total = _num(cur.get("otherTotal"))
    grand_total = _num(cur.get("grandTotal")) or _num(cur.get("netBuyTotal"))

    # Delivery-day table (grand/other) when date matches
    for row in (bundle.get("deliveryCiticIndex") or {}).get("rows") or []:
        if str(row.get("delivery") or "") != cur_date:
            continue
        if cur_total is None:
            cur_total = _num(row.get("citicTotal"))
        if other_total is None:
            other_total = _num(row.get("otherTotal"))
        if grand_total is None:
            grand_total = _num(row.get("grandTotal"))
        break

    # Daily CFFEX export: net_buy_total = 排名会员当日净增仓合计
    cffex = _load_cffex_day(cur_date)
    if cffex:
        if cur_total is None:
            cur_total = _num(cffex.get("citic_total"))
        if grand_total is None:
            grand_total = _num(cffex.get("net_buy_total"))
        if other_total is None and grand_total is not None and cur_total is not None:
            other_total = grand_total - cur_total
        elif grand_total is not None and cur_total is not None:
            other_total = grand_total - cur_total

    if other_total is None and grand_total is not None and cur_total is not None:
        other_total = grand_total - cur_total

    ym = cur_date[:7]
    month_row: dict[str, Any] | None = None
    for month in months:
        if str(month.get("label") or "") == ym:
            month_row = month
            break
        if any(str(d.get("date") or "").startswith(ym) for d in (month.get("days") or [])):
            month_row = month
            break

    month_net = _num((month_row or {}).get("monthNet"))
    if month_net is None and month_row:
        vals = [_num(d.get("citicTotal")) for d in (month_row.get("days") or [])]
        vals = [v for v in vals if v is not None]
        if vals:
            month_net = float(sum(vals))

    stance = cur.get("stance") or _stance_from_lots(cur_total)
    other_stance = _stance_from_lots(other_total)
    grand_stance = _stance_from_lots(grand_total)
    raw_month_stance = _stance_from_lots(month_net)
    if raw_month_stance == "净加空":
        month_stance_label = "净空"
    elif raw_month_stance == "净加多":
        month_stance_label = "净多"
    elif raw_month_stance == "平":
        month_stance_label = "持平"
    else:
        month_stance_label = "—"

    return {
        "ok": True,
        "date": cur_date,
        "prevDate": str(prev["date"]) if prev else None,
        "citicTotal": cur_total,
        "otherTotal": other_total,
        "grandTotal": grand_total,
        "prevTotal": prev_total,
        "delta": delta,
        "monthNet": month_net,
        "monthLabel": (month_row or {}).get("label") or ym,
        "stance": stance,
        "otherStance": other_stance,
        "grandStance": grand_stance,
        "monthStance": month_stance_label,
        "label": cur.get("label") or "—",
    }


def _event_key(ev: dict[str, Any]) -> str:
    return str(ev.get("sourceKey") or ev.get("id") or ev.get("title") or "").strip()


def collect_news(
    bundle: dict[str, Any],
    n: int = 5,
    *,
    lookback_days: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """Pick newest substantive bullish/bearish headlines (prefer recent dates)."""
    pos: dict[str, dict[str, Any]] = {}
    neg: dict[str, dict[str, Any]] = {}
    as_of = str(bundle.get("dataDate") or "").strip()

    def _ingest(bucket: dict[str, dict[str, Any]], ev: dict[str, Any]) -> None:
        key = _event_key(ev)
        title = str(ev.get("title") or "").strip()
        if not key or not title:
            return
        cur = bucket.get(key)
        if cur is None or str(ev.get("date") or "") >= str(cur.get("date") or ""):
            bucket[key] = {
                "title": title,
                "date": ev.get("date"),
                "impact": ev.get("impact"),
                "sourceKey": key,
            }

    for row in (bundle.get("impactEvents") or {}).get("rows") or []:
        if not isinstance(row, dict):
            continue
        for ev in row.get("positiveEvents") or []:
            if isinstance(ev, dict):
                _ingest(pos, ev)
        for ev in row.get("negativeEvents") or []:
            if isinstance(ev, dict):
                _ingest(neg, ev)

    # Prefer events on/after (as_of - lookback). Floor date as YYYY-MM-DD string compare.
    min_date = ""
    if as_of and lookback_days > 0:
        try:
            from datetime import date, timedelta

            d0 = date.fromisoformat(as_of[:10])
            min_date = (d0 - timedelta(days=lookback_days)).isoformat()
        except ValueError:
            min_date = ""

    def _sort_take(items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        arr = list(items.values())
        # live_ keys and newer dates first
        arr.sort(
            key=lambda x: (
                str(x.get("date") or ""),
                1 if str(x.get("sourceKey") or "").startswith("live_") else 0,
            ),
            reverse=True,
        )
        seen_titles: set[str] = set()
        fresh: list[dict[str, Any]] = []
        older: list[dict[str, Any]] = []
        for ev in arr:
            t = str(ev["title"])
            if t in seen_titles:
                continue
            seen_titles.add(t)
            d = str(ev.get("date") or "")
            if min_date and d and d < min_date:
                older.append(ev)
            else:
                fresh.append(ev)
        out = fresh + older
        return out[:n]

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


def build_chapters(
    bundle: dict[str, Any],
    *,
    market_board: dict[str, Any] | None = None,
    fetch_market: bool = True,
) -> dict[str, Any]:
    day = str(bundle.get("dataDate") or "")
    rows = list(bundle.get("rows") or [])
    breadth = _num(bundle.get("breadthPct"))
    sectors = top_bottom_sectors(sector_averages(rows), 3)
    citic = citic_change(bundle)
    news = collect_news(bundle, 5)
    cands = technical_candidates(rows, 5)

    # Visual-only open board (turnover + indices); never added to narration.
    if market_board is not None:
        board = market_board
    elif fetch_market:
        try:
            from src.market_snapshot import build_market_board

            board = build_market_board(as_of=day or None)
        except Exception as exc:  # noqa: BLE001 — soft-fail
            board = {"ok": False, "error": str(exc)[:160], "turnover": {}, "indices": []}
    else:
        board = {"ok": False, "skipped": True, "turnover": {}, "indices": []}

    # Narration lines (compact for 45–60s)
    # 「市场温度」= 站上均线 / 均线上行 / 5日上涨 / 资金流入 的综合热度
    open_line = f"ETF六十八市场复盘。数据日期{day}。"
    if breadth is not None:
        open_line += f"市场温度百分之{breadth:.1f}。"

    g_parts = [f"{x['sector']}{_fmt_pct(x['avgRet1'])}" for x in sectors["gainers"]]
    l_parts = [f"{x['sector']}{_fmt_pct(x['avgRet1'])}" for x in sectors["losers"]]
    sector_line = "板块均涨跌。"
    if g_parts:
        sector_line += "涨幅前三：" + "，".join(g_parts) + "。"
    if l_parts:
        sector_line += "跌幅前三：" + "，".join(l_parts) + "。"
    if not g_parts and not l_parts:
        sector_line += "暂无板块收益数据。"

    def _lots_txt(v: Any) -> str:
        n = _num(v)
        if n is None:
            return "暂无"
        return f"{int(n)}手"

    if citic.get("ok"):
        citic_line = (
            "持仓量变动。"
            + _daily_stance_phrase("中信", citic.get("citicTotal"), citic.get("stance"))
            + "；"
            + _daily_stance_phrase("其它机构", citic.get("otherTotal"), citic.get("otherStance"))
            + "；"
            + _daily_stance_phrase("总体", citic.get("grandTotal"), citic.get("grandStance"))
            + "；"
            + _month_net_phrase(citic.get("monthNet"))
            + "。"
        )
    else:
        citic_line = "持仓量变动。暂无当日持仓数据。"

    # 口播用完整标题，避免省略导致遗漏
    pos_titles = [str(e["title"]).strip() for e in news["positive"] if str(e.get("title") or "").strip()]
    neg_titles = [str(e["title"]).strip() for e in news["negative"] if str(e.get("title") or "").strip()]
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
                f"{c['name']}当日{_fmt_pct(c['ret1'])}，五日{_fmt_pct(c['ret5'])}"
            )
        cand_line = "技术候选。" + "。".join(c_parts) + "。"
    else:
        cand_line = "技术候选。今日暂无技术候选。"

    close_line = "复盘结束。数据来源于网络，仅供参考。"

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
                f"市场温度 {_fmt_pct(breadth, digits=1) if breadth is not None else '暂无'}",
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
            "id": "citic",
            "title": "持仓量变动",
            "kicker": "03 · 持仓",
            "budget_s": CHAPTER_BUDGETS["citic"],
            "narration": citic_line,
            "caption": "中信 / 其它机构 / 总体 / 本月",
            "bullets": [
                _daily_stance_phrase("中信多空", citic.get("citicTotal"), citic.get("stance")),
                _daily_stance_phrase("其它机构", citic.get("otherTotal"), citic.get("otherStance")),
                _daily_stance_phrase("总体", citic.get("grandTotal"), citic.get("grandStance")),
                _month_net_phrase(citic.get("monthNet")),
            ],
        },
        {
            "id": "news",
            "title": "实质消息",
            "kicker": "04 · 消息",
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
            "title": "技术候选",
            "kicker": "05 · 候选",
            "budget_s": CHAPTER_BUDGETS["candidates"],
            "narration": cand_line,
            "caption": "技术面筛选候选 · 涨跌百分比",
            "bullets": [
                f"{_etf_label(c['name'], c['code'])} 日{_fmt_pct(c['ret1'])}/5日{_fmt_pct(c['ret5'])}"
                for c in cands
            ]
            or ["今日暂无技术候选"],
        },
        {
            "id": "close",
            "title": "收束",
            "kicker": "06 · 结束",
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
        "marketBoard": board,
        "sectors": sectors,
        "citic": citic,
        "news": news,
        "candidates": cands,
        "chapters": chapters,
        "fullNarration": full_narration,
    }


def build_review_script(
    bundle: dict[str, Any],
    *,
    market_board: dict[str, Any] | None = None,
    fetch_market: bool = True,
) -> dict[str, Any]:
    if not bundle or not bundle.get("dataDate"):
        return {"ok": False, "error": "missing_bundle"}
    return build_chapters(bundle, market_board=market_board, fetch_market=fetch_market)
