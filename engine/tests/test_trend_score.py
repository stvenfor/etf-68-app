"""Tests for multi-dimension trend score card."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from src.trend_score import (  # noqa: E402
    build_advice,
    build_trend_score_card,
    rating_for,
    score_flow,
    score_ma_axis,
    score_macd_momentum,
    score_valuation_proxy,
)


class TrendScoreTests(unittest.TestCase):
    def test_ma_axis_corners(self) -> None:
        self.assertEqual(90.0, score_ma_axis(above=True, rising=True))
        self.assertEqual(15.0, score_ma_axis(above=False, rising=False))
        self.assertEqual(72.0, score_ma_axis(above=True, rising=None))

    def test_macd_histogram_tilts_score(self) -> None:
        up = score_macd_momentum(state="金叉", histogram=0.5)
        down = score_macd_momentum(state="金叉", histogram=-0.5)
        self.assertGreater(up, down)

    def test_flow_and_valuation(self) -> None:
        self.assertGreater(
            score_flow(flow_5d_cny=1e7, aum_cny=1e9) or 0,
            score_flow(flow_5d_cny=-1e7, aum_cny=1e9) or 0,
        )
        cheap = score_valuation_proxy(rsi14=30.0, distance_ma20_pct=-3.0)
        rich = score_valuation_proxy(rsi14=75.0, distance_ma20_pct=8.0)
        self.assertIsNotNone(cheap)
        self.assertIsNotNone(rich)
        self.assertGreater(cheap or 0, rich or 0)

    def test_rating_bands(self) -> None:
        self.assertEqual("强烈看涨", rating_for(85))
        self.assertEqual("看涨", rating_for(70))
        self.assertEqual("中性", rating_for(50))
        self.assertEqual("看跌", rating_for(30))
        self.assertEqual("强烈看跌", rating_for(10))

    def test_advice_pullback_layout(self) -> None:
        text = build_advice(
            {"weekly": 40, "monthly": 75, "momentum": 55, "flow": 50, "valuation": 60}
        )
        self.assertIn("逢低布局", text)

    def test_build_card_from_rows(self) -> None:
        rows = [
            {
                "close": 1.2,
                "ma20": 1.0,
                "ma60": 0.9,
                "ma20_rising": True,
                "ma60_rising": True,
                "macd": {"state": "金叉", "histogram": 0.2},
                "flows": {"5": {"value_cny": 5_000_000}},
                "aum_estimate_cny": 1_000_000_000,
                "rsi14": 45.0,
                "distance_ma20_pct": 2.0,
            },
            {
                "close": 0.8,
                "ma20": 1.0,
                "ma60": 1.1,
                "ma20_rising": False,
                "ma60_rising": False,
                "macd": {"state": "死叉", "histogram": -0.2},
                "flows": {"5": {"value_cny": -5_000_000}},
                "aum_estimate_cny": 1_000_000_000,
                "rsi14": 70.0,
                "distance_ma20_pct": 6.0,
            },
        ]
        card = build_trend_score_card(rows)
        self.assertIn(card["rating"], {"强烈看涨", "看涨", "中性", "看跌", "强烈看跌"})
        self.assertGreaterEqual(card["total"], 0)
        self.assertLessEqual(card["total"], 100)
        self.assertEqual(5, len(card["dimensions"]))
        self.assertIn("pe_pb_percentile", card["missing"])
        self.assertTrue(card["advice"])


if __name__ == "__main__":
    unittest.main()
