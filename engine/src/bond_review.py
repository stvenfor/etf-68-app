"""今日债市收评：利率债（超长/中长/中短）+ 信用债，收蛋/丢蛋口径。

口径
----
- 1 蛋 = 1bp
- 债基净值上涨 = 收蛋；下跌 = 丢蛋
- 国债收益率下行 = 收蛋；上行 = 丢蛋（Δbp = (y_t - y_{t-1}) * 100）
- 纯债「今日估算」：按久期分档套用当日预判区间（示例口径）
- 曲线隐含：多关键点加权 Δbp×久期×仓位（超长 30Y/10Y；中长 10Y/5Y；中短 2Y/5Y）
- 净值实盘蛋：最新已披露单位净值日涨跌对照
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable, Mapping, Optional, Sequence
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_DIRECT = build_opener(ProxyHandler({}))

# Eastmoney RPTA_WEB_TREASURYYIELD field ids (akshare bond_zh_us_rate)
EM_FIELDS = {
    "y2": "EMM00588704",
    "y5": "EMM00166462",
    "y10": "EMM00166466",
    "y30": "EMM00166469",
}

RATE_ETF_CODE = "511090"  # 30年国债ETF鹏扬 — 超长辅证
CREDIT_ETF_CODE = "511190"  # 信用债ETF海富通

# 久期分档：与示例「今日估算」一致（可按日改方向/区间）
DAILY_OUTLOOK = {
    "ultra_long": {"side": "gain", "lo": 0, "hi": 10, "label": "收0-10个"},
    "mid_long": {"side": "loss", "lo": 0, "hi": 10, "label": "丢0-10个"},
    "mid_short": {"side": "flat", "lo": 0, "hi": 0, "label": "收0个左右"},
    "credit": {"side": "flat", "lo": 0, "hi": 0, "label": "收0个左右"},
}

FORECAST = {k: v["label"] for k, v in DAILY_OUTLOOK.items()}

# 示例图收录的纯债基金（仓位/久期截止公开报告；总仓位可>100%）
PURE_BOND_FUNDS: list[dict[str, Any]] = [
    {
        "code": "015909",
        "name": "方正富邦鸿远C",
        "ratePos": 116.5,
        "creditPos": 0.0,
        "duration": 20.3,
    },
    {
        "code": "020741",
        "name": "华泰保兴安悦C",
        "ratePos": 126.2,
        "creditPos": 0.0,
        "duration": 16.7,
    },
    {
        "code": "007859",
        "name": "平安5-10政金债A",
        "ratePos": 134.1,
        "creditPos": 0.0,
        "duration": 8.8,
    },
    {
        "code": "019596",
        "name": "富国7-10政金债联接E",
        "ratePos": 123.7,
        "creditPos": 0.0,
        "duration": 7.5,
    },
    {
        "code": "013594",
        "name": "南方7-10年国开债E",
        "ratePos": 125.8,
        "creditPos": 0.0,
        "duration": 6.8,
    },
    {
        "code": "011062",
        "name": "广发7-10年国开行E",
        "ratePos": 118.9,
        "creditPos": 0.0,
        "duration": 6.9,
    },
    {
        "code": "019451",
        "name": "中欧兴悦C",
        "ratePos": 21.3,
        "creditPos": 83.3,
        "duration": 1.5,
    },
    {
        "code": "002404",
        "name": "博时裕乾C",
        "ratePos": 56.1,
        "creditPos": 56.0,
        "duration": 2.5,
    },
    {
        "code": "161119",
        "name": "易方达中债新综指",
        "ratePos": 60.2,
        "creditPos": 32.1,
        "duration": 5.4,
    },
]

FetchFn = Callable[[str], str]


def _default_fetch(url: str, *, timeout: float = 20.0) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": "https://data.eastmoney.com/cjsj/zmgzsyl.html",
            "Accept": "application/json,text/plain,*/*",
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
    if x != x:
        return None
    return x


def eggs_from_yield_delta_bp(delta_bp: float | None) -> dict[str, Any]:
    """收益率变动(bp)：下行→收蛋，上行→丢蛋。整数蛋，非零至少 1。"""
    if delta_bp is None or not isinstance(delta_bp, (int, float)):
        return {
            "eggs": None,
            "side": "flat",
            "label": "—",
            "tone": "flat",
        }
    rounded = round(float(delta_bp))
    if rounded == 0:
        return {"eggs": 0, "side": "flat", "label": "平", "tone": "flat"}
    # 收益率下行 = 债牛 = 收蛋
    if rounded < 0:
        mag = abs(rounded)
        return {
            "eggs": mag,
            "side": "gain",
            "label": f"收 {mag} 蛋",
            "tone": "up",
        }
    return {
        "eggs": rounded,
        "side": "loss",
        "label": f"丢 {rounded} 蛋",
        "tone": "dn",
    }


def eggs_from_nav_ret_pct(ret_pct: float | None) -> dict[str, Any]:
    """债基净值涨跌% → 蛋：eggs ≈ ret1_pct × 100；涨=收蛋，跌=丢蛋。整数蛋，非零至少 1。"""
    if ret_pct is None or not isinstance(ret_pct, (int, float)):
        return {
            "eggs": None,
            "side": "flat",
            "label": "—",
            "tone": "flat",
        }
    raw = round(float(ret_pct) * 100.0)
    if raw == 0:
        return {"eggs": 0, "side": "flat", "label": "平", "tone": "flat"}
    if raw > 0:
        return {
            "eggs": raw,
            "side": "gain",
            "label": f"收 {raw} 蛋",
            "tone": "up",
        }
    mag = abs(raw)
    return {
        "eggs": mag,
        "side": "loss",
        "label": f"丢 {mag} 蛋",
        "tone": "dn",
    }


def classify_fund_bucket(duration: float, rate_pos: float, credit_pos: float) -> str:
    """按久期/仓位归入超长、中长、中短（信用偏重归中短口径）。"""
    if duration >= 12:
        return "ultra_long"
    if duration >= 6:
        return "mid_long"
    if credit_pos >= 50 and credit_pos >= rate_pos:
        return "credit"
    return "mid_short"


# 曲线隐含：多关键点加权，避免超长只盯 30Y 在曲线分化日严重失真
RATE_BP_BLEND: dict[str, tuple[tuple[str, float], ...]] = {
    "ultra_long": (("y30", 0.5), ("y10", 0.5)),
    "mid_long": (("y10", 0.6), ("y5", 0.4)),
    "mid_short": (("y2", 0.7), ("y5", 0.3)),
    "credit": (("y2", 0.7), ("y5", 0.3)),
}


def blended_rate_bp(
    bucket: str,
    yield_deltas: Mapping[str, Optional[float]],
) -> tuple[Optional[float], list[dict[str, Any]]]:
    """Return (weighted Δbp, blend detail). Missing legs are skipped and weights renormalized."""
    spec = RATE_BP_BLEND.get(bucket) or RATE_BP_BLEND["mid_short"]
    parts: list[dict[str, Any]] = []
    num = 0.0
    den = 0.0
    for key, weight in spec:
        bp = yield_deltas.get(key)
        if bp is None or not isinstance(bp, (int, float)):
            parts.append({"tenor": key, "weight": weight, "deltaBp": None, "used": False})
            continue
        parts.append({"tenor": key, "weight": weight, "deltaBp": float(bp), "used": True})
        num += float(bp) * float(weight)
        den += float(weight)
    if den <= 0:
        return None, parts
    return round(num / den, 4), parts


def outlook_estimate(bucket: str, outlook: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """生成示例风格的「今日估算」文案与色调。"""
    src = outlook or DAILY_OUTLOOK
    node = src.get(bucket) or src.get("mid_short") or {
        "side": "flat",
        "lo": 0,
        "hi": 0,
        "label": "收0个左右",
    }
    side = str(node.get("side") or "flat")
    tone = "up" if side == "gain" else "dn" if side == "loss" else "flat"
    return {
        "bucket": bucket,
        "side": side,
        "tone": tone,
        "lo": int(node.get("lo") or 0),
        "hi": int(node.get("hi") or 0),
        "label": str(node.get("label") or "—"),
    }


def implied_eggs_from_curve(
    *,
    duration: float,
    rate_pos: float,
    credit_pos: float,
    yield_deltas: Mapping[str, Optional[float]],
    credit_delta_bp: float | None = None,
) -> dict[str, Any]:
    """曲线隐含：蛋 ≈ -久期×加权Δbp×利率仓位% + (-久期×信用Δbp×信用仓位%)。

    超长：30Y/10Y 各 50%；中长：10Y 60% + 5Y 40%；中短/信用利率腿：2Y 70% + 5Y 30%。
    """
    bucket = classify_fund_bucket(duration, rate_pos, credit_pos)
    rate_bp, blend = blended_rate_bp(bucket, yield_deltas)

    eggs = 0.0
    used = False
    if rate_bp is not None:
        eggs += -float(duration) * float(rate_bp) * (float(rate_pos) / 100.0)
        used = True
    if credit_pos and credit_delta_bp is not None and isinstance(credit_delta_bp, (int, float)):
        eggs += -float(duration) * float(credit_delta_bp) * (float(credit_pos) / 100.0)
        used = True
    if not used:
        return {
            "eggs": None,
            "side": "flat",
            "label": "—",
            "tone": "flat",
            "raw": None,
            "rateBp": None,
            "blend": blend,
        }

    raw = round(eggs)
    base = {
        "raw": eggs,
        "rateBp": rate_bp,
        "blend": blend,
        "bucket": bucket,
    }
    if raw == 0:
        return {"eggs": 0, "side": "flat", "label": "平", "tone": "flat", **base}
    if raw > 0:
        return {
            "eggs": raw,
            "side": "gain",
            "label": f"收 {raw} 蛋",
            "tone": "up",
            **base,
        }
    mag = abs(raw)
    return {
        "eggs": mag,
        "side": "loss",
        "label": f"丢 {mag} 蛋",
        "tone": "dn",
        **base,
    }


def fetch_fund_nav_day_change(
    code: str,
    *,
    fetch: FetchFn | None = None,
) -> dict[str, Any]:
    """Latest published unit NAV day-change from Eastmoney pingzhong (soft-fail)."""
    fetch = fetch or _default_fetch
    code = str(code or "").zfill(6)
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    try:
        body = fetch(url)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "code": code, "error": str(exc)}

    m = re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\]);", body, re.S)
    if not m:
        return {"ok": False, "code": code, "error": "missing_netWorthTrend"}
    try:
        series = json.loads(m.group(1))
    except json.JSONDecodeError:
        return {"ok": False, "code": code, "error": "bad_netWorthTrend"}
    if not series:
        return {"ok": False, "code": code, "error": "empty_netWorthTrend"}
    last = series[-1] if isinstance(series[-1], dict) else {}
    nav = _num(last.get("y"))
    day_chg = _num(last.get("equityReturn"))
    nav_date = None
    ts = last.get("x")
    if ts is not None:
        try:
            nav_date = datetime.fromtimestamp(float(ts) / 1000.0, tz=SHANGHAI).date().isoformat()
        except (TypeError, ValueError, OSError, OverflowError):
            nav_date = None
    if nav is None and day_chg is None:
        return {"ok": False, "code": code, "error": "missing_nav"}
    return {
        "ok": True,
        "code": code,
        "nav": nav,
        "dayChangePct": day_chg,
        "navDate": nav_date,
    }


def fetch_pure_bond_nav_map(
    funds: Sequence[Mapping[str, Any]],
    *,
    fetch: FetchFn | None = None,
) -> dict[str, dict[str, Any]]:
    """Best-effort map code → nav day-change for pure-bond rows."""
    out: dict[str, dict[str, Any]] = {}
    for f in funds:
        code = str(f.get("code") or "").zfill(6)
        if not code.isdigit():
            continue
        info = fetch_fund_nav_day_change(code, fetch=fetch)
        if info.get("ok"):
            out[code] = info
    return out


def build_pure_bond_estimates(
    *,
    funds: Sequence[Mapping[str, Any]] | None = None,
    outlook: Mapping[str, Any] | None = None,
    yield_deltas: Mapping[str, Optional[float]] | None = None,
    credit_delta_bp: float | None = None,
    nav_by_code: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """收录基金 → 今日估算（分档预判）+ 曲线隐含 + 净值实盘蛋。"""
    rows: list[dict[str, Any]] = []
    nav_map = nav_by_code or {}
    for f in funds or PURE_BOND_FUNDS:
        duration = float(f.get("duration") or 0)
        rate_pos = float(f.get("ratePos") or 0)
        credit_pos = float(f.get("creditPos") or 0)
        code = str(f.get("code") or "").zfill(6)
        bucket = classify_fund_bucket(duration, rate_pos, credit_pos)
        estimate = outlook_estimate(bucket, outlook)
        implied = None
        if yield_deltas is not None:
            implied = implied_eggs_from_curve(
                duration=duration,
                rate_pos=rate_pos,
                credit_pos=credit_pos,
                yield_deltas=yield_deltas,
                credit_delta_bp=credit_delta_bp,
            )
        nav_info = nav_map.get(code) if isinstance(nav_map.get(code), Mapping) else None
        actual = None
        nav_ret = None
        nav_date = None
        nav_val = None
        if nav_info:
            nav_ret = _num(nav_info.get("dayChangePct"))
            nav_date = nav_info.get("navDate")
            nav_val = _num(nav_info.get("nav"))
            actual = eggs_from_nav_ret_pct(nav_ret)
        rows.append(
            {
                "code": code if code.isdigit() else str(f.get("code") or ""),
                "name": str(f.get("name") or ""),
                "ratePos": rate_pos,
                "creditPos": credit_pos,
                "duration": duration,
                "bucket": bucket,
                "estimate": estimate,
                "implied": implied,
                "actual": actual,
                "nav": nav_val,
                "navDate": nav_date,
                "navRetPct": nav_ret,
            }
        )
    return rows


def fetch_cn_treasury_yields(
    *,
    fetch: FetchFn | None = None,
    pages: int = 2,
) -> dict[str, Any]:
    """Fetch recent CN treasury yields from Eastmoney datacenter (soft-fail)."""
    fetch = fetch or _default_fetch
    rows: list[dict[str, Any]] = []
    try:
        for page in range(1, max(1, pages) + 1):
            params = {
                "type": "RPTA_WEB_TREASURYYIELD",
                "sty": "ALL",
                "st": "SOLAR_DATE",
                "sr": "-1",
                "token": "894050c76af8597a853f5b408b759f5d",
                "p": str(page),
                "ps": "50",
                "pageNo": str(page),
                "pageNum": str(page),
            }
            url = "https://datacenter.eastmoney.com/api/data/get?" + urlencode(params)
            raw = fetch(url)
            payload = json.loads(raw)
            chunk = ((payload.get("result") or {}).get("data")) or []
            if not isinstance(chunk, list) or not chunk:
                break
            rows.extend(chunk)
            total_pages = int(((payload.get("result") or {}).get("pages")) or 1)
            if page >= total_pages:
                break
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:160], "series": []}

    series: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        day = str(row.get("SOLAR_DATE") or "")[:10]
        if not day:
            continue
        series.append(
            {
                "date": day,
                "y2": _num(row.get(EM_FIELDS["y2"])),
                "y5": _num(row.get(EM_FIELDS["y5"])),
                "y10": _num(row.get(EM_FIELDS["y10"])),
                "y30": _num(row.get(EM_FIELDS["y30"])),
            }
        )
    # API returns newest-first; keep that for delta, also expose sorted
    series_sorted = sorted(series, key=lambda x: x["date"])
    return {
        "ok": len(series_sorted) >= 1,
        "series": series_sorted,
        "fetchedAt": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
    }


def _delta_bp(series: Sequence[Mapping[str, Any]], key: str, as_of: str | None) -> tuple[Optional[float], Optional[float], Optional[str]]:
    """Return (level%, delta_bp, date) for key on/before as_of."""
    usable = [r for r in series if r.get(key) is not None]
    if as_of:
        usable = [r for r in usable if str(r.get("date") or "") <= as_of]
    if not usable:
        return None, None, None
    cur = usable[-1]
    level = _num(cur.get(key))
    day = str(cur.get("date") or "") or None
    if len(usable) < 2 or level is None:
        return level, None, day
    prev = _num(usable[-2].get(key))
    if prev is None:
        return level, None, day
    return level, round((level - prev) * 100.0, 2), day


def _find_row(rows: Sequence[Mapping[str, Any]], code: str) -> Mapping[str, Any] | None:
    for r in rows:
        if str(r.get("code") or "") == code:
            return r
    return None


def _ret1_pct(row: Mapping[str, Any] | None) -> float | None:
    if not row:
        return None
    for key in ("ret1", "dayChangePct", "changePct"):
        v = _num(row.get(key))
        if v is not None:
            return v
    return None


def _bucket(
    *,
    key: str,
    label: str,
    tenorNote: str,
    primary_yield: dict[str, Any],
    secondary_yields: list[dict[str, Any]] | None = None,
    etf: dict[str, Any] | None = None,
    forecast: str,
) -> dict[str, Any]:
    move = eggs_from_yield_delta_bp(primary_yield.get("deltaBp"))
    return {
        "key": key,
        "label": label,
        "tenorNote": tenorNote,
        "forecast": forecast,
        "move": move,
        "primaryYield": primary_yield,
        "secondaryYields": secondary_yields or [],
        "etf": etf,
    }


def build_bond_review(
    *,
    as_of: str | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
    fetch: FetchFn | None = None,
    yields_payload: Mapping[str, Any] | None = None,
    outlook: Mapping[str, Any] | None = None,
    pure_bond_funds: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble 今日债市收评 payload for the dashboard."""
    fetched_at = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    rows = list(rows or [])
    live_yields = yields_payload is None
    if yields_payload is None:
        yields_payload = fetch_cn_treasury_yields(fetch=fetch)
    series = list(yields_payload.get("series") or []) if isinstance(yields_payload, Mapping) else []
    outlook = outlook or DAILY_OUTLOOK

    def _yield_node(field: str, name: str) -> dict[str, Any]:
        level, delta, day = _delta_bp(series, field, as_of)
        move = eggs_from_yield_delta_bp(delta)
        return {
            "id": field,
            "name": name,
            "level": level,
            "deltaBp": delta,
            "date": day,
            "move": move,
        }

    y2 = _yield_node("y2", "国债2Y")
    y5 = _yield_node("y5", "国债5Y")
    y10 = _yield_node("y10", "国债10Y")
    y30 = _yield_node("y30", "国债30Y")

    rate_etf_row = _find_row(rows, RATE_ETF_CODE)
    credit_etf_row = _find_row(rows, CREDIT_ETF_CODE)
    rate_etf = None
    if rate_etf_row:
        ret = _ret1_pct(rate_etf_row)
        rate_etf = {
            "code": RATE_ETF_CODE,
            "name": str(rate_etf_row.get("name") or "30年国债ETF"),
            "ret1": ret,
            "move": eggs_from_nav_ret_pct(ret),
        }
    credit_ret = _ret1_pct(credit_etf_row)
    credit_move = eggs_from_nav_ret_pct(credit_ret)
    # 信用隐含：净值变动蛋 ≈ -久期×Δbp；缺信用利差时用 ETF 蛋数近似为 Δbp
    credit_delta_bp = None
    if credit_move.get("eggs") is not None and credit_move.get("side") != "flat":
        signed = float(credit_move["eggs"])
        if credit_move.get("side") == "loss":
            signed = -signed
        # NAV 蛋≈收益 bp；信用债 Δbp ≈ -NAV蛋
        credit_delta_bp = -signed

    credit = {
        "key": "credit",
        "label": "信用债",
        "forecast": str((outlook.get("credit") or {}).get("label") or FORECAST["credit"]),
        "move": credit_move,
        "etf": {
            "code": CREDIT_ETF_CODE,
            "name": str((credit_etf_row or {}).get("name") or "信用债ETF"),
            "ret1": credit_ret,
            "move": credit_move,
        }
        if credit_etf_row or credit_ret is not None
        else None,
    }

    rate_buckets = [
        _bucket(
            key="ultra_long",
            label="超长",
            tenorNote="30Y",
            primary_yield=y30,
            secondary_yields=[],
            etf=rate_etf,
            forecast=str((outlook.get("ultra_long") or {}).get("label") or FORECAST["ultra_long"]),
        ),
        _bucket(
            key="mid_long",
            label="中长",
            tenorNote="5–10年",
            primary_yield=y10,
            secondary_yields=[y5],
            etf=None,
            forecast=str((outlook.get("mid_long") or {}).get("label") or FORECAST["mid_long"]),
        ),
        _bucket(
            key="mid_short",
            label="中短",
            tenorNote="0–5年",
            primary_yield=y2,
            secondary_yields=[y5],
            etf=None,
            forecast=str((outlook.get("mid_short") or {}).get("label") or FORECAST["mid_short"]),
        ),
    ]

    yield_deltas = {
        "y2": y2.get("deltaBp"),
        "y5": y5.get("deltaBp"),
        "y10": y10.get("deltaBp"),
        "y30": y30.get("deltaBp"),
    }
    fund_list = list(pure_bond_funds or PURE_BOND_FUNDS)
    # Offline unit tests inject yields without fetch — skip live NAV scrape.
    nav_by_code = (
        fetch_pure_bond_nav_map(fund_list, fetch=fetch)
        if live_yields or fetch is not None
        else {}
    )
    pure_bonds = build_pure_bond_estimates(
        funds=fund_list,
        outlook=outlook,
        yield_deltas=yield_deltas,
        credit_delta_bp=credit_delta_bp,
        nav_by_code=nav_by_code,
    )

    summary = _build_summary(rate_buckets, credit)
    ok = bool(yields_payload.get("ok")) or any(
        b.get("move", {}).get("eggs") is not None for b in rate_buckets
    ) or credit_move.get("eggs") is not None

    return {
        "ok": ok,
        "asOf": as_of,
        "fetchedAt": yields_payload.get("fetchedAt") or fetched_at,
        "unit": "1蛋=1bp",
        "rule": "债基净值上涨=收蛋，下跌=丢蛋；国债收益率下行=收蛋，上行=丢蛋；曲线隐含按多关键点加权Δbp×久期×仓位；纯债附净值实盘蛋对照",
        "yields": {"y2": y2, "y5": y5, "y10": y10, "y30": y30},
        "rate": {"buckets": rate_buckets},
        "credit": credit,
        "pureBonds": pure_bonds,
        "outlook": {k: outlook_estimate(k, outlook) for k in ("ultra_long", "mid_long", "mid_short", "credit")},
        "summary": summary,
        "error": yields_payload.get("error") if not yields_payload.get("ok") else None,
    }


def _build_summary(rate_buckets: list[dict[str, Any]], credit: dict[str, Any]) -> str:
    parts: list[str] = []
    for b in rate_buckets:
        move = b.get("move") or {}
        label = move.get("label") or "—"
        parts.append(f"{b['label']}{label}")
    c_move = (credit.get("move") or {}).get("label") or "—"
    parts.append(f"信用{c_move}")
    # Tone headline
    gains = sum(1 for b in rate_buckets if (b.get("move") or {}).get("side") == "gain")
    losses = sum(1 for b in rate_buckets if (b.get("move") or {}).get("side") == "loss")
    if gains >= 2 and losses == 0:
        head = "利率债偏强"
    elif losses >= 2 and gains == 0:
        head = "利率债偏弱"
    else:
        head = "利率债分化"
    credit_side = (credit.get("move") or {}).get("side")
    if credit_side == "gain":
        head += "，信用跟涨"
    elif credit_side == "loss":
        head += "，信用回落"
    return head + "：" + " · ".join(parts)
