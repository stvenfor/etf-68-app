"""Select and value an open-end mutual-fund representative pool.

Quota (by latest approximate AUM): equity / bond / hybrid / QDII = 20 each.
Data: Sina fund-center scale list + Eastmoney published NAV + Sina estimate quote.
Manual hybrid pins / excludes override pure AUM ranking when rebuilding.
Bond sleeve pins dashboard pure-bond codes first, then fills by AUM to quota.
Equity keeps tech theme pins first, then fills by AUM to quota.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

from .bond_review import PURE_BOND_FUNDS
from .fund_advice import FRAMEWORK as ADVICE_FRAMEWORK
from .fund_advice import apply_fund_advice

SHANGHAI = ZoneInfo("Asia/Shanghai")

# Local HTTP(S)_PROXY often points at a dead client; fund hosts need direct egress.
_DIRECT = build_opener(ProxyHandler({}))

# Dashboard 纯债基金 → 代表性公募债券袖（钉选，重建时优先保留）
PURE_BOND_PIN_CODES: tuple[str, ...] = tuple(
    str(f.get("code") or "").zfill(6) for f in PURE_BOND_FUNDS if f.get("code")
)
PURE_BOND_PIN_NAMES: dict[str, str] = {
    str(f.get("code") or "").zfill(6): str(f.get("name") or "")
    for f in PURE_BOND_FUNDS
    if f.get("code")
}

QUOTA: dict[str, int] = {
    "equity": 20,
    "bond": 20,
    "hybrid": 20,
    "qdii": 20,
}

# Always keep these codes on rebuild. Missing from Sina list → stub, NAV later.
# Equity: tech themes — 半导体 / 芯片 / CPO(通信设备代理) / 机器人（场外无纯 CPO 开放式）。
# Bond: 数据看板「纯债基金」清单（久期/仓位样本）。
# Hybrid: 综合性医疗主题用主动「医疗保健」基金，不用 ETF/联接。
FORCE_INCLUDE: dict[str, tuple[str, ...]] = {
    "equity": ("014855", "014193", "020899", "020256"),
    "bond": PURE_BOND_PIN_CODES,
    "hybrid": ("001638", "001123", "001423", "001407", "009690", "110023"),
}

# Optional display names for pinned stubs missing from Sina scale list.
FORCE_INCLUDE_NAMES: dict[str, str] = dict(PURE_BOND_PIN_NAMES)

# Drop from any category on rebuild (user removals from hybrid).
# 003095/003096 = 中欧医疗健康 A/C（改盯易方达医疗保健行业混合 110023）。
FORCE_EXCLUDE: frozenset[str] = frozenset(
    {"163406", "007119", "003095", "003096", "002910", "008989", "005827", "009881"}
)

CATEGORY_LABELS: dict[str, str] = {
    "equity": "股票型",
    "bond": "债券型",
    "hybrid": "混合型",
    "qdii": "QDII",
}

# Sina NetValueReturnOpen type2
SINA_TYPE2: dict[str, str] = {
    "equity": "2",
    "bond": "3",
    "hybrid": "1",
    "qdii": "6",
}

SINA_URL = (
    "http://vip.stock.finance.sina.com.cn/fund_center/data/jsonp.php/"
    "IO.XSRV2.CallbackList['J2cW8KXheoWKdSHc']/"
    "NetValueReturn_Service.NetValueReturnOpen"
)

ETF_CODE_RE = re.compile(r"^(15|51|56|58)\d{4}$")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


FetchFn = Callable[[str], str]


def _default_fetch(url: str, *, timeout: float = 30.0) -> str:
    referer = "https://vip.stock.finance.sina.com.cn/"
    if "sinajs.cn" in url or "finance.sina.com.cn" in url:
        referer = "https://finance.sina.com.cn/"
    elif "eastmoney.com" in url:
        referer = "https://fund.eastmoney.com/"
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": referer,
            "Accept": "*/*",
        },
    )
    with _DIRECT.open(req, timeout=timeout) as resp:  # noqa: S310 — public market data
        raw = resp.read()
    if "sinajs.cn" in url:
        return raw.decode("gb18030", "replace")
    return raw.decode("utf-8", "replace")


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


def is_excluded_name_code(name: str, code: str, category: str) -> bool:
    """Reject ETF / ETF-feeder / money-market / cross-type noise from Sina buckets."""
    n = name or ""
    u = n.upper()
    c = (code or "").zfill(6)
    if "ETF" in u or "LOF" in u or "交易型" in n:
        return True
    # ETF 联接（场外联接基金）；名称含「联接」一律排除
    if "联接" in n:
        return True
    if "货币" in n or "现金宝" in n or "日日盈" in n:
        return True
    if ETF_CODE_RE.match(c):
        return True
    if category == "equity":
        if "QDII" in u or "债" in n:
            return True
    elif category == "bond":
        if "QDII" in u:
            return True
        if "股票" in n and "债" not in n:
            return True
    elif category == "hybrid":
        if "QDII" in u:
            return True
    elif category == "qdii":
        if "QDII" not in u:
            return True
    return False


def share_class_key(name: str) -> str:
    """Collapse A/C/D share classes of the same fund for de-duplication."""
    n = re.sub(r"\s+", "", name or "")
    n = re.sub(r"\((QDII)[^)]*\)", r"(\1)", n, flags=re.I)
    n = re.sub(r"\([AaCcDdEeFfRr]\)$", "", n)
    n = re.sub(r"[AaCcDdEeFf]类?$", "", n)
    n = re.sub(r"(人民币|美元|港币)$", "", n)
    return n


def approx_aum_yi(shares: Any, nav: Any) -> Optional[float]:
    """Sina zjzfe is share count; AUM(亿元) ≈ shares * NAV / 1e8."""
    s = _num(shares)
    p = _num(nav)
    if s is None or p is None or s <= 0 or p <= 0:
        return None
    return s * p / 1e8


def parse_sina_jsonp(body: str) -> list[dict[str, Any]]:
    start = body.find("({")
    end = body.rfind("})")
    if start < 0 or end < 0:
        raise ValueError("malformed_sina_jsonp")
    payload = json.loads(body[start + 1 : end + 1])
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("malformed_sina_data")
    return [row for row in data if isinstance(row, dict)]


def fetch_sina_category(
    category: str,
    *,
    fetch: FetchFn = _default_fetch,
    page_size: int = 2000,
) -> list[dict[str, Any]]:
    type2 = SINA_TYPE2[category]
    params = urlencode(
        {
            "page": "1",
            "num": str(page_size),
            "sort": "zjzfe",
            "asc": "0",
            "ccode": "",
            "type2": type2,
            "type3": "",
        }
    )
    body = fetch(f"{SINA_URL}?{params}")
    return parse_sina_jsonp(body)


def select_category_top(
    raw_rows: list[dict[str, Any]],
    category: str,
    limit: int,
    *,
    pin_codes: Optional[tuple[str, ...] | list[str]] = None,
    exclude_codes: Optional[frozenset[str] | set[str]] = None,
) -> list[dict[str, Any]]:
    pins = [str(c).zfill(6) for c in (pin_codes if pin_codes is not None else FORCE_INCLUDE.get(category, ()))]
    excluded = {
        str(c).zfill(6)
        for c in (exclude_codes if exclude_codes is not None else FORCE_EXCLUDE)
    }
    scored: list[dict[str, Any]] = []
    by_code: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        code = str(row.get("symbol") or "").zfill(6)
        name = str(row.get("sname") or "").strip()
        if not code.isdigit() or not name:
            continue
        if code in excluded:
            continue
        # Pinned codes bypass name-based filters (user-forced representatives).
        if code not in pins and is_excluded_name_code(name, code, category):
            continue
        aum = approx_aum_yi(row.get("zjzfe"), row.get("dwjz"))
        nav = _num(row.get("dwjz"))
        if aum is None or nav is None:
            continue
        nav_date = str(row.get("jzrq") or "")[:10]
        item = {
            "code": code,
            "name": name,
            "category": category,
            "categoryLabel": CATEGORY_LABELS[category],
            "aumYi": round(aum, 4),
            "nav": nav,
            "navDate": nav_date or None,
            "dayChangePct": None,
        }
        scored.append(item)
        by_code[code] = item
    scored.sort(key=lambda x: float(x["aumYi"] or 0), reverse=True)

    out: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    seen_keys: set[str] = set()

    def _append(row: dict[str, Any]) -> bool:
        code = str(row["code"]).zfill(6)
        if code in seen_codes or code in excluded:
            return False
        key = share_class_key(str(row.get("name") or ""))
        if key and key in seen_keys:
            return False
        item = {**row, "rankInCategory": len(out) + 1}
        out.append(item)
        seen_codes.add(code)
        if key:
            seen_keys.add(key)
        return True

    for code in pins:
        if code in excluded:
            continue
        if code in by_code:
            _append(by_code[code])
        else:
            _append(
                {
                    "code": code,
                    "name": FORCE_INCLUDE_NAMES.get(code, ""),
                    "category": category,
                    "categoryLabel": CATEGORY_LABELS[category],
                    "aumYi": None,
                    "nav": None,
                    "navDate": None,
                    "dayChangePct": None,
                }
            )
        if len(out) >= limit:
            return out

    for row in scored:
        _append(row)
        if len(out) >= limit:
            break
    return out


def _nav_point(row: Mapping[str, Any] | dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[str]]:
    nav = _num(row.get("y"))
    day_chg = _num(row.get("equityReturn"))
    nav_date = None
    ts = row.get("x")
    if ts is not None:
        try:
            nav_date = (
                datetime.fromtimestamp(float(ts) / 1000.0, tz=SHANGHAI).date().isoformat()
            )
        except (TypeError, ValueError, OSError, OverflowError):
            nav_date = None
    return nav, day_chg, nav_date


def parse_pingzhong_nav(body: str) -> dict[str, Any]:
    """Latest published unit NAV + day change from Eastmoney pingzhong JS.

    Also exposes the previous series point so callers can roll back when the
    latest NAV date is still the unfinished trading day.
    """
    m = re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\]);", body, re.S)
    if not m:
        raise ValueError("missing_netWorthTrend")
    series = json.loads(m.group(1))
    if not series:
        raise ValueError("empty_netWorthTrend")
    nav, day_chg, nav_date = _nav_point(series[-1])
    if nav is None:
        raise ValueError("missing_nav")
    name = None
    nm = re.search(r'var\s+fS_name\s*=\s*"([^"]*)"', body)
    if nm:
        name = nm.group(1)
    out: dict[str, Any] = {"nav": nav, "dayChangePct": day_chg, "navDate": nav_date, "name": name}
    if len(series) >= 2:
        p_nav, p_chg, p_date = _nav_point(series[-2])
        if p_nav is not None:
            out["prevNav"] = p_nav
            out["prevDayChangePct"] = p_chg
            out["prevNavDate"] = p_date
    # Optional: latest report-period asset mix (股票/债券/现金占净比)
    try:
        from .fund_portfolio_profile import parse_pingzhong_asset_mix

        mix = parse_pingzhong_asset_mix(body)
        if mix:
            out["assetMix"] = mix
    except Exception:  # noqa: BLE001
        pass
    return out


def parse_sina_fund_quote(body: str, code: str) -> dict[str, Any]:
    """Parse Sina ``hq_str_fu_{code}`` intraday fund valuation.

    ``f_`` quotes are *not* estimates — field[3] there is previous NAV.
    ``fu_`` fields (observed):
      name, time(HH:MM:SS), estimateNav, prevNav, prevNav, flag,
      estimateChangePct, date, ...
    """
    key = f"hq_str_fu_{code}"
    m = re.search(rf'{re.escape(key)}="([^"]*)"', body)
    if not m:
        raise ValueError("missing_sina_fund_estimate")
    raw = (m.group(1) or "").strip()
    if not raw:
        raise ValueError("empty_sina_fund_estimate")
    fields = raw.split(",")
    if len(fields) < 7:
        raise ValueError("malformed_sina_fund_estimate")
    estimate = _num(fields[2])
    prev_nav = _num(fields[3])
    estimate_chg_pct = _num(fields[6])
    est_date = (fields[7] or "").strip()[:10] or None if len(fields) > 7 else None
    hhmmss = (fields[1] or "").strip() or None
    estimate_chg = None
    if estimate is not None and prev_nav is not None:
        estimate_chg = round(estimate - prev_nav, 4)
        if estimate_chg_pct is None and prev_nav != 0:
            estimate_chg_pct = round((estimate - prev_nav) / prev_nav * 100.0, 4)
    estimate_time = None
    if est_date and hhmmss:
        estimate_time = f"{est_date} {hhmmss}"
    elif hhmmss:
        estimate_time = hhmmss
    return {
        "estimateNav": estimate,
        "prevNav": prev_nav,
        "estimateChange": estimate_chg,
        "estimateChangePct": estimate_chg_pct,
        "estimateDate": est_date,
        "estimateTime": estimate_time,
        "name": (fields[0] or "").strip() or None,
    }


# Sina fu_ clock often freezes after close (15:00–16:04). Product rule:
# show valuation at most as of 14:50:00, and freeze estimate *values* the same way
# when the quote/local clock is past 14:50 (prefer prior same-day ≤14:50 snapshot).
# Before 12:00: show previous session 14:50 (not today's early/open quote).
ESTIMATE_DISPLAY_CUTOFF_HM = (14, 50)
ESTIMATE_MORNING_CUTOFF_HM = (12, 0)


def _parse_estimate_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    # Drop trailing " · …" annotations if present.
    text = text.split("·", 1)[0].strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19] if len(text) >= 19 else text, fmt).replace(tzinfo=SHANGHAI)
        except ValueError:
            continue
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}(?::\d{2})?)", str(raw))
    if m:
        return _parse_estimate_dt(f"{m.group(1)} {m.group(2)}")
    tm = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if tm:
        now = datetime.now(SHANGHAI)
        sec = int(tm.group(3) or 0)
        return now.replace(hour=int(tm.group(1)), minute=int(tm.group(2)), second=sec, microsecond=0)
    return None


def _hm_tuple(dt: datetime) -> tuple[int, int]:
    return (dt.hour, dt.minute)


def _past_estimate_cutoff(dt: datetime) -> bool:
    return _hm_tuple(dt) > ESTIMATE_DISPLAY_CUTOFF_HM


def format_estimate_time_only(raw: str | None, *, fallback: datetime | None = None) -> str:
    """Return ``YYYY-MM-DD HH:MM:SS`` only; clock capped at 14:50:00."""
    dt = _parse_estimate_dt(raw) or fallback or datetime.now(SHANGHAI)
    cut_h, cut_m = ESTIMATE_DISPLAY_CUTOFF_HM
    if _past_estimate_cutoff(dt):
        return f"{dt.date().isoformat()} {cut_h:02d}:{cut_m:02d}:00"
    return f"{dt.date().isoformat()} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"


def cap_estimate_clock_for_display(raw: str | None) -> str | None:
    """Cap timestamp at 14:50:00; always prefer full ``YYYY-MM-DD HH:MM:SS``."""
    if not raw:
        return raw
    return format_estimate_time_only(raw)


def _should_freeze_at_1450(quote_raw: str | None, *, now: datetime) -> bool:
    quote_dt = _parse_estimate_dt(quote_raw)
    if quote_dt is not None and _past_estimate_cutoff(quote_dt):
        return True
    if quote_dt is not None and quote_dt.date() == now.date() and _past_estimate_cutoff(now):
        return True
    if quote_dt is None and _past_estimate_cutoff(now):
        return True
    return False


def _prev_usable_1450_snapshot(prev: dict[str, Any] | None, *, day: str) -> dict[str, Any] | None:
    """Reuse prior same-day estimate when freezing at 14:50.

    Prefer a snapshot whose quote clock is ≤14:50; also accept an already
    frozen ``… 14:50:00`` row from a later pull.
    """
    if not prev or prev.get("estimateNav") is None:
        return None
    raw = prev.get("estimateQuoteTime") or prev.get("estimateTime")
    dt = _parse_estimate_dt(str(raw) if raw else None)
    if dt is None or dt.date().isoformat() != day:
        return None
    display = str(prev.get("estimateTime") or "")
    if _past_estimate_cutoff(dt) and "14:50:00" not in display:
        return None
    return prev


def _date_key(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def _before_morning_cutoff(now: datetime) -> bool:
    """True before 12:00 — show previous session 14:50 valuation."""
    return _hm_tuple(now) < ESTIMATE_MORNING_CUTOFF_HM


def compute_estimate_vs_nav_error(
    *,
    nav: Any,
    estimate_nav: Any,
) -> dict[str, Any]:
    """估值误差 = 估值相对实际公布净值的差距（始终按当前展示的估值与净值计算）。"""
    est = _num(estimate_nav)
    px = _num(nav)
    if est is None or px is None or px == 0:
        return {
            "estimateErrorPct": None,
            "estimateErrorAbs": None,
            "estimateErrorStatus": "pending",
        }
    err_abs = round(est - px, 6)
    err_pct = round((est - px) / px * 100.0, 4)
    return {
        "estimateErrorPct": err_pct,
        "estimateErrorAbs": err_abs,
        "estimateErrorStatus": "ready",
    }


def compute_nav_vs_1450_error(
    *,
    nav: Any,
    nav_date: Any = None,
    estimate_1450_nav: Any = None,
    estimate_1450_date: Any = None,
    estimate_nav: Any = None,
) -> dict[str, Any]:
    """Backward-compatible wrapper: prefer explicit estimate_nav, else 14:50 snapshot."""
    est = estimate_nav if estimate_nav is not None else estimate_1450_nav
    return compute_estimate_vs_nav_error(nav=nav, estimate_nav=est)


def _prev_session_1450_snapshot(
    prev: dict[str, Any] | None,
    *,
    today: str,
) -> dict[str, Any] | None:
    """Previous trading session's frozen 14:50 estimate (date strictly before today)."""
    if not prev:
        return None
    d1450 = _date_key(prev.get("estimate1450Date"))
    nav1450 = _num(prev.get("estimate1450Nav"))
    if d1450 and d1450 < today and nav1450 is not None:
        return {
            "estimateNav": nav1450,
            "estimateChange": prev.get("estimateChange"),
            "estimateChangePct": prev.get("estimateChangePct"),
            "estimateTime": f"{d1450} 14:50:00",
            "estimate1450Date": d1450,
            "estimate1450Nav": nav1450,
            "estimate1450Frozen": True,
        }
    # Fallback: last displayed estimate from a prior calendar day
    raw = prev.get("estimateTime") or prev.get("estimateQuoteTime")
    dt = _parse_estimate_dt(str(raw) if raw else None)
    est = _num(prev.get("estimateNav"))
    if dt is None or est is None:
        return None
    day = dt.date().isoformat()
    if day >= today:
        return None
    return {
        "estimateNav": est,
        "estimateChange": prev.get("estimateChange"),
        "estimateChangePct": prev.get("estimateChangePct"),
        "estimateTime": f"{day} 14:50:00",
        "estimate1450Date": _date_key(prev.get("estimate1450Date")) or day,
        "estimate1450Nav": nav1450 if nav1450 is not None else est,
        "estimate1450Frozen": True,
    }


def _carry_or_set_1450(
    item: dict[str, Any],
    *,
    day: str,
    estimate_nav: Any,
    prev: dict[str, Any] | None,
    freeze: bool,
) -> None:
    """Persist same-day 14:50 valuation for later comparison with published NAV."""
    prev_date = _date_key((prev or {}).get("estimate1450Date"))
    prev_nav = _num((prev or {}).get("estimate1450Nav"))
    # Prefer an already frozen same-day snapshot from a prior refresh.
    if prev_date == day and prev_nav is not None:
        item["estimate1450Date"] = day
        item["estimate1450Nav"] = prev_nav
        if (prev or {}).get("estimate1450Frozen") or freeze:
            item["estimate1450Frozen"] = True
        return
    est = _num(estimate_nav)
    if est is None:
        return
    item["estimate1450Date"] = day
    item["estimate1450Nav"] = est
    if freeze:
        item["estimate1450Frozen"] = True


def _date_le(a: Optional[str], b: Optional[str]) -> bool:
    """True if a and b look like YYYY-MM-DD and a < b."""
    if not a or not b or len(a) < 10 or len(b) < 10:
        return False
    try:
        return a[:10] < b[:10]
    except Exception:  # noqa: BLE001
        return False


def fetch_eastmoney_nav(code: str, *, fetch: FetchFn = _default_fetch) -> dict[str, Any]:
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    body = fetch(url)
    return parse_pingzhong_nav(body)


def fetch_sina_estimates(
    codes: list[str],
    *,
    fetch: FetchFn = _default_fetch,
) -> dict[str, dict[str, Any]]:
    """Batch-fetch Sina ``fu_`` fund valuations; returns code -> estimate fields."""
    out: dict[str, dict[str, Any]] = {}
    if not codes:
        return out
    chunk_size = 40
    for i in range(0, len(codes), chunk_size):
        chunk = codes[i : i + chunk_size]
        url = "https://hq.sinajs.cn/list=" + ",".join(f"fu_{c}" for c in chunk)
        try:
            body = fetch(url)
        except Exception:  # noqa: BLE001
            continue
        for code in chunk:
            try:
                out[code] = parse_sina_fund_quote(body, code)
            except Exception:  # noqa: BLE001
                continue
    return out


def _apply_published_as_estimate(
    item: dict[str, Any],
    *,
    now: datetime | None = None,
    morning: bool = False,
) -> None:
    """When no usable intraday valuation, mirror published NAV day-change.

    「估值时间」只保留完整日期时间（超过 14:50 记为 14:50:00），无刷新后缀。
    上午无上一日 14:50 缓存时，用净值日 14:50 对齐展示。
    """
    if item.get("nav") is None:
        return
    item["estimateNav"] = item.get("nav")
    item["estimateChangePct"] = item.get("dayChangePct")
    item["estimateChange"] = None
    now = now or datetime.now(SHANGHAI)
    nav_day = _date_key(item.get("navDate"))
    if morning and nav_day:
        item["estimateTime"] = f"{nav_day} 14:50:00"
        item["estimate1450Date"] = nav_day
        item["estimate1450Nav"] = item.get("nav")
        item["estimate1450Frozen"] = True
    else:
        item["estimateTime"] = format_estimate_time_only(None, fallback=now)
    item["refreshedAt"] = now.strftime("%Y-%m-%d %H:%M:%S")


def enrich_nav(
    rows: list[dict[str, Any]],
    *,
    fetch: FetchFn = _default_fetch,
    previous_by_code: Optional[dict[str, dict[str, Any]]] = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    codes = [str(r.get("code") or "").zfill(6) for r in rows if r.get("code")]
    estimates = fetch_sina_estimates(codes, fetch=fetch)
    prev_map = previous_by_code or {}
    now = now or datetime.now(SHANGHAI)
    today = now.date().isoformat()
    morning = _before_morning_cutoff(now)
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        code = str(item.get("code") or "").zfill(6)
        nav_info: dict[str, Any] = {}
        try:
            nav_info = fetch_eastmoney_nav(code, fetch=fetch)
            item["nav"] = nav_info["nav"]
            item["dayChangePct"] = nav_info["dayChangePct"]
            if nav_info.get("navDate"):
                item["navDate"] = nav_info["navDate"]
            if nav_info.get("name") and not item.get("name"):
                item["name"] = nav_info["name"]
            if nav_info.get("assetMix"):
                item["assetMix"] = nav_info["assetMix"]
            item.pop("error", None)
        except Exception as exc:  # noqa: BLE001 — keep row, mark error
            item["error"] = str(exc)

        # 交易日净值未更新/未落定（最新点仍标今日）→ 展示上一交易日最终净值
        if (
            morning
            and _date_key(item.get("navDate")) == today
            and nav_info.get("prevNav") is not None
            and nav_info.get("prevNavDate")
        ):
            item["nav"] = nav_info["prevNav"]
            item["dayChangePct"] = nav_info.get("prevDayChangePct")
            item["navDate"] = nav_info["prevNavDate"]

        est = estimates.get(code)
        prev_row = prev_map.get(code)
        pulled_at = now.strftime("%Y-%m-%d %H:%M:%S")
        used_morning_prev = False

        # 12:00 前：展示上一交易日 14:50 估值（不用当日早盘报价）
        if morning:
            snap = _prev_session_1450_snapshot(prev_row, today=today)
            if snap is not None:
                item["estimateNav"] = snap["estimateNav"]
                item["estimateChange"] = snap.get("estimateChange")
                item["estimateChangePct"] = snap.get("estimateChangePct")
                item["estimateTime"] = snap["estimateTime"]
                item["estimateQuoteTime"] = snap["estimateTime"]
                item["estimate1450Date"] = snap.get("estimate1450Date")
                item["estimate1450Nav"] = snap.get("estimate1450Nav")
                item["estimate1450Frozen"] = True
                item["refreshedAt"] = pulled_at
                used_morning_prev = True
            elif est and est.get("estimateNav") is not None:
                est_day = _date_key(est.get("estimateDate"))
                # Sina 仍挂着上一交易日估值时可用；当日早盘报价丢弃
                if est_day and est_day < today:
                    quote_time = est.get("estimateTime") or est.get("estimateDate")
                    item["estimateQuoteTime"] = quote_time
                    item["estimateNav"] = est["estimateNav"]
                    if est.get("estimateChange") is not None:
                        item["estimateChange"] = est["estimateChange"]
                    if est.get("estimateChangePct") is not None:
                        item["estimateChangePct"] = est["estimateChangePct"]
                    item["estimateTime"] = f"{est_day} 14:50:00"
                    item["estimate1450Date"] = est_day
                    item["estimate1450Nav"] = est["estimateNav"]
                    item["estimate1450Frozen"] = True
                    item["refreshedAt"] = pulled_at
                    used_morning_prev = True

        if not used_morning_prev:
            # Stale estimate (common for QDII / missing fu_): fall back to published.
            stale = bool(est and _date_le(est.get("estimateDate"), item.get("navDate")))
            if est and est.get("estimateNav") is not None and not stale and not (
                morning and _date_key(est.get("estimateDate")) == today
            ):
                quote_time = est.get("estimateTime") or est.get("estimateDate")
                item["estimateQuoteTime"] = quote_time
                freeze = _should_freeze_at_1450(str(quote_time) if quote_time else None, now=now)
                quote_dt = _parse_estimate_dt(str(quote_time) if quote_time else None) or now
                day = quote_dt.date().isoformat()
                snap = _prev_usable_1450_snapshot(prev_row, day=day) if freeze else None
                if snap is not None:
                    item["estimateNav"] = snap.get("estimateNav")
                    item["estimateChange"] = snap.get("estimateChange")
                    item["estimateChangePct"] = snap.get("estimateChangePct")
                else:
                    item["estimateNav"] = est["estimateNav"]
                    if est.get("estimateChange") is not None:
                        item["estimateChange"] = est["estimateChange"]
                    if est.get("estimateChangePct") is not None:
                        item["estimateChangePct"] = est["estimateChangePct"]
                item["estimateTime"] = format_estimate_time_only(
                    str(quote_time) if quote_time else None,
                    fallback=now,
                )
                item["refreshedAt"] = pulled_at
                _carry_or_set_1450(
                    item,
                    day=day,
                    estimate_nav=item.get("estimateNav"),
                    prev=prev_row,
                    freeze=freeze,
                )
            else:
                _apply_published_as_estimate(item, now=now, morning=morning)
                if prev_row and _num(prev_row.get("estimate1450Nav")) is not None:
                    item["estimate1450Date"] = prev_row.get("estimate1450Date")
                    item["estimate1450Nav"] = prev_row.get("estimate1450Nav")
                    if prev_row.get("estimate1450Frozen"):
                        item["estimate1450Frozen"] = True

        # 估值误差始终 = 当前展示估值 vs 当前展示公布净值
        item.update(
            compute_estimate_vs_nav_error(
                nav=item.get("nav"),
                estimate_nav=item.get("estimateNav"),
            )
        )
        out.append(item)
    return out


def rebuild_universe(*, fetch: FetchFn = _default_fetch, page_size: int = 2000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category, limit in QUOTA.items():
        raw = fetch_sina_category(category, fetch=fetch, page_size=page_size)
        rows.extend(select_category_top(raw, category, limit))
    return rows


def load_cached_universe(path_data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = path_data.get("rows") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "").zfill(6)
        if not code.isdigit():
            continue
        category = str(row.get("category") or "")
        if category not in QUOTA:
            continue
        item: dict[str, Any] = {
            "code": code,
            "name": str(row.get("name") or ""),
            "category": category,
            "categoryLabel": row.get("categoryLabel") or CATEGORY_LABELS.get(category, category),
            "aumYi": _num(row.get("aumYi")),
            "nav": _num(row.get("nav")),
            "navDate": row.get("navDate"),
            "dayChangePct": _num(row.get("dayChangePct")),
            "estimateNav": _num(row.get("estimateNav")),
            "estimateChange": _num(row.get("estimateChange")),
            "estimateChangePct": _num(row.get("estimateChangePct")),
            "estimateTime": row.get("estimateTime"),
            "estimateQuoteTime": row.get("estimateQuoteTime"),
            "rankInCategory": row.get("rankInCategory"),
        }
        # Preserve portfolio profile so refresh without rebuild keeps industry mix.
        for key in (
            "assetMix",
            "industries",
            "industryAsOf",
            "riskLevel",
            "riskLabel",
            "riskNote",
            "profileError",
        ):
            if row.get(key) is not None:
                item[key] = row[key]
        out.append(item)
    return out


def build_funds_top30(
    *,
    rebuild: bool = False,
    previous: Optional[dict[str, Any]] = None,
    fetch: FetchFn = _default_fetch,
    page_size: int = 2000,
) -> dict[str, Any]:
    from .fund_portfolio_profile import enrich_portfolio_profile

    if rebuild or not previous or not (previous.get("rows")):
        universe = rebuild_universe(fetch=fetch, page_size=page_size)
    else:
        universe = load_cached_universe(previous)

    prev_by: dict[str, dict[str, Any]] = {}
    if previous and isinstance(previous.get("rows"), list):
        for r in previous["rows"]:
            if isinstance(r, dict) and r.get("code"):
                prev_by[str(r["code"]).zfill(6)] = r

    valued = enrich_nav(universe, fetch=fetch, previous_by_code=prev_by)
    valued = enrich_portfolio_profile(
        valued,
        fetch=fetch,
        previous_by_code=prev_by,
        workers=6,
        industry_top_n=8,
    )
    valued = apply_fund_advice(valued)
    counts = {k: 0 for k in QUOTA}
    advice_counts: dict[str, int] = {}
    for row in valued:
        cat = str(row.get("category") or "")
        if cat in counts:
            counts[cat] += 1
        label = str(row.get("advice") or "观望")
        advice_counts[label] = advice_counts.get(label, 0) + 1

    return {
        "ok": True,
        "asOf": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "quota": dict(QUOTA),
        "counts": counts,
        "adviceCounts": advice_counts,
        "adviceFramework": ADVICE_FRAMEWORK,
        "source": {
            "universe": "sina_fund_center",
            "nav": "eastmoney_pingzhong",
            "estimate": "sina_hq_fu",
            "industry": "eastmoney_hypz",
            "assetMix": "eastmoney_pingzhong_asset",
        },
        "rows": valued,
    }


def write_funds_top30(path: Any, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
