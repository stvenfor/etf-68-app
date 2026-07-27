"""Tests for week/month direction + daily entry signals."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from src.market_data import DailyBar  # noqa: E402
from src.wm_daily_signal import (  # noqa: E402
    SIGNAL_DIR_MIXED,
    SIGNAL_LONG,
    SIGNAL_NO_LONG,
    SIGNAL_OVERHEAT,
    SIGNAL_WAIT_DAILY,
    aggregate_monthly_bars,
    decide_wm_daily_signal,
    monthly_trend_label,
)


FETCHED_AT = datetime(2026, 7, 24, 18, 0, tzinfo=timezone(timedelta(hours=8)))


def _bars_rising(n: int = 130) -> list[DailyBar]:
    start = date(2025, 12, 1)
    out: list[DailyBar] = []
    px = 1.0
    for i in range(n):
        px += 0.01
        d = start + timedelta(days=i)
        out.append(
            DailyBar(
                date=d,
                open=px,
                close=px,
                high=px * 1.01,
                low=px * 0.99,
                volume=1_000_000,
                turnover_cny=1_000_000 * px,
                source="fixture",
                timestamp=FETCHED_AT,
            )
        )
    return out


class WmDailySignalTests(unittest.TestCase):
    def test_monthly_aggregation_and_uptrend(self) -> None:
        bars = _bars_rising(150)
        monthly = aggregate_monthly_bars(bars)
        self.assertGreaterEqual(len(monthly), 5)
        self.assertEqual("多头", monthly_trend_label(bars))

    def test_decide_labels(self) -> None:
        self.assertEqual(
            SIGNAL_LONG,
            decide_wm_daily_signal(
                monthly_trend="多头",
                weekly_trend="多头",
                daily_trend="多头",
                ret1=1.0,
                distance_ma20=2.0,
            ),
        )
        self.assertEqual(
            SIGNAL_WAIT_DAILY,
            decide_wm_daily_signal(
                monthly_trend="多头",
                weekly_trend="多头",
                daily_trend="震荡",
                ret1=0.0,
                distance_ma20=1.0,
            ),
        )
        self.assertEqual(
            SIGNAL_OVERHEAT,
            decide_wm_daily_signal(
                monthly_trend="多头",
                weekly_trend="多头",
                daily_trend="多头",
                ret1=4.0,
                distance_ma20=1.0,
            ),
        )
        self.assertEqual(
            SIGNAL_DIR_MIXED,
            decide_wm_daily_signal(
                monthly_trend="多头",
                weekly_trend="震荡",
                daily_trend="多头",
                ret1=0.0,
                distance_ma20=0.0,
            ),
        )
        self.assertEqual(
            SIGNAL_NO_LONG,
            decide_wm_daily_signal(
                monthly_trend="空头",
                weekly_trend="多头",
                daily_trend="多头",
                ret1=0.0,
                distance_ma20=0.0,
            ),
        )


if __name__ == "__main__":
    unittest.main()
