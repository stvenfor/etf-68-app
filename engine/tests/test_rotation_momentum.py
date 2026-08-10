from __future__ import annotations

import math
import unittest

from src.rotation.filters import build_rankings, is_limit_up, passes_condition_filters
from src.rotation.momentum import compute_momentum, simple_momentum, slope_momentum


class MomentumTests(unittest.TestCase):
    def test_simple_momentum(self) -> None:
        closes = [100.0] * 20 + [110.0]
        m = simple_momentum(closes, 20)
        assert m is not None
        self.assertAlmostEqual(m.score, 0.10, places=6)

    def test_slope_score_matches_ann_times_r2(self) -> None:
        # steadily rising series
        closes = [100 * (1.01**i) for i in range(30)]
        m = slope_momentum(closes, 20)
        assert m is not None
        assert m.annualized_return is not None
        assert m.r_squared is not None
        self.assertAlmostEqual(m.score, (m.annualized_return / 100.0) * m.r_squared, places=6)
        self.assertGreater(m.score, 0)

    def test_weighted_slope_runs(self) -> None:
        closes = [100 + i for i in range(40)]
        m = compute_momentum(method="weighted_slope", window=20, closes=closes)
        assert m is not None
        self.assertTrue(math.isfinite(m.score))

    def test_rsrs_runs(self) -> None:
        n = 80
        closes = [100 + 0.2 * i for i in range(n)]
        highs = [c + 1 for c in closes]
        lows = [c - 1 for c in closes]
        m = compute_momentum(
            method="rsrs", window=18, closes=closes, highs=highs, lows=lows
        )
        assert m is not None
        self.assertTrue(math.isfinite(m.score))


class FilterTests(unittest.TestCase):
    def test_limit_up(self) -> None:
        self.assertTrue(is_limit_up(110.0, 100.0))
        self.assertFalse(is_limit_up(105.0, 100.0))

    def test_condition_ma(self) -> None:
        closes = [10.0] * 60 + [20.0]
        self.assertTrue(
            passes_condition_filters(
                closes,
                price_above_ma=True,
                ma_period=60,
                ma_bull=False,
                ma_fast=20,
                ma_slow=60,
            )
        )

    def test_secondary_momentum_filter(self) -> None:
        # code A strong short-term but weak long; B moderate both
        closes_a = [100.0] * 70 + [100.0 + i for i in range(1, 21)]  # recent spike
        closes_b = [100 + 0.3 * i for i in range(90)]
        rankings = build_rankings(
            pool=["AAAAAA", "BBBBBB"],
            names={"AAAAAA": "A", "BBBBBB": "B"},
            closes_by_code={"AAAAAA": closes_a, "BBBBBB": closes_b},
            highs_by_code={"AAAAAA": closes_a, "BBBBBB": closes_b},
            lows_by_code={"AAAAAA": closes_a, "BBBBBB": closes_b},
            method="simple",
            window=20,
            secondary_enabled=True,
            secondary_method="simple",
            secondary_window=60,
            secondary_min=0.05,
            score_min=None,
            score_max=None,
            skip_limit_up=False,
            skip_limit_down=False,
            price_above_ma=False,
            ma_period=60,
            ma_bull=False,
            ma_fast=20,
            ma_slow=60,
            market_timing_enabled=False,
            benchmark_code=None,
        )
        codes = [r.code for r in rankings]
        self.assertIn("BBBBBB", codes)


if __name__ == "__main__":
    unittest.main()
