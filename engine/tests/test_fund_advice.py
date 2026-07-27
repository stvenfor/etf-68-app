"""Unit tests for open-end fund「建议」labels."""

from __future__ import annotations

import unittest

from src.fund_advice import (
    ADVICE_FRIENDLY,
    ADVICE_HOLD,
    ADVICE_NEUTRAL,
    ADVICE_NO_CHASE,
    ADVICE_WATCH,
    decide_fund_advice,
    estimate_premium_pct,
)


class FundAdviceTests(unittest.TestCase):
    def test_premium(self) -> None:
        self.assertAlmostEqual(estimate_premium_pct(1.02, 1.0) or 0, 2.0)
        self.assertIsNone(estimate_premium_pct(None, 1.0))

    def test_hold_on_error(self) -> None:
        out = decide_fund_advice({"category": "equity", "error": "missing_nav"})
        self.assertEqual(out["advice"], ADVICE_HOLD)

    def test_no_chase_on_hot_move(self) -> None:
        out = decide_fund_advice(
            {
                "category": "equity",
                "categoryLabel": "股票型",
                "nav": 1.0,
                "estimateNav": 1.01,
                "estimateChangePct": 2.5,
                "dayChangePct": 0.5,
            }
        )
        self.assertEqual(out["advice"], ADVICE_NO_CHASE)
        self.assertIn("过热", out["adviceDetail"])

    def test_no_chase_on_premium(self) -> None:
        out = decide_fund_advice(
            {
                "category": "hybrid",
                "nav": 1.0,
                "estimateNav": 1.02,
                "estimateChangePct": 0.3,
                "dayChangePct": 0.2,
            }
        )
        self.assertEqual(out["advice"], ADVICE_NO_CHASE)
        self.assertIn("溢价", out["adviceDetail"])

    def test_friendly_on_soft_dip(self) -> None:
        out = decide_fund_advice(
            {
                "category": "equity",
                "nav": 1.0,
                "estimateNav": 0.99,
                "estimateChangePct": -1.5,
                "dayChangePct": -0.2,
            }
        )
        self.assertEqual(out["advice"], ADVICE_FRIENDLY)

    def test_watch_mild_positive(self) -> None:
        out = decide_fund_advice(
            {
                "category": "equity",
                "nav": 1.0,
                "estimateNav": 1.004,
                "estimateChangePct": 0.4,
                "dayChangePct": 0.3,
            }
        )
        self.assertEqual(out["advice"], ADVICE_WATCH)

    def test_neutral_default(self) -> None:
        out = decide_fund_advice(
            {
                "category": "equity",
                "nav": 1.0,
                "estimateNav": 1.0,
                "estimateChangePct": 0.0,
                "dayChangePct": 0.0,
            }
        )
        self.assertEqual(out["advice"], ADVICE_NEUTRAL)

    def test_bond_mild_is_watch(self) -> None:
        out = decide_fund_advice(
            {
                "category": "bond",
                "nav": 1.0,
                "estimateNav": 1.001,
                "estimateChangePct": 0.05,
                "dayChangePct": 0.02,
            }
        )
        self.assertEqual(out["advice"], ADVICE_WATCH)

    def test_bond_overheat_tighter(self) -> None:
        out = decide_fund_advice(
            {
                "category": "bond",
                "nav": 1.0,
                "estimateNav": 1.003,
                "estimateChangePct": 0.5,
                "dayChangePct": 0.1,
            }
        )
        self.assertEqual(out["advice"], ADVICE_NO_CHASE)


if __name__ == "__main__":
    unittest.main()
