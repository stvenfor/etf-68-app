"""Fetch China official PMI (制造 / 非制造) from Eastmoney datacenter.

Optional curated overlay supplies 综合 PMI and sub-indices not in the base feed.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.request import ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_DIRECT = build_opener(ProxyHandler({}))

EM_PMI_URL = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
    "?reportName=RPT_ECONOMY_PMI&columns=ALL&pageNumber=1&pageSize={n}"
    "&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB"
)

THRESHOLD = 50.0
FetchFn = Callable[[str], str]

_ENGINE_DATA = Path(__file__).resolve().parents[1] / "data"
_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_TIME_RE = re.compile(r"(\d{4})年(\d{1,2})月")


def _default_fetch(url: str, *, timeout: float = 25.0) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": "https://data.eastmoney.com/cjsj/pmi.html",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with _DIRECT.open(req, timeout=timeout) as resp:  # noqa: S310 — public macro data
        return resp.read().decode("utf-8", "replace")


def _num(v: Any) -> Optional[float]:
    if v is None or v == "-" or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def _month_key_from_row(row: dict[str, Any]) -> Optional[str]:
    rd = str(row.get("REPORT_DATE") or "")
    if len(rd) >= 7 and rd[4] == "-":
        return rd[:7]
    m = _TIME_RE.search(str(row.get("TIME") or ""))
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    return None


def _metric(value: Optional[float], prev: Optional[float], *, label: str) -> dict[str, Any]:
    mom = None
    if value is not None and prev is not None:
        mom = round(value - prev, 2)
    return {
        "label": label,
        "value": value,
        "prev": prev,
        "momPp": mom,
        "below50": (value is not None and value < THRESHOLD),
        "above50": (value is not None and value >= THRESHOLD),
    }


def parse_em_pmi_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Eastmoney RPT_ECONOMY_PMI rows (newest first)."""
    rows = ((payload.get("result") or {}).get("data")) or []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        month = _month_key_from_row(row)
        make = _num(row.get("MAKE_INDEX"))
        nmake = _num(row.get("NMAKE_INDEX"))
        if not month or make is None:
            continue
        out.append(
            {
                "month": month,
                "timeLabel": str(row.get("TIME") or ""),
                "manufacturing": make,
                "nonManufacturing": nmake,
                "raw": {
                    "MAKE_SAME": _num(row.get("MAKE_SAME")),
                    "NMAKE_SAME": _num(row.get("NMAKE_SAME")),
                },
            }
        )
    return out


def load_overlay(month: str, *, overlay_dir: Path | None = None) -> dict[str, Any]:
    """Load optional curated overlay: engine/data/macro-pmi-overlay-YYYY-MM.json."""
    root = overlay_dir or _ENGINE_DATA
    path = root / f"macro-pmi-overlay-{month}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def build_pmi_snapshot(
    series: list[dict[str, Any]],
    *,
    month: str | None = None,
    overlay: dict[str, Any] | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Build one-month PMI snapshot with MoM vs previous row in series."""
    if not series:
        return {"ok": False, "error": "empty_series", "month": month}

    by_month = {str(r["month"]): r for r in series if r.get("month")}
    target = month or str(series[0]["month"])
    if not _MONTH_RE.match(target):
        return {"ok": False, "error": f"bad_month:{target}", "month": target}
    cur = by_month.get(target)
    if not cur:
        return {"ok": False, "error": f"month_not_found:{target}", "month": target}

    # previous calendar month in series order (series newest-first)
    months_sorted = sorted(by_month.keys())
    prev_month = None
    if target in months_sorted:
        idx = months_sorted.index(target)
        if idx > 0:
            prev_month = months_sorted[idx - 1]
    prev = by_month.get(prev_month) if prev_month else None

    ov = overlay if isinstance(overlay, dict) else {}
    m_val = _num(cur.get("manufacturing"))
    m_prev = _num((prev or {}).get("manufacturing"))
    n_val = _num(cur.get("nonManufacturing"))
    n_prev = _num((prev or {}).get("nonManufacturing"))

    manufacturing = _metric(m_val, m_prev, label="制造业PMI")
    non_mfg = _metric(n_val, n_prev, label="非制造业PMI")

    c_val = _num(ov.get("composite"))
    c_prev = _num(ov.get("compositePrev"))
    composite = _metric(c_val, c_prev, label="综合PMI产出") if c_val is not None else None

    details: list[dict[str, Any]] = []
    for d in ov.get("details") or []:
        if not isinstance(d, dict):
            continue
        v = _num(d.get("value"))
        p = _num(d.get("prev"))
        label = str(d.get("label") or d.get("id") or "").strip()
        if not label or v is None:
            continue
        item = _metric(v, p, label=label)
        item["id"] = str(d.get("id") or "")
        item["note"] = str(d.get("note") or "")
        details.append(item)

    both_below = bool(
        manufacturing.get("below50") and non_mfg.get("value") is not None and non_mfg.get("below50")
    )
    sync_contract = both_below
    if ov.get("syncContract") is not None:
        sync_contract = bool(ov.get("syncContract"))

    return {
        "ok": True,
        "month": target,
        "timeLabel": cur.get("timeLabel") or f"{target} PMI",
        "asOf": as_of or datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "source": "eastmoney_rpt_economy_pmi",
        "sourceUrl": "https://data.eastmoney.com/cjsj/pmi.html",
        "threshold": THRESHOLD,
        "manufacturing": manufacturing,
        "nonManufacturing": non_mfg,
        "composite": composite,
        "details": details,
        "flags": {
            "manufacturingBelow50": bool(manufacturing.get("below50")),
            "nonManufacturingBelow50": bool(non_mfg.get("below50")),
            "syncContract": sync_contract,
            "hasOverlay": bool(ov),
        },
        "overlayNotes": list(ov.get("notes") or []),
        "forwardWindowMonth": ov.get("forwardWindowMonth"),
        "interpretation": list(ov.get("interpretation") or []),
        "signals": list(ov.get("signals") or []),
    }


def fetch_pmi_series(*, pagesize: int = 24, fetch: FetchFn | None = None) -> list[dict[str, Any]]:
    fn = fetch or _default_fetch
    text = fn(EM_PMI_URL.format(n=max(2, pagesize)))
    payload = json.loads(text)
    return parse_em_pmi_payload(payload)


def fetch_macro_pmi(
    month: str | None = None,
    *,
    fetch: FetchFn | None = None,
    overlay_dir: Path | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Network fetch + overlay merge. Soft structure always returns dict with ok flag."""
    try:
        series = fetch_pmi_series(fetch=fetch)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"fetch_failed:{exc}", "month": month}
    target = month or (series[0]["month"] if series else None)
    if not target:
        return {"ok": False, "error": "no_data", "month": month}
    overlay = load_overlay(target, overlay_dir=overlay_dir)
    return build_pmi_snapshot(series, month=target, overlay=overlay, as_of=as_of)


def write_macro_pmi(path: Path, snapshot: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
