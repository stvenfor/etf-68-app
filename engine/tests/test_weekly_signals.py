"""Tests for weekly MACD + MA framework and action gate."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from src.market_data import DailyBar  # noqa: E402
from src.report_generator import build_report  # noqa: E402
from src.reporting import SharePoint, calculate_macd  # noqa: E402
from src.weekly_signals import (  # noqa: E402
    aggregate_weekly_bars,
    decide_action,
    macd_is_bullish,
    passes_gate,
    select_best_params,
    volume_price_from_ratio_ret,
)


FETCHED_AT = datetime(2026, 7, 24, 16, 0, tzinfo=timezone(timedelta(hours=8)))


def _daily_trend(count: int = 400, *, up: bool = True) -> list[DailyBar]:
    """Generate weekday-ish bars with a clear long uptrend or downtrend."""
    start = date(2022, 1, 3)
    bars: list[DailyBar] = []
    d = start
    price = 10.0
    while len(bars) < count:
        if d.weekday() < 5:
            if up:
                price *= 1.0025
            else:
                price *= 0.9975
            # mild weekly rhythm
            wobble = 1 + 0.01 * ((len(bars) % 5) - 2) / 100
            close = price * wobble
            bars.append(
                DailyBar(
                    date=d,
                    open=close * 0.999,
                    close=close,
                    high=close * 1.01,
                    low=close * 0.99,
                    volume=1_000_000,
                    turnover_cny=close * 1_000_000,
                    source="fixture",
                    timestamp=FETCHED_AT,
                )
            )
        d += timedelta(days=1)
    return bars


class WeeklyAggregationTests(unittest.TestCase):
    def test_aggregate_weekly_reduces_bar_count(self) -> None:
        daily = _daily_trend(260)
        weekly = aggregate_weekly_bars(daily)
        self.assertGreaterEqual(len(weekly), 50)
        self.assertLess(len(weekly), len(daily) / 4 + 5)
        self.assertEqual(weekly[-1].date, daily[-1].date)

    def test_weekly_macd_computable(self) -> None:
        weekly = aggregate_weekly_bars(_daily_trend(400))
        macd = calculate_macd(weekly)
        self.assertIn(macd.state, {"零轴上多头", "金叉", "收敛", "死叉", "零轴下空头"})


class GateAndActionTests(unittest.TestCase):
    def test_bearish_weekly_never_candidate(self) -> None:
        self.assertEqual(
            decide_action(
                weekly_trend="空头",
                long_eligible=False,
                backtest_pass=True,
                ret1=0.1,
                distance_ma20=1.0,
                sentiment=60,
            ),
            "暂缓",
        )

    def test_bullish_without_gate_is_observe_not_candidate(self) -> None:
        self.assertEqual(
            decide_action(
                weekly_trend="多头",
                long_eligible=True,
                backtest_pass=False,
                ret1=0.1,
                distance_ma20=1.0,
                sentiment=60,
            ),
            "观察",
        )

    def test_bullish_with_gate_is_candidate(self) -> None:
        self.assertEqual(
            decide_action(
                weekly_trend="多头",
                long_eligible=True,
                backtest_pass=True,
                ret1=0.1,
                distance_ma20=1.0,
                sentiment=60,
            ),
            "技术候选",
        )

    def test_overbought_overrides_candidate(self) -> None:
        self.assertEqual(
            decide_action(
                weekly_trend="多头",
                long_eligible=True,
                backtest_pass=True,
                ret1=4.0,
                distance_ma20=1.0,
                sentiment=60,
            ),
            "不追涨",
        )

    def test_volume_up_price_flat_blocks_candidate(self) -> None:
        self.assertEqual(
            decide_action(
                weekly_trend="多头",
                long_eligible=True,
                backtest_pass=True,
                ret1=0.1,
                distance_ma20=1.0,
                sentiment=60,
                volume_price_bearish=True,
            ),
            "观察",
        )

    def test_volume_up_price_up_does_not_alone_create_candidate(self) -> None:
        self.assertEqual(
            decide_action(
                weekly_trend="震荡",
                long_eligible=False,
                backtest_pass=True,
                ret1=0.1,
                distance_ma20=1.0,
                sentiment=60,
                volume_price_bullish=True,
            ),
            "观察",
        )

    def test_passes_gate_requires_samples_and_positive_score(self) -> None:
        self.assertFalse(passes_gate({"n": 5, "score": 1.0, "maxDdPct": -5}))
        self.assertFalse(passes_gate({"n": 20, "score": -0.1, "maxDdPct": -5}))
        self.assertFalse(passes_gate({"n": 20, "score": 1.0, "maxDdPct": -20}))
        self.assertTrue(passes_gate({"n": 20, "score": 1.0, "maxDdPct": -5}))

    def test_macd_strict_excludes_convergence(self) -> None:
        self.assertFalse(macd_is_bullish("收敛", "strict"))
        self.assertTrue(macd_is_bullish("收敛", "loose"))

    def test_volume_price_classify(self) -> None:
        bull = volume_price_from_ratio_ret(1.3, 1.5)
        self.assertEqual("量升价增", bull.label)
        self.assertTrue(bull.bullish)
        bear = volume_price_from_ratio_ret(1.3, -0.2)
        self.assertEqual("量升价不涨", bear.label)
        self.assertTrue(bear.bearish)
        flat = volume_price_from_ratio_ret(0.9, 1.0)
        self.assertEqual("中性", flat.label)


class SelectParamsTests(unittest.TestCase):
    def test_uptrend_selects_params_and_regime(self) -> None:
        weekly = aggregate_weekly_bars(_daily_trend(500, up=True))
        result = select_best_params(weekly, sector="broad_market")
        self.assertIn("bestParams", result)
        self.assertIn(result["bestParams"]["macdMode"], {"strict", "loose"})
        self.assertIsNotNone(result["regimeNow"])
        self.assertIn(result["regimeNow"]["weeklyTrend"], {"多头", "空头", "震荡"})


class ReportGeneratorWeeklyGateTests(unittest.TestCase):
    def _context(self) -> dict:
        evidence = {
            "text": "证据正文",
            "title": "证据标题",
            "publisher": "官方机构",
            "date": "2026-07-24",
            "url": "https://example.gov.cn/evidence",
        }
        return {
            "themes": {"broad": {"policy": evidence, "fundamental": evidence}},
            "sector_theme": {"large_cap": "broad"},
        }

    def test_cached_backtest_pass_can_yield_candidate(self) -> None:
        bars = _daily_trend(120, up=True)
        shares = [
            SharePoint(
                code="510050",
                date=bar.date,
                shares=1_000_000 + i * 1000,
                source="fixture",
                fetched_at=FETCHED_AT,
            )
            for i, bar in enumerate(bars)
        ]
        seed = {
            "data_date": bars[-1].date.isoformat(),
            "rows": [
                {
                    "code": "510050",
                    "name": "上证50ETF华夏",
                    "market": "CN",
                    "sector": "large_cap",
                    "tracking_index": "上证50指数",
                }
            ],
        }
        weekly_bt = {
            "510050": {
                "passGate": True,
                "bestParams": {"fast": 10, "slow": 20, "macdMode": "strict"},
                "metrics": {"n": 20, "score": 1.2, "maxDdPct": -8},
                "regimeNow": {
                    "weekDate": bars[-1].date.isoformat(),
                    "weeklyBars": 80,
                    "macd": {"dif": 0.1, "dea": 0.05, "histogram": 0.1, "state": "零轴上多头"},
                    "ma": {
                        "fast": 10,
                        "slow": 20,
                        "ma_fast": 1.0,
                        "ma_slow": 0.9,
                        "above_fast": True,
                        "above_slow": True,
                        "fast_above_slow": True,
                        "aligned": True,
                    },
                    "macdMode": "strict",
                    "macdBullish": True,
                    "macdBearish": False,
                    "maOk": True,
                    "weeklyTrend": "多头",
                    "longEligible": True,
                },
            }
        }
        report = build_report(
            seed=seed,
            bars_by_code={"510050": bars},
            shares_by_code={"510050": shares},
            share_errors={},
            context=self._context(),
            generated_at=FETCHED_AT,
            weekly_backtest_by_code=weekly_bt,
        )
        row = report["rows"][0]
        self.assertEqual("多头", row["trend"])
        self.assertTrue(row["backtestPass"])
        self.assertEqual("技术候选", row["action"])
        self.assertIn("周线趋势", row["technical_reason"])
        self.assertEqual("dailyMaTrend" in row, True)

    def test_weekly_bear_forces_suspend_even_if_gate_true(self) -> None:
        bars = _daily_trend(120, up=False)
        shares = [
            SharePoint(
                code="510050",
                date=bar.date,
                shares=1_000_000,
                source="fixture",
                fetched_at=FETCHED_AT,
            )
            for bar in bars
        ]
        seed = {
            "data_date": bars[-1].date.isoformat(),
            "rows": [
                {
                    "code": "510050",
                    "name": "上证50ETF华夏",
                    "market": "CN",
                    "sector": "large_cap",
                    "tracking_index": "上证50指数",
                }
            ],
        }
        weekly_bt = {
            "510050": {
                "passGate": True,
                "bestParams": {"fast": 10, "slow": 20, "macdMode": "strict"},
                "metrics": {"n": 20, "score": 1.2, "maxDdPct": -8},
                "regimeNow": {
                    "weekDate": bars[-1].date.isoformat(),
                    "weeklyBars": 80,
                    "macd": {"dif": -0.1, "dea": -0.05, "histogram": -0.1, "state": "零轴下空头"},
                    "ma": {
                        "fast": 10,
                        "slow": 20,
                        "ma_fast": 1.0,
                        "ma_slow": 1.1,
                        "above_fast": False,
                        "above_slow": False,
                        "fast_above_slow": False,
                        "aligned": False,
                    },
                    "macdMode": "strict",
                    "macdBullish": False,
                    "macdBearish": True,
                    "maOk": False,
                    "weeklyTrend": "空头",
                    "longEligible": False,
                },
            }
        }
        report = build_report(
            seed=seed,
            bars_by_code={"510050": bars},
            shares_by_code={"510050": shares},
            share_errors={},
            context=self._context(),
            generated_at=FETCHED_AT,
            weekly_backtest_by_code=weekly_bt,
        )
        self.assertEqual("暂缓", report["rows"][0]["action"])


if __name__ == "__main__":
    unittest.main()
