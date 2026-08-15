#!/usr/bin/env python3
"""Exit 0 if DATE is an A-share trading day, else 1.

Usage:
  python3 scripts/is_trading_day.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")

# SSE/SZSE closed weekdays (国务院放假 + 调休补班反向：仅列休市日).
# 补班周六另计入 _MAKEUP_TRADING_DAYS。
_CLOSED_WEEKDAYS = frozenset(
    {
        # 2025
        "2025-01-01",
        "2025-01-28",
        "2025-01-29",
        "2025-01-30",
        "2025-01-31",
        "2025-02-03",
        "2025-02-04",
        "2025-04-04",
        "2025-05-01",
        "2025-05-02",
        "2025-05-05",
        "2025-06-02",
        "2025-10-01",
        "2025-10-02",
        "2025-10-03",
        "2025-10-06",
        "2025-10-07",
        "2025-10-08",
        # 2026
        "2026-01-01",
        "2026-01-02",
        "2026-02-16",
        "2026-02-17",
        "2026-02-18",
        "2026-02-19",
        "2026-02-20",
        "2026-02-23",
        "2026-04-06",
        "2026-05-01",
        "2026-05-04",
        "2026-05-05",
        "2026-06-19",
        "2026-09-25",
        "2026-10-01",
        "2026-10-02",
        "2026-10-05",
        "2026-10-06",
        "2026-10-07",
    }
)

# 调休上班（周末开市）
_MAKEUP_TRADING_DAYS = frozenset(
    {
        "2025-01-26",
        "2025-02-08",
        "2025-04-27",
        "2025-09-28",
        "2025-10-11",
        "2026-01-04",
        "2026-02-14",
        "2026-02-28",
        "2026-05-09",
        "2026-09-20",
        "2026-10-10",
    }
)


def clear_proxy() -> None:
    import os

    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"


def live_index_has_date(d: date) -> bool | None:
    """True/False if 上证指数日K含该日；网络失败返回 None。"""
    clear_proxy()
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid=1.000001&klt=101&fqt=1&end={d.strftime('%Y%m%d')}&lmt=8"
        "&fields1=f1&fields2=f51"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        rows = (payload.get("data") or {}).get("klines") or []
        dates = {str(r).split(",", 1)[0] for r in rows}
        return d.isoformat() in dates
    except Exception:  # noqa: BLE001
        return None


def is_trading_day(d: date) -> tuple[bool, str]:
    iso = d.isoformat()
    if iso in _MAKEUP_TRADING_DAYS:
        return True, "makeup"
    if iso in _CLOSED_WEEKDAYS:
        return False, "holiday_static"
    if d.weekday() >= 5:
        return False, "weekend"
    live = live_index_has_date(d)
    # 工作日默认继续；日K 仅作旁证（盘后可能尚未写入）。
    if live is True:
        return True, "weekday_live"
    if live is False:
        return True, "weekday_live_missing_bar"
    return True, "weekday"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=datetime.now(TZ).date().isoformat())
    args = parser.parse_args()
    d = date.fromisoformat(args.date)
    ok, reason = is_trading_day(d)
    print(
        json.dumps(
            {"date": d.isoformat(), "is_trading_day": ok, "reason": reason},
            ensure_ascii=False,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
