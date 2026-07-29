#!/usr/bin/env python3
"""Generate a deterministic full-day frozen JSON for composition development."""

from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")

OUTFLOW = [
    ("BK0481", "半导体", 200.0),
    ("BK0448", "通信设备", 180.0),
    ("BK0459", "元件", 120.0),
    ("BK0428", "电力设备", 55.0),
    ("BK0493", "消费电子", 48.0),
    ("BK0486", "光学光电子", 42.0),
    ("BK1038", "电子化学品", 35.0),
    ("BK0534", "国防军工", 32.0),
    ("BK0450", "机械设备", 25.0),
    ("BK0478", "有色金属", 20.0),
]
INFLOW = [
    ("BK0475", "银行", 15.27),
    ("BK0896", "白酒", 12.0),
    ("BK1029", "乘用车", 8.0),
    ("BK0730", "软件开发", 8.0),
    ("BK0438", "食品饮料", 6.0),
    ("BK0439", "家用电器", 5.0),
    ("BK0480", "传媒", 4.0),
    ("BK0427", "公用事业", 3.5),
    ("BK0482", "商贸零售", 3.0),
    ("BK0740", "教育", 2.0),
]


def trading_minutes(day: date) -> list[datetime]:
    stamps: list[datetime] = []
    cursor = datetime.combine(day, dtime(9, 30), tzinfo=TZ)
    morning_end = datetime.combine(day, dtime(11, 30), tzinfo=TZ)
    while cursor <= morning_end:
        stamps.append(cursor)
        cursor += timedelta(minutes=1)
    cursor = datetime.combine(day, dtime(13, 0), tzinfo=TZ)
    afternoon_end = datetime.combine(day, dtime(15, 0), tzinfo=TZ)
    while cursor <= afternoon_end:
        stamps.append(cursor)
        cursor += timedelta(minutes=1)
    return stamps


def ease_progress(i: int, n: int) -> float:
    """Slow start, faster mid-day, settle to 1.0 at the close."""
    if n <= 1:
        return 1.0
    x = i / (n - 1)
    # smoothstep that stays in [0, 1]
    return x * x * (3.0 - 2.0 * x)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-date", default=datetime.now(TZ).date().isoformat())
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    day = date.fromisoformat(args.trade_date)
    now = datetime.now(TZ)
    minutes = trading_minutes(day)
    n = len(minutes)

    frames = []
    for idx, ts in enumerate(minutes):
        p = ease_progress(idx, n)
        # mild mid-day wiggle that returns to 1.0 at the close
        wobble = 1.0 + 0.02 * math.sin(idx / 7.0) * (1.0 - p)
        outflow_top = []
        for rank, (code, name, final_v) in enumerate(OUTFLOW, start=1):
            value = round(final_v * p * wobble, 4)
            outflow_top.append({"rank": rank, "code": code, "name": name, "netYi": value})
        inflow_top = []
        for rank, (code, name, final_v) in enumerate(INFLOW, start=1):
            value = round(final_v * p * (1.0 + (1.0 - wobble)), 4)
            inflow_top.append({"rank": rank, "code": code, "name": name, "netYi": value})
        out_sum = sum(item["netYi"] for item in outflow_top)
        in_sum = sum(item["netYi"] for item in inflow_top)
        frames.append({
            "time": ts.strftime("%H:%M"),
            "stamp": ts.strftime("%Y-%m-%d %H:%M"),
            "outflowTop": outflow_top,
            "inflowTop": inflow_top,
            "marketExitYi": round(max(0.0, out_sum - in_sum), 4),
        })

    sectors = [
        {"code": c, "name": n, "side": "outflow", "finalNetYi": v}
        for c, n, v in OUTFLOW
    ] + [
        {"code": c, "name": n, "side": "inflow", "finalNetYi": v}
        for c, n, v in INFLOW
    ]

    payload = {
        "tradeDate": day.isoformat(),
        "dataCutoff": datetime.combine(day, dtime(15, 0), tzinfo=TZ).isoformat(timespec="seconds"),
        "fetchedAt": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "snapshotMode": "close",
        "synthetic": True,
        "source": "演示合成数据（结构对齐参考片；实盘请用 fetch_intraday_flow.py 盘后冻结）",
        "sourceUrl": "https://data.eastmoney.com/bkzj/hy.html",
        "unit": "亿元",
        "classification": "演示行业名称",
        "fieldNote": "主力净流入累计示意；跨板块连线为视觉示意，非真实对手方",
        "topN": 10,
        "boardCount": 20,
        "selectedCount": 20,
        "sectors": sectors,
        "frames": frames,
        "disclaimer": "数据来源于网络，不构成投资建议；流向示意，非真实对手方",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "synthetic": True,
        "frameCount": len(frames),
        "finalOutflow": frames[-1]["outflowTop"][:3],
        "finalInflow": frames[-1]["inflowTop"][:3],
        "marketExitYi": frames[-1]["marketExitYi"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
