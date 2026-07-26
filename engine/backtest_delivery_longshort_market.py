#!/usr/bin/env python3.12
"""Backtest: CFFEX 中信期货(代客) net long/short on equity-index delivery days
vs spot index returns (T / T+1 / T+3).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any
from zoneinfo import ZoneInfo

CFFEX_ROOT = Path(__file__).resolve().parents[1] / "cffex-daily"
sys.path.insert(0, str(CFFEX_ROOT))
from fetch_and_render import fetch_report  # noqa: E402

MODULE_ROOT = Path(__file__).resolve().parent
OUT_DIR = MODULE_ROOT / "reports"
CACHE_DIR = CFFEX_ROOT / "work" / "output"
SHANGHAI = ZoneInfo("Asia/Shanghai")

# Known holiday-shifted delivery dates (third Friday → next trading day)
KNOWN_SHIFTS = {
    date(2024, 2, 16): date(2024, 2, 19),  # 春节附近（若第三周五仍交易则不用）
    date(2025, 1, 17): date(2025, 1, 17),
    date(2025, 2, 21): date(2025, 2, 24),  # 春节
    date(2026, 2, 20): date(2026, 2, 24),
    date(2026, 6, 19): date(2026, 6, 22),
}

INDEX_TENCENT = {
    "sh": "sh000001",
    "sz": "sz399001",
    "ih": "sh000016",
    "if": "sh000300",
    "ic": "sh000905",
    "im": "sh000852",
}


def fetch_index_closes(symbol: str, start: date, end: date) -> dict[date, float]:
    """Fetch daily closes via Tencent (Eastmoney often drops connections)."""
    param = f"{symbol},day,{start.isoformat()},{end.isoformat()},800,qfq"
    url = f"https://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get?param={param}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            block = (payload.get("data") or {}).get(symbol) or {}
            rows = block.get("qfqday") or block.get("day") or []
            out: dict[date, float] = {}
            for row in rows:
                if not row or len(row) < 3:
                    continue
                d = date.fromisoformat(str(row[0])[:10])
                out[d] = float(row[2])
            if out:
                return out
        except Exception as exc:
            last_err = exc
            import time

            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"index_fetch_failed:{symbol}:{last_err}")


def third_fridays(year: int) -> list[date]:
    out: list[date] = []
    for month in range(1, 13):
        d = date(year, month, 1)
        # first Friday
        while d.weekday() != 4:
            d += timedelta(days=1)
        # third Friday
        d += timedelta(weeks=2)
        out.append(d)
    return out


def delivery_dates(years: list[int]) -> list[date]:
    days: list[date] = []
    for y in years:
        for fri in third_fridays(y):
            days.append(KNOWN_SHIFTS.get(fri, fri))
    # unique sorted, only up to today
    today = datetime.now(SHANGHAI).date()
    return sorted({d for d in days if d <= today})


def load_or_fetch_citic(day: date, *, fetch: bool = True, timeout_s: float = 12) -> dict[str, Any] | None:
    stem = day.strftime("%Y%m%d")
    path = CACHE_DIR / f"citic-net-positions-{stem}.json"
    if path.exists() and path.stat().st_size > 50:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if "citic_total" in data:
                return data
        except json.JSONDecodeError:
            pass
    if not fetch:
        return None
    # socket-level timeout around CFFEX fetch
    import socket

    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout_s)
    try:
        try:
            report = fetch_report(day)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return report
        except Exception:
            for add in (1, 2, 3):
                alt = day + timedelta(days=add)
                if alt.weekday() >= 5:
                    continue
                alt_path = CACHE_DIR / f"citic-net-positions-{alt.strftime('%Y%m%d')}.json"
                if alt_path.exists() and alt_path.stat().st_size > 50:
                    try:
                        report = json.loads(alt_path.read_text(encoding="utf-8"))
                        report["_actual_date"] = alt.isoformat()
                        return report
                    except json.JSONDecodeError:
                        pass
                try:
                    report = fetch_report(alt)
                    alt_path.write_text(
                        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                    )
                    report["_actual_date"] = alt.isoformat()
                    return report
                except Exception:
                    continue
    finally:
        socket.setdefaulttimeout(old)
    return None


def pct(a: float, b: float) -> float | None:
    if a <= 0 or b <= 0:
        return None
    return round((b / a - 1) * 100, 4)


def corr(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx, my = fmean(xs), fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx <= 0 or deny <= 0:
        return None
    return round(num / (denx * deny), 4)


def summarize(group: list[dict[str, Any]], key: str) -> dict[str, Any]:
    vals = [float(r[key]) for r in group if r.get(key) is not None]
    if not vals:
        return {"n": 0}
    ups = sum(1 for v in vals if v > 0)
    return {
        "n": len(vals),
        "mean": round(fmean(vals), 4),
        "std": round(pstdev(vals), 4) if len(vals) > 1 else 0.0,
        "winRate": round(ups / len(vals), 4),
        "median": round(sorted(vals)[len(vals) // 2], 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--years", default="2024,2025,2026")
    ap.add_argument("--no-fetch", action="store_true", help="Only use cached citic JSON")
    ap.add_argument(
        "--output",
        type=Path,
        default=OUT_DIR / "delivery-longshort-market-backtest.json",
    )
    args = ap.parse_args()
    years = [int(y.strip()) for y in args.years.split(",") if y.strip()]
    days = delivery_dates(years)

    # Prefer cache; optional network fetch with short timeout
    citic_by_day: dict[date, dict[str, Any]] = {}
    do_fetch = not args.no_fetch
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {
            ex.submit(load_or_fetch_citic, d, fetch=do_fetch, timeout_s=10): d for d in days
        }
        for fut in as_completed(futs):
            d0 = futs[fut]
            try:
                rep = fut.result()
            except Exception:
                rep = None
            if rep:
                actual = date.fromisoformat(rep["_actual_date"]) if "_actual_date" in rep else d0
                citic_by_day[actual] = rep

    if not citic_by_day:
        raise SystemExit("no_citic_data")

    # index history spanning all days + 10 sessions buffer
    min_d = min(citic_by_day) - timedelta(days=10)
    max_d = max(citic_by_day) + timedelta(days=20)
    closes: dict[str, dict[date, float]] = {}
    for name, symbol in INDEX_TENCENT.items():
        closes[name] = fetch_index_closes(symbol, min_d, max_d)

    def next_sessions(d: date, n: int) -> list[date]:
        # trading dates present in sh calendar
        keys = sorted(closes["sh"])
        if d not in closes["sh"]:
            # find first >= d
            later = [k for k in keys if k >= d]
            if not later:
                return []
            d = later[0]
        i = keys.index(d)
        return keys[i : i + n + 1]  # include T

    rows: list[dict[str, Any]] = []
    for d, rep in sorted(citic_by_day.items()):
        total = int(rep.get("citic_total") or 0)
        by_sym = rep.get("citic_by_symbol") or {}
        # Skip empty/placeholder CFFEX payloads
        if total == 0 and all(int(by_sym.get(s) or 0) == 0 for s in ("IH", "IF", "IC", "IM")):
            continue
        sess = next_sessions(d, 3)
        if len(sess) < 1:
            continue
        t0 = sess[0]
        row: dict[str, Any] = {
            "delivery": t0.isoformat(),
            "planned": d.isoformat(),
            "citicTotal": total,
            "stance": "净加多" if total > 0 else ("净加空" if total < 0 else "平"),
            "IH": by_sym.get("IH"),
            "IF": by_sym.get("IF"),
            "IC": by_sym.get("IC"),
            "IM": by_sym.get("IM"),
        }
        for idx_name in INDEX_TENCENT:
            c = closes[idx_name]
            if t0 not in c:
                continue
            # T day return: need previous session
            keys = sorted(c)
            ti = keys.index(t0)
            if ti == 0:
                continue
            prev = keys[ti - 1]
            row[f"{idx_name}PctT"] = pct(c[prev], c[t0])
            if len(sess) > 1 and sess[1] in c:
                row[f"{idx_name}PctT1"] = pct(c[t0], c[sess[1]])
            if len(sess) > 3 and sess[3] in c:
                row[f"{idx_name}PctT3"] = pct(c[t0], c[sess[3]])
            # from prev close to T+3
            if len(sess) > 3 and sess[3] in c:
                row[f"{idx_name}PctPrevToT3"] = pct(c[prev], c[sess[3]])
        rows.append(row)

    long_rows = [r for r in rows if (r.get("citicTotal") or 0) > 0]
    short_rows = [r for r in rows if (r.get("citicTotal") or 0) < 0]

    metrics: dict[str, Any] = {}
    for idx_name, label in [
        ("sh", "上证"),
        ("sz", "深成"),
        ("ih", "上证50"),
        ("if", "沪深300"),
        ("ic", "中证500"),
        ("im", "中证1000"),
    ]:
        for horizon in ("PctT", "PctT1", "PctT3", "PctPrevToT3"):
            key = f"{idx_name}{horizon}"
            metrics[f"{label}_{horizon}"] = {
                "all": summarize(rows, key),
                "净加多": summarize(long_rows, key),
                "净加空": summarize(short_rows, key),
            }

    # correlation citicTotal vs returns
    correlations: dict[str, float | None] = {}
    for idx_name, label in [("sh", "上证"), ("if", "沪深300"), ("ic", "中证500"), ("im", "中证1000")]:
        for horizon, hlab in [("PctT", "当日"), ("PctT1", "次日"), ("PctT3", "三日")]:
            key = f"{idx_name}{horizon}"
            pairs = [
                (float(r["citicTotal"]), float(r[key]))
                for r in rows
                if r.get("citicTotal") is not None and r.get(key) is not None
            ]
            if not pairs:
                correlations[f"{label}_{hlab}"] = None
            else:
                correlations[f"{label}_{hlab}"] = corr([p[0] for p in pairs], [p[1] for p in pairs])

    # directional agreement: sign(citic) == sign(return)
    agreement: dict[str, Any] = {}
    for idx_name, label in [("sh", "上证"), ("if", "沪深300"), ("im", "中证1000")]:
        for horizon, hlab in [("PctT", "当日"), ("PctT3", "三日")]:
            key = f"{idx_name}{horizon}"
            ok = 0
            n = 0
            for r in rows:
                ct = r.get("citicTotal")
                ret = r.get(key)
                if ct is None or ret is None or ct == 0 or ret == 0:
                    continue
                n += 1
                if (ct > 0 and ret > 0) or (ct < 0 and ret < 0):
                    ok += 1
            agreement[f"{label}_{hlab}"] = {
                "n": n,
                "sameDirectionRate": round(ok / n, 4) if n else None,
            }

    # strong short / strong long buckets (|citic| >= median abs)
    abs_vals = sorted(abs(int(r["citicTotal"])) for r in rows)
    med_abs = abs_vals[len(abs_vals) // 2] if abs_vals else 0
    strong_short = [r for r in short_rows if abs(int(r["citicTotal"])) >= med_abs]
    strong_long = [r for r in long_rows if abs(int(r["citicTotal"])) >= med_abs]

    findings = []
    sh_t_short = metrics.get("上证_PctT", {}).get("净加空", {})
    sh_t_long = metrics.get("上证_PctT", {}).get("净加多", {})
    if sh_t_short.get("n", 0) and sh_t_long.get("n", 0):
        findings.append(
            f"交割日当天：中信净加空样本上证均{sh_t_short['mean']:+.2f}%（涨面{sh_t_short['winRate']*100:.0f}%），"
            f"净加多样本均{sh_t_long['mean']:+.2f}%（涨面{sh_t_long['winRate']*100:.0f}%）。"
        )
    im_t3_short = metrics.get("中证1000_PctT3", {}).get("净加空", {})
    im_t3_long = metrics.get("中证1000_PctT3", {}).get("净加多", {})
    if im_t3_short.get("n") and im_t3_long.get("n"):
        findings.append(
            f"交割后三日（相对交割收盘）：净加空时中证1000均{im_t3_short['mean']:+.2f}%，"
            f"净加多时均{im_t3_long['mean']:+.2f}%。"
        )
    ag = agreement.get("上证_当日") or {}
    if ag.get("sameDirectionRate") is not None:
        findings.append(
            f"中信净变动方向与上证当日涨跌同向比例 {ag['sameDirectionRate']*100:.0f}%（n={ag['n']}）；"
            f"相关（上证当日）={correlations.get('上证_当日')}。"
        )
    findings.append(
        "口径：中信期货(代客)当日净增仓合计；指数涨跌为收盘价；样本含已发生交割日。"
        "相关≠因果，交割踩踏与宏观冲击常同时发生。"
    )

    payload = {
        "generatedAt": datetime.now(SHANGHAI).isoformat(),
        "years": years,
        "sampleSize": len(rows),
        "longDays": len(long_rows),
        "shortDays": len(short_rows),
        "medianAbsCitic": med_abs,
        "strongLongN": len(strong_long),
        "strongShortN": len(strong_short),
        "strongShort_上证_PctT": summarize(strong_short, "shPctT"),
        "strongLong_上证_PctT": summarize(strong_long, "shPctT"),
        "metrics": metrics,
        "correlations": correlations,
        "agreement": agreement,
        "findings": findings,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sampleSize": len(rows),
                "longDays": len(long_rows),
                "shortDays": len(short_rows),
                "findings": findings,
                "correlations": correlations,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
