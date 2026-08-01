"""Tests for 今日债市收评 (bond_review)."""

from __future__ import annotations

import json
import unittest

from src.bond_review import (
    build_bond_review,
    build_pure_bond_estimates,
    classify_fund_bucket,
    eggs_from_nav_ret_pct,
    eggs_from_yield_delta_bp,
)


class BondReviewTests(unittest.TestCase):
    def test_yield_down_is_gain_eggs(self) -> None:
        out = eggs_from_yield_delta_bp(-3.2)
        self.assertEqual(out["side"], "gain")
        self.assertEqual(out["tone"], "up")
        self.assertIn("收", out["label"])
        self.assertEqual(out["eggs"], 3)

    def test_yield_up_is_loss_eggs(self) -> None:
        out = eggs_from_yield_delta_bp(2.0)
        self.assertEqual(out["side"], "loss")
        self.assertEqual(out["tone"], "dn")
        self.assertIn("丢", out["label"])

    def test_nav_up_is_gain_eggs(self) -> None:
        out = eggs_from_nav_ret_pct(0.05)  # +0.05% → 5 蛋
        self.assertEqual(out["side"], "gain")
        self.assertEqual(out["eggs"], 5)
        self.assertIn("收", out["label"])

    def test_nav_down_is_loss_eggs(self) -> None:
        out = eggs_from_nav_ret_pct(-0.03)
        self.assertEqual(out["side"], "loss")
        self.assertEqual(out["eggs"], 3)
        self.assertIn("丢", out["label"])

    def test_classify_matches_sample_buckets(self) -> None:
        self.assertEqual(classify_fund_bucket(20.3, 116.5, 0.0), "ultra_long")
        self.assertEqual(classify_fund_bucket(8.8, 134.1, 0.0), "mid_long")
        self.assertEqual(classify_fund_bucket(1.5, 21.3, 83.3), "credit")
        self.assertEqual(classify_fund_bucket(5.4, 60.2, 32.1), "mid_short")

    def test_pure_bond_estimates_match_sample_labels(self) -> None:
        rows = {r["name"]: r for r in build_pure_bond_estimates()}
        self.assertEqual(rows["方正富邦鸿远C"]["estimate"]["label"], "收0-10个")
        self.assertEqual(rows["华泰保兴安悦C"]["estimate"]["side"], "gain")
        self.assertEqual(rows["平安5-10政金债A"]["estimate"]["label"], "丢0-10个")
        self.assertEqual(rows["南方7-10年国开债E"]["estimate"]["side"], "loss")
        self.assertEqual(rows["中欧兴悦C"]["estimate"]["label"], "收0个左右")
        self.assertEqual(rows["易方达中债新综指"]["estimate"]["label"], "收0个左右")
        self.assertEqual(len(rows), 9)

    def test_implied_uses_duration_times_bp(self) -> None:
        rows = build_pure_bond_estimates(
            yield_deltas={"y2": -1.0, "y5": -1.0, "y10": 2.0, "y30": -3.0},
            credit_delta_bp=0.0,
        )
        by_name = {r["name"]: r for r in rows}
        # 超长：-20.3 * (-3) * 1.165 ≈ +71 → 收 71 蛋
        ultra = by_name["方正富邦鸿远C"]["implied"]
        self.assertEqual(ultra["side"], "gain")
        self.assertGreaterEqual(ultra["eggs"], 70)
        # 中长：-8.8 * 2 * 1.341 ≈ -23.6 → 丢 24 蛋
        mid = by_name["平安5-10政金债A"]["implied"]
        self.assertEqual(mid["side"], "loss")
        self.assertGreaterEqual(mid["eggs"], 20)

    def test_build_bond_review_with_fake_yields(self) -> None:
        yields_payload = {
            "ok": True,
            "fetchedAt": "2026-07-28T15:00:00+08:00",
            "series": [
                {"date": "2026-07-25", "y2": 1.40, "y5": 1.60, "y10": 1.70, "y30": 1.90},
                {"date": "2026-07-28", "y2": 1.38, "y5": 1.58, "y10": 1.67, "y30": 1.87},
            ],
        }
        rows = [
            {"code": "511090", "name": "30年国债ETF鹏扬", "ret1": 0.12},
            {"code": "511190", "name": "信用债ETF海富通", "ret1": -0.02},
        ]
        card = build_bond_review(as_of="2026-07-28", rows=rows, yields_payload=yields_payload)
        self.assertTrue(card["ok"])
        buckets = {b["key"]: b for b in card["rate"]["buckets"]}
        self.assertEqual(buckets["ultra_long"]["forecast"], "收0-10个")
        self.assertEqual(buckets["mid_long"]["forecast"], "丢0-10个")
        self.assertEqual(buckets["mid_short"]["forecast"], "收0个左右")
        # 30Y 1.90→1.87 = -3bp → 收蛋
        self.assertEqual(buckets["ultra_long"]["move"]["side"], "gain")
        self.assertIn("收", buckets["ultra_long"]["move"]["label"])
        # 10Y 1.70→1.67 = -3bp
        self.assertEqual(buckets["mid_long"]["move"]["side"], "gain")
        # 2Y 1.40→1.38 = -2bp
        self.assertEqual(buckets["mid_short"]["move"]["side"], "gain")
        # credit NAV -0.02% → 丢 2 蛋
        self.assertEqual(card["credit"]["forecast"], "收0个左右")
        self.assertEqual(card["credit"]["move"]["side"], "loss")
        self.assertIn("丢", card["credit"]["move"]["label"])
        self.assertIn("利率债", card["summary"])
        self.assertEqual(len(card["pureBonds"]), 9)
        self.assertEqual(card["pureBonds"][0]["estimate"]["label"], "收0-10个")

    def test_fetch_parser_via_fake_fetch(self) -> None:
        sample = {
            "result": {
                "pages": 1,
                "data": [
                    {
                        "SOLAR_DATE": "2026-07-28",
                        "EMM00588704": 1.38,
                        "EMM00166462": 1.58,
                        "EMM00166466": 1.67,
                        "EMM00166469": 1.87,
                    },
                    {
                        "SOLAR_DATE": "2026-07-25",
                        "EMM00588704": 1.40,
                        "EMM00166462": 1.60,
                        "EMM00166466": 1.70,
                        "EMM00166469": 1.90,
                    },
                ],
            }
        }

        def fake_fetch(url: str) -> str:
            self.assertIn("RPTA_WEB_TREASURYYIELD", url)
            return json.dumps(sample)

        card = build_bond_review(
            as_of="2026-07-28",
            rows=[{"code": "511190", "name": "信用债ETF", "ret1": 0.01}],
            fetch=fake_fetch,
        )
        self.assertTrue(card["ok"])
        self.assertEqual(card["yields"]["y10"]["level"], 1.67)
        self.assertEqual(card["credit"]["move"]["side"], "gain")


if __name__ == "__main__":
    unittest.main()
