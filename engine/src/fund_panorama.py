"""Open-end fund NAV panorama (mirror of ETF 数据全景 for 场外基金).

Series from Eastmoney pingzhong ``Data_netWorthTrend``; UI maps ``close`` ← unit NAV.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable, Mapping, Optional, Sequence
from urllib.request import ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_DIRECT = build_opener(ProxyHandler({}))

FetchFn = Callable[[str], str]


def _default_fetch(url: str, *, timeout: float = 30.0) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": "https://fund.eastmoney.com/",
            "Accept": "*/*",
        },
    )
    with _DIRECT.open(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read().decode("utf-8", "replace")


def _num(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    return x


def _nav_point(row: Mapping[str, Any]) -> tuple[Optional[float], Optional[float], Optional[str]]:
    nav = _num(row.get("y"))
    day_chg = _num(row.get("equityReturn"))
    nav_date = None
    ts = row.get("x")
    if ts is not None:
        try:
            nav_date = datetime.fromtimestamp(float(ts) / 1000.0, tz=SHANGHAI).date().isoformat()
        except (TypeError, ValueError, OSError, OverflowError):
            nav_date = None
    return nav, day_chg, nav_date


def parse_net_worth_trend(body: str) -> list[dict[str, Any]]:
    m = re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\]);", body, re.S)
    if not m:
        raise ValueError("missing_netWorthTrend")
    raw = json.loads(m.group(1))
    if not isinstance(raw, list) or not raw:
        raise ValueError("empty_netWorthTrend")
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        nav, day_chg, nav_date = _nav_point(row)
        if nav is None or not nav_date:
            continue
        # ``close`` alias so desktop can reuse ETF panorama close-interval helpers.
        out.append(
            {
                "date": nav_date,
                "close": round(nav, 6),
                "nav": round(nav, 6),
                "dayChangePct": day_chg,
            }
        )
    if not out:
        raise ValueError("empty_parsed_nav_series")
    return out


def _return_from_end(series: Sequence[Mapping[str, Any]], trading_days: int) -> Optional[float]:
    if len(series) < 2 or trading_days <= 0:
        return None
    end = series[-1]
    end_nav = _num(end.get("nav") if end.get("nav") is not None else end.get("close"))
    if end_nav is None or end_nav == 0:
        return None
    idx = max(0, len(series) - 1 - trading_days)
    start_nav = _num(series[idx].get("nav") if series[idx].get("nav") is not None else series[idx].get("close"))
    if start_nav is None or start_nav == 0:
        return None
    return round((end_nav / start_nav - 1.0) * 100.0, 4)


def _max_drawdown_pct(series: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    peak = None
    peak_date = None
    best_dd = 0.0
    best: dict[str, Any] = {
        "maxDrawdownPct": 0.0,
        "peakDate": None,
        "troughDate": None,
        "peakNav": None,
        "troughNav": None,
    }
    for p in series:
        nav = _num(p.get("nav") if p.get("nav") is not None else p.get("close"))
        if nav is None or nav <= 0:
            continue
        date = str(p.get("date") or "")
        if peak is None or nav > peak:
            peak = nav
            peak_date = date
        dd = (peak - nav) / peak * 100.0 if peak else 0.0
        if dd > best_dd:
            best_dd = dd
            best = {
                "maxDrawdownPct": round(dd, 4),
                "peakDate": peak_date,
                "troughDate": date,
                "peakNav": peak,
                "troughNav": nav,
            }
    return best


def build_fund_panorama_summary(series: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    last = series[-1] if series else {}
    dd = _max_drawdown_pct(series)
    return {
        "points": len(series),
        "startDate": series[0].get("date") if series else None,
        "endDate": last.get("date"),
        "lastNav": _num(last.get("nav") if last.get("nav") is not None else last.get("close")),
        "lastDayChangePct": _num(last.get("dayChangePct")),
        "ret5dPct": _return_from_end(series, 5),
        "ret20dPct": _return_from_end(series, 20),
        "ret60dPct": _return_from_end(series, 60),
        "ret250dPct": _return_from_end(series, 250),
        **dd,
    }


def build_fund_panorama(
    code: str,
    *,
    fetch: FetchFn | None = None,
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch / parse NAV history for one open-end fund."""
    fetch = fetch or _default_fetch
    code = str(code or "").zfill(6)
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    fetched_at = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    try:
        body = fetch(url)
        series = parse_net_worth_trend(body)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "code": code,
            "error": str(exc)[:200],
            "fetchedAt": fetched_at,
            "series": [],
            "summary": None,
            "meta": dict(meta or {}),
        }

    name = None
    nm = re.search(r'var\s+fS_name\s*=\s*"([^"]*)"', body)
    if nm:
        name = nm.group(1)
    meta_out = dict(meta or {})
    if name and not meta_out.get("name"):
        meta_out["name"] = name

    # Prefer last ~5y for UI (keep full if shorter).
    max_points = 1300
    if len(series) > max_points:
        series = series[-max_points:]

    return {
        "ok": True,
        "code": code,
        "fetchedAt": fetched_at,
        "series": series,
        "summary": build_fund_panorama_summary(series),
        "meta": meta_out,
        "error": None,
    }
