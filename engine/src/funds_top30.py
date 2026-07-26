"""Select and value a ~30 open-end mutual-fund representative pool.

Quota (by latest approximate AUM): equity 4 / bond 4 / hybrid 16 / QDII 4.
Data: Sina fund-center scale list + Eastmoney published NAV + Sina estimate quote.
Manual hybrid pins / excludes override pure AUM ranking when rebuilding.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

QUOTA: dict[str, int] = {
    "equity": 4,
    "bond": 4,
    "hybrid": 16,
    "qdii": 4,
}

# Always keep these codes on rebuild. Missing from Sina list → stub, NAV later.
# Equity: tech themes — 半导体 / 芯片 / CPO(通信设备代理) / 机器人（场外无纯 CPO 开放式）。
FORCE_INCLUDE: dict[str, tuple[str, ...]] = {
    "equity": ("014855", "014193", "020899", "020256"),
    "hybrid": ("001638", "001123", "001423", "001407", "009690"),
}

# Drop from any category on rebuild (user removals from hybrid).
FORCE_EXCLUDE: frozenset[str] = frozenset(
    {"163406", "007119", "003095", "002910", "008989", "005827"}
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
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — public market data
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
                    "name": "",
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


def parse_pingzhong_nav(body: str) -> dict[str, Any]:
    """Latest published unit NAV + day change from Eastmoney pingzhong JS."""
    m = re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\]);", body, re.S)
    if not m:
        raise ValueError("missing_netWorthTrend")
    series = json.loads(m.group(1))
    if not series:
        raise ValueError("empty_netWorthTrend")
    last = series[-1]
    nav = _num(last.get("y"))
    if nav is None:
        raise ValueError("missing_nav")
    day_chg = _num(last.get("equityReturn"))
    nav_date = None
    ts = last.get("x")
    if ts is not None:
        try:
            nav_date = (
                datetime.fromtimestamp(float(ts) / 1000.0, tz=SHANGHAI).date().isoformat()
            )
        except (TypeError, ValueError, OSError, OverflowError):
            nav_date = None
    name = None
    nm = re.search(r'var\s+fS_name\s*=\s*"([^"]*)"', body)
    if nm:
        name = nm.group(1)
    return {"nav": nav, "dayChangePct": day_chg, "navDate": nav_date, "name": name}


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


def _apply_published_as_estimate(item: dict[str, Any]) -> None:
    """When no usable intraday valuation, mirror published NAV day-change."""
    if item.get("nav") is None:
        return
    item["estimateNav"] = item.get("nav")
    item["estimateChangePct"] = item.get("dayChangePct")
    item["estimateChange"] = None
    if item.get("navDate"):
        item["estimateTime"] = f"{item['navDate']} 已公布"
    else:
        item["estimateTime"] = "已公布·无盘中估值"


def enrich_nav(
    rows: list[dict[str, Any]],
    *,
    fetch: FetchFn = _default_fetch,
) -> list[dict[str, Any]]:
    codes = [str(r.get("code") or "").zfill(6) for r in rows if r.get("code")]
    estimates = fetch_sina_estimates(codes, fetch=fetch)
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        code = str(item.get("code") or "").zfill(6)
        try:
            nav_info = fetch_eastmoney_nav(code, fetch=fetch)
            item["nav"] = nav_info["nav"]
            item["dayChangePct"] = nav_info["dayChangePct"]
            if nav_info.get("navDate"):
                item["navDate"] = nav_info["navDate"]
            if nav_info.get("name") and not item.get("name"):
                item["name"] = nav_info["name"]
            item.pop("error", None)
        except Exception as exc:  # noqa: BLE001 — keep row, mark error
            item["error"] = str(exc)

        est = estimates.get(code)
        # Stale estimate (common for QDII / missing fu_): fall back to published.
        stale = bool(est and _date_le(est.get("estimateDate"), item.get("navDate")))
        if est and est.get("estimateNav") is not None and not stale:
            item["estimateNav"] = est["estimateNav"]
            if est.get("estimateChange") is not None:
                item["estimateChange"] = est["estimateChange"]
            if est.get("estimateChangePct") is not None:
                item["estimateChangePct"] = est["estimateChangePct"]
            if est.get("estimateTime"):
                item["estimateTime"] = est["estimateTime"]
            elif est.get("estimateDate"):
                item["estimateTime"] = est["estimateDate"]
        else:
            _apply_published_as_estimate(item)
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
        out.append(
            {
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
                "rankInCategory": row.get("rankInCategory"),
            }
        )
    return out


def build_funds_top30(
    *,
    rebuild: bool = False,
    previous: Optional[dict[str, Any]] = None,
    fetch: FetchFn = _default_fetch,
    page_size: int = 2000,
) -> dict[str, Any]:
    if rebuild or not previous or not (previous.get("rows")):
        universe = rebuild_universe(fetch=fetch, page_size=page_size)
    else:
        universe = load_cached_universe(previous)

    valued = enrich_nav(universe, fetch=fetch)
    counts = {k: 0 for k in QUOTA}
    for row in valued:
        cat = str(row.get("category") or "")
        if cat in counts:
            counts[cat] += 1

    return {
        "ok": True,
        "asOf": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "quota": dict(QUOTA),
        "counts": counts,
        "source": {
            "universe": "sina_fund_center",
            "nav": "eastmoney_pingzhong",
            "estimate": "sina_hq_fu",
        },
        "rows": valued,
    }


def write_funds_top30(path: Any, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
