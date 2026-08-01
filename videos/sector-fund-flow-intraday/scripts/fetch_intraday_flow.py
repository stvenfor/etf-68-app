#!/usr/bin/env python3
"""Fetch and freeze Eastmoney industry sector intraday main-net fund-flow series."""

from __future__ import annotations

import argparse
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
EM_UT = "b2884a393a59ad64002292a3e90d46a5"
# push2.eastmoney.com often drops connections; delay mirror is more stable.
EM_HOSTS = (
    "https://push2delay.eastmoney.com",
    "https://push2.eastmoney.com",
    "https://82.push2.eastmoney.com",
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}
# Trading minutes 09:30-11:30 and 13:00-15:00 inclusive of last print.
EXPECTED_MINUTES = 241
TOP_N = 10

# Eastmoney mixes 一级/二级/三级行业（银行 vs 银行Ⅱ vs …Ⅲ）with identical main-net.
_LEVEL_SUFFIX_RE = re.compile(r"(Ⅰ|Ⅱ|Ⅲ|Ⅳ|Ⅴ|III|II|IV|IX|VI{0,3}|I)$")
_LEVEL_ORDER = {
    "": 0,
    "Ⅰ": 1,
    "I": 1,
    "Ⅱ": 2,
    "II": 2,
    "Ⅲ": 3,
    "III": 3,
    "Ⅳ": 4,
    "IV": 4,
    "Ⅴ": 5,
    "V": 5,
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade-date", default=datetime.now(TZ).date().isoformat())
    parser.add_argument("--snapshot-mode", choices=("close", "latest"), default="close")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--top-n", type=int, default=TOP_N)
    parser.add_argument("--board-fs", default="m:90 t:2", help="Eastmoney clist fs filter")
    parser.add_argument("--min-boards", type=int, default=80)
    parser.add_argument("--sleep", type=float, default=0.08)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Skip full-day minute coverage gate (latest / debugging only)",
    )
    return parser.parse_args()


def clear_proxy_env() -> None:
    for key in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy",
    ):
        __import__("os").environ.pop(key, None)
    __import__("os").environ["NO_PROXY"] = "*"
    __import__("os").environ["no_proxy"] = "*"


def get_json(url: str, retries: int = 8) -> dict:
    """GET JSON; if URL uses push2 host, rotate EM_HOSTS on failure."""
    last: Exception | None = None
    candidates = [url]
    for host in EM_HOSTS:
        if "eastmoney.com/api/" in url and host not in url:
            # swap host prefix
            for old in EM_HOSTS:
                if old in url:
                    candidates.append(url.replace(old, host))
                    break
            else:
                # absolute path after domain
                idx = url.find("/api/")
                if idx > 0:
                    candidates.append(host + url[idx:])
    # de-dupe preserve order
    seen: set[str] = set()
    urls: list[str] = []
    for u in candidates:
        if u not in seen:
            seen.add(u)
            urls.append(u)

    for attempt in range(retries):
        target = urls[attempt % len(urls)]
        try:
            req = urllib.request.Request(target, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            ConnectionError,
            OSError,
        ) as exc:
            last = exc
            time.sleep(0.6 * (attempt + 1) + (attempt * 0.2))
    raise RuntimeError(f"GET failed after {retries} tries: {url}: {last}")


def market_cutoff(now: datetime, mode: str) -> datetime:
    current = now.time()
    if mode == "close":
        if current < dtime(15, 5):
            raise RuntimeError("Close snapshot is unavailable before 15:05 Asia/Shanghai")
        return now.replace(hour=15, minute=0, second=0, microsecond=0)
    if current < dtime(9, 30):
        raise RuntimeError("Latest snapshot is unavailable before 09:30 Asia/Shanghai")
    if dtime(11, 30) < current < dtime(13, 0):
        return now.replace(hour=11, minute=30, second=0, microsecond=0)
    if current >= dtime(15, 0):
        return now.replace(hour=15, minute=0, second=0, microsecond=0)
    return now.replace(second=0, microsecond=0)


def trading_minutes_for(day: date) -> list[str]:
    stamps: list[str] = []
    cursor = datetime.combine(day, dtime(9, 30), tzinfo=TZ)
    morning_end = datetime.combine(day, dtime(11, 30), tzinfo=TZ)
    while cursor <= morning_end:
        stamps.append(cursor.strftime("%Y-%m-%d %H:%M"))
        cursor += timedelta(minutes=1)
    cursor = datetime.combine(day, dtime(13, 0), tzinfo=TZ)
    afternoon_end = datetime.combine(day, dtime(15, 0), tzinfo=TZ)
    while cursor <= afternoon_end:
        stamps.append(cursor.strftime("%Y-%m-%d %H:%M"))
        cursor += timedelta(minutes=1)
    return stamps


def finite(value: object, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} is not finite: {value!r}")
    return number


def industry_stem(name: str) -> str:
    """Strip Eastmoney level suffixes: 银行Ⅱ → 银行, 国有大型银行Ⅲ → 国有大型银行."""
    return _LEVEL_SUFFIX_RE.sub("", name.strip()).strip()


def _level_rank(name: str) -> int:
    stem = industry_stem(name)
    if name == stem:
        return 0
    return _LEVEL_ORDER.get(name[len(stem) :], 9)


def prefer_industry_row(
    left: tuple[str, str, float],
    right: tuple[str, str, float],
) -> tuple[str, str, float]:
    """Prefer unsuffixed / shallower level / shorter name / smaller code."""
    _, left_name, _ = left
    _, right_name, _ = right
    left_key = (_level_rank(left_name), len(left_name), left[0])
    right_key = (_level_rank(right_name), len(right_name), right[0])
    return left if left_key <= right_key else right


def dedupe_hierarchical_nets(
    rows: list[tuple[str, str, float]],
    *,
    net_decimals: int = 2,
) -> list[tuple[str, str, float]]:
    """
    Drop multi-level industry clones that share the same stem + net.

    Eastmoney's industry clist mixes 一级/二级/三级 boards (e.g. 银行 + 银行Ⅱ)
    with identical主力净流入; ranking should keep only one.
    """
    winners: dict[tuple[str, int], tuple[str, str, float]] = {}
    order: list[tuple[str, int]] = []
    for row in rows:
        code, name, net = row
        key = (industry_stem(name), round(net, net_decimals))
        if key not in winners:
            winners[key] = row
            order.append(key)
            continue
        winners[key] = prefer_industry_row(winners[key], row)
    return [winners[key] for key in order]


def fetch_boards(fs: str, min_boards: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for pn in range(1, 20):
        query = urllib.parse.urlencode({
            "pn": str(pn),
            "pz": "100",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f62",
            "fs": fs,
            "fields": "f12,f14,f3,f62,f184",
            "ut": EM_UT,
            "_": str(int(time.time() * 1000)),
        })
        payload = get_json(f"{EM_HOSTS[0]}/api/qt/clist/get?{query}")
        diff = (payload.get("data") or {}).get("diff") or []
        items = diff if isinstance(diff, list) else list(diff.values())
        if not items:
            break
        for item in items:
            code = str(item.get("f12") or "").strip()
            name = str(item.get("f14") or "").strip()
            if not code or not name:
                continue
            net = item.get("f62")
            if net in (None, "-", ""):
                continue
            rows.append({
                "code": code,
                "name": name,
                "changePercent": finite(item.get("f3") or 0, f"{name}.change"),
                "mainNetYuan": finite(net, f"{name}.mainNet"),
            })
        if len(items) < 100:
            break
        time.sleep(0.05)
    # de-dupe by code
    by_code: dict[str, dict[str, object]] = {}
    for row in rows:
        by_code[str(row["code"])] = row
    unique = list(by_code.values())
    # Drop 银行/银行Ⅱ style clones with identical main-net.
    as_tuples = [
        (str(r["code"]), str(r["name"]), float(r["mainNetYuan"]) / 1e8)
        for r in unique
    ]
    kept_codes = {code for code, _, _ in dedupe_hierarchical_nets(as_tuples)}
    unique = [r for r in unique if str(r["code"]) in kept_codes]
    if len(unique) < min_boards:
        raise RuntimeError(f"Expected at least {min_boards} boards, got {len(unique)}")
    return unique


def fetch_fflow_klines(code: str) -> list[tuple[str, float]]:
    query = urllib.parse.urlencode({
        "lmt": "0",
        "klt": "1",
        "secid": f"90.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "ut": EM_UT,
        "_": str(int(time.time() * 1000)),
    })
    payload = get_json(f"{EM_HOSTS[0]}/api/qt/stock/fflow/kline/get?{query}")
    klines = (payload.get("data") or {}).get("klines") or []
    series: list[tuple[str, float]] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 2:
            continue
        stamp = parts[0].strip()
        # f52 = 主力净流入（元），累计
        main_net = finite(parts[1], f"{code}@{stamp}")
        series.append((stamp, main_net))
    return series


def yuan_to_yi(value: float) -> float:
    return round(value / 1e8, 4)


def fetch_two_market_stats(trade_date: date) -> dict[str, float]:
    """沪+深日成交额（亿元）及较昨/近五日日均增减。"""
    def amount_map(symbol: str) -> dict[str, float]:
        url = (
            "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
            f"?param={symbol},day,,,12,qfq&r=0.5"
        )
        payload = get_json(url)
        rows = ((payload.get("data") or {}).get(symbol) or {}).get("day") or []
        out: dict[str, float] = {}
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) < 9:
                continue
            day = str(row[0])[:10]
            try:
                wan = float(row[8])
            except (TypeError, ValueError):
                continue
            out[day] = wan / 10_000.0  # 万元 → 亿
        return out

    sh = amount_map("sh000001")
    sz = amount_map("sz399001")
    target = trade_date.isoformat()
    dates = sorted(d for d in (set(sh) & set(sz)) if d <= target)
    if not dates:
        raise RuntimeError("No two-market turnover series from Tencent fqkline")
    series = [round(sh[d] + sz[d], 2) for d in dates]
    today_amt = series[-1]
    prev_amt = series[-2] if len(series) >= 2 else today_amt
    last5 = series[-5:]
    avg5 = round(sum(last5) / len(last5), 2)
    return {
        "totalAmountYi": today_amt,
        "vsPrevDayYi": round(today_amt - prev_amt, 2),
        "vsFiveDayAvgYi": round(today_amt - avg5, 2),
        "prevDayAmountYi": prev_amt,
        "fiveDayAvgAmountYi": avg5,
    }


def build_frames(
    trade_date: date,
    selected: list[dict[str, object]],
    series_by_code: dict[str, dict[str, float]],
    top_n: int,
    allow_partial: bool,
) -> list[dict[str, object]]:
    minutes = trading_minutes_for(trade_date)
    frames: list[dict[str, object]] = []
    for stamp in minutes:
        hhmm = stamp[-5:]
        # skip lunch gap stamps already excluded
        nets: list[tuple[str, str, float]] = []
        for board in selected:
            code = str(board["code"])
            name = str(board["name"])
            path = series_by_code.get(code) or {}
            if stamp in path:
                net_yi = yuan_to_yi(path[stamp])
            else:
                # forward-fill from last known <= stamp
                prior = [k for k in path if k <= stamp]
                net_yi = yuan_to_yi(path[max(prior)]) if prior else 0.0
            nets.append((code, name, net_yi))

        nets = dedupe_hierarchical_nets(nets)
        outflow = sorted((row for row in nets if row[2] < 0), key=lambda r: (r[2], r[1]))[:top_n]
        inflow = sorted((row for row in nets if row[2] > 0), key=lambda r: (-r[2], r[1]))[:top_n]
        out_sum = abs(sum(r[2] for r in outflow))
        in_sum = sum(r[2] for r in inflow)
        # Signed: >0 市场离场, <0 市场进场
        market_exit = round(out_sum - in_sum, 4)
        frames.append({
            "time": hhmm,
            "stamp": stamp,
            "outflowTop": [
                {"rank": i + 1, "code": c, "name": n, "netYi": round(abs(v), 4)}
                for i, (c, n, v) in enumerate(outflow)
            ],
            "inflowTop": [
                {"rank": i + 1, "code": c, "name": n, "netYi": round(v, 4)}
                for i, (c, n, v) in enumerate(inflow)
            ],
            "marketExitYi": market_exit,
        })

    if not allow_partial:
        non_empty = [f for f in frames if f["outflowTop"] or f["inflowTop"]]
        if len(non_empty) < EXPECTED_MINUTES * 0.85:
            raise RuntimeError(
                f"Incomplete intraday coverage: {len(non_empty)} usable minutes "
                f"(need ~{EXPECTED_MINUTES}). Re-run after 15:05 or pass --allow-partial."
            )
        last = frames[-1]
        if last["time"] != "15:00":
            raise RuntimeError(f"Expected final frame 15:00, got {last['time']}")
        if len(last["outflowTop"]) < top_n or len(last["inflowTop"]) < top_n:
            raise RuntimeError("Final frame missing full TOP lists")
    return frames


def main() -> None:
    clear_proxy_env()
    args = parse_args()
    now = datetime.now(TZ)
    target = date.fromisoformat(args.trade_date)
    if target != now.date():
        raise RuntimeError(
            "Eastmoney intraday fflow kline is same-day only; "
            "provide an existing frozen JSON for historical dates"
        )
    cutoff = market_cutoff(now, args.snapshot_mode)
    boards = fetch_boards(args.board_fs, args.min_boards)

    # Anchor selection on latest cumulative main-net so the cast stays stable.
    ordered = sorted(boards, key=lambda b: float(b["mainNetYuan"]))
    outflow_seed = ordered[: max(args.top_n * 2, args.top_n)]
    inflow_seed = list(reversed(ordered[-max(args.top_n * 2, args.top_n) :]))
    selected_map: dict[str, dict[str, object]] = {}
    for row in outflow_seed + inflow_seed:
        selected_map[str(row["code"])] = row
    selected = list(selected_map.values())

    series_by_code: dict[str, dict[str, float]] = {}
    for idx, board in enumerate(selected):
        code = str(board["code"])
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                points = fetch_fflow_klines(code)
                series_by_code[code] = {stamp: value for stamp, value in points}
                last_err = None
                break
            except Exception as exc:  # noqa: BLE001 — transient Eastmoney disconnects
                last_err = exc
                time.sleep(1.2 * (attempt + 1))
        if last_err is not None:
            raise RuntimeError(f"fflow kline failed for {code}: {last_err}") from last_err
        if (idx + 1) % 5 == 0:
            print(f"fetched klines {idx + 1}/{len(selected)}", flush=True)
        time.sleep(args.sleep)

    frames = build_frames(
        target,
        selected,
        series_by_code,
        args.top_n,
        allow_partial=args.allow_partial or args.snapshot_mode == "latest",
    )

    try:
        market_stats = fetch_two_market_stats(target)
    except Exception as exc:  # noqa: BLE001 — keep flow freeze even if turnover fails
        print(f"WARN marketStats unavailable: {exc}", flush=True)
        market_stats = {
            "totalAmountYi": 0.0,
            "vsPrevDayYi": 0.0,
            "vsFiveDayAvgYi": 0.0,
        }

    # Stable end-of-day cast for particle wiring (final ranking order).
    final = frames[-1]
    sectors = []
    for item in final["outflowTop"]:
        sectors.append({
            "code": item["code"],
            "name": item["name"],
            "side": "outflow",
            "finalNetYi": item["netYi"],
        })
    for item in final["inflowTop"]:
        sectors.append({
            "code": item["code"],
            "name": item["name"],
            "side": "inflow",
            "finalNetYi": item["netYi"],
        })

    payload = {
        "tradeDate": target.isoformat(),
        "dataCutoff": cutoff.isoformat(timespec="seconds"),
        "fetchedAt": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "snapshotMode": args.snapshot_mode,
        "synthetic": False,
        "source": "东方财富行业板块资金流分时 (push2 fflow/kline klt=1, f52 主力净流入)",
        "sourceUrl": "https://data.eastmoney.com/bkzj/hy.html",
        "unit": "亿元",
        "classification": "东方财富行业板块",
        "fieldNote": "主力净流入累计值；跨板块连线为视觉示意，非真实对手方",
        "topN": args.top_n,
        "boardCount": len(boards),
        "selectedCount": len(selected),
        "sectors": sectors,
        "frames": frames,
        "marketStats": market_stats,
        "disclaimer": "数据来源于网络，不构成投资建议；流向示意，非真实对手方",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "fetchedAt": payload["fetchedAt"],
        "dataCutoff": payload["dataCutoff"],
        "frameCount": len(frames),
        "finalOutflow": final["outflowTop"][:5],
        "finalInflow": final["inflowTop"][:5],
        "marketExitYi": final["marketExitYi"],
        "marketStats": market_stats,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
