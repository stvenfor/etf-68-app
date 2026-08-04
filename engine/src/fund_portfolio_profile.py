"""Eastmoney F10 portfolio profile: industry weights, asset mix, risk level.

Soft-fail per fund. Used by my_holdings to show 行业占比 / 股债仓位 / R1–R5.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

from .funds_top30 import FetchFn, _default_fetch, _num

SHANGHAI = ZoneInfo("Asia/Shanghai")

RISK_LABELS: dict[str, str] = {
    "1": "低风险",
    "2": "中低风险",
    "3": "中等风险",
    "4": "中高风险",
    "5": "高风险",
}

RISK_NOTES: dict[str, str] = {
    "1": "波动通常较低，仍可能受利率与流动性影响",
    "2": "波动低于权益类，仍受利率与信用影响",
    "3": "股债混合或均衡风格，波动居中",
    "4": "净值波动较大，回撤风险更高",
    "5": "高波动权益/主题风格，回撤风险高",
}

PROFILE_KEYS = (
    "riskLevel",
    "riskLabel",
    "riskNote",
    "assetMix",
    "industries",
    "industryAsOf",
    "profileError",
)


def parse_pingzhong_asset_mix(body: str) -> dict[str, Any] | None:
    """Parse latest report-period stock/bond/cash % from pingzhong Data_assetAllocation."""
    m = re.search(r"Data_assetAllocation\s*=\s*(\{.*?\});", body, re.S)
    if not m:
        return None
    try:
        payload = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    categories = payload.get("categories") or []
    series = payload.get("series") or []
    if not categories or not isinstance(series, list):
        return None
    idx = len(categories) - 1
    as_of = str(categories[idx])[:10] if categories[idx] is not None else None

    def _series_val(name_substr: str) -> Optional[float]:
        for s in series:
            if not isinstance(s, dict):
                continue
            name = str(s.get("name") or "")
            if name_substr not in name:
                continue
            data = s.get("data") or []
            if idx < len(data):
                return _num(data[idx])
        return None

    stock = _series_val("股票")
    bond = _series_val("债券")
    cash = _series_val("现金")
    if stock is None and bond is None and cash is None:
        return None
    known = [x for x in (stock, bond, cash) if x is not None]
    other = None
    if known:
        other = round(max(0.0, 100.0 - sum(known)), 2)
    return {
        "stockPct": stock,
        "bondPct": bond,
        "cashPct": cash,
        "otherPct": other,
        "asOf": as_of,
    }


def parse_hypz_industries(payload: Mapping[str, Any], *, top_n: int = 5) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Return (TOP industries, asOf) from HYPZ JSON Data.QuarterInfos."""
    data = payload.get("Data") if isinstance(payload, Mapping) else None
    if not isinstance(data, Mapping):
        return [], None
    quarters = data.get("QuarterInfos") or []
    if not isinstance(quarters, list) or not quarters:
        return [], None
    # API usually newest-first; pick max FSRQ/JZRQ just in case
    best = None
    best_day = ""
    for q in quarters:
        if not isinstance(q, dict):
            continue
        day = str(q.get("JZRQ") or "")[:10]
        infos = q.get("HYPZInfo") or []
        if not isinstance(infos, list) or not infos:
            continue
        if day >= best_day:
            best_day = day
            best = infos
    if not best:
        return [], None
    rows: list[dict[str, Any]] = []
    for item in best:
        if not isinstance(item, dict):
            continue
        name = str(item.get("HYMC") or "").strip()
        w = _num(item.get("ZJZBL"))
        if not name or w is None:
            continue
        rows.append({"name": name, "weightPct": round(float(w), 2)})
    rows.sort(key=lambda x: x["weightPct"], reverse=True)
    return rows[: max(1, top_n)], best_day or None


def parse_risk_level(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Parse RISKLEVEL from FundMNbasicInformation Datas."""
    datas = payload.get("Datas") if isinstance(payload, Mapping) else None
    if not isinstance(datas, Mapping):
        datas = payload if isinstance(payload, Mapping) else None
    if not isinstance(datas, Mapping):
        return None
    raw = datas.get("RISKLEVEL")
    if raw is None or raw == "":
        return None
    key = str(raw).strip()
    # Sometimes "R3" / "3"
    if key.upper().startswith("R") and len(key) >= 2 and key[1:].isdigit():
        key = key[1:]
    if key not in RISK_LABELS:
        # try digit only
        m = re.search(r"[1-5]", key)
        if not m:
            return None
        key = m.group(0)
    return {
        "riskLevel": f"R{key}",
        "riskLabel": RISK_LABELS[key],
        "riskNote": RISK_NOTES[key],
    }


def fetch_hypz_industries(
    code: str,
    *,
    fetch: FetchFn = _default_fetch,
    years: Sequence[int] | None = None,
    top_n: int = 5,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    now_y = datetime.now(SHANGHAI).year
    try_years = list(years) if years is not None else [now_y, now_y - 1]
    for year in try_years:
        url = f"https://api.fund.eastmoney.com/f10/HYPZ/?fundCode={code}&year={year}"
        try:
            raw = fetch(url)
            start = raw.find("{")
            end = raw.rfind("}")
            if start < 0 or end <= start:
                continue
            payload = json.loads(raw[start : end + 1])
            industries, as_of = parse_hypz_industries(payload, top_n=top_n)
            if industries:
                return industries, as_of
        except Exception:  # noqa: BLE001
            continue
    return [], None


def fetch_risk_level(code: str, *, fetch: FetchFn = _default_fetch) -> dict[str, Any] | None:
    url = (
        "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNbasicInformation"
        f"?FCODE={code}&deviceid=Wap&plat=Wap&product=EFund&version=2.0.0"
    )
    try:
        raw = fetch(url)
        payload = json.loads(raw)
        return parse_risk_level(payload)
    except Exception:  # noqa: BLE001
        return None


def fetch_asset_mix_from_pingzhong(code: str, *, fetch: FetchFn = _default_fetch) -> dict[str, Any] | None:
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    try:
        body = fetch(url)
        return parse_pingzhong_asset_mix(body)
    except Exception:  # noqa: BLE001
        return None


def _copy_profile(src: Mapping[str, Any] | None) -> dict[str, Any]:
    if not src:
        return {}
    out: dict[str, Any] = {}
    for k in PROFILE_KEYS:
        if k in src and src[k] is not None:
            out[k] = src[k]
    return out


def fetch_one_profile(
    code: str,
    *,
    fetch: FetchFn = _default_fetch,
    previous: Mapping[str, Any] | None = None,
    asset_mix: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch industries + risk (+ asset mix if not provided). Soft-fail with previous fallback."""
    prev = _copy_profile(previous)
    errors: list[str] = []
    out: dict[str, Any] = {}

    if asset_mix and (asset_mix.get("stockPct") is not None or asset_mix.get("bondPct") is not None):
        out["assetMix"] = dict(asset_mix)
    else:
        mix = fetch_asset_mix_from_pingzhong(code, fetch=fetch)
        if mix:
            out["assetMix"] = mix
        elif prev.get("assetMix"):
            out["assetMix"] = prev["assetMix"]
        else:
            errors.append("assetMix")

    try:
        industries, as_of = fetch_hypz_industries(code, fetch=fetch)
        if industries:
            out["industries"] = industries
            out["industryAsOf"] = as_of
        elif prev.get("industries"):
            out["industries"] = prev["industries"]
            out["industryAsOf"] = prev.get("industryAsOf")
        else:
            errors.append("industries")
    except Exception:  # noqa: BLE001
        if prev.get("industries"):
            out["industries"] = prev["industries"]
            out["industryAsOf"] = prev.get("industryAsOf")
        else:
            errors.append("industries")

    risk = fetch_risk_level(code, fetch=fetch)
    if risk:
        out.update(risk)
    elif prev.get("riskLevel"):
        out["riskLevel"] = prev.get("riskLevel")
        out["riskLabel"] = prev.get("riskLabel")
        out["riskNote"] = prev.get("riskNote")
    else:
        errors.append("risk")

    if errors and not any(out.get(k) for k in ("industries", "assetMix", "riskLevel")):
        out["profileError"] = "profile_unavailable:" + ",".join(errors)
    elif errors:
        out["profileError"] = "partial:" + ",".join(errors)
    else:
        out.pop("profileError", None)
    return out


def enrich_portfolio_profile(
    rows: Sequence[Mapping[str, Any]],
    *,
    fetch: FetchFn = _default_fetch,
    previous_by_code: Mapping[str, Mapping[str, Any]] | None = None,
    workers: int = 5,
) -> list[dict[str, Any]]:
    """Attach risk / assetMix / industries onto each row (soft-fail per code)."""
    prev_map = previous_by_code or {}
    items = [dict(r) for r in rows]
    if not items:
        return items

    def _job(idx: int, row: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        code = str(row.get("code") or "").zfill(6)
        existing_mix = row.get("assetMix") if isinstance(row.get("assetMix"), dict) else None
        profile = fetch_one_profile(
            code,
            fetch=fetch,
            previous=prev_map.get(code),
            asset_mix=existing_mix,
        )
        return idx, profile

    workers = max(1, min(workers, len(items)))
    if workers == 1:
        for i, row in enumerate(items):
            _, profile = _job(i, row)
            row.update(profile)
        return items

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_job, i, row) for i, row in enumerate(items)]
        for fut in as_completed(futs):
            try:
                idx, profile = fut.result()
                items[idx].update(profile)
            except Exception:  # noqa: BLE001
                continue
    return items
