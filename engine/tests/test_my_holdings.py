"""Unit tests for my_holdings + position_advice (no network)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.my_holdings import HOLDINGS_SEED, build_my_holdings, seed_universe, write_my_holdings
from src.position_advice import (
    ADVICE_ADD,
    ADVICE_HOLD,
    ADVICE_KEEP,
    ADVICE_REDEEM,
    ADVICE_TRIM,
    decide_position_advice,
)


class SeedTest(unittest.TestCase):
    def test_seed_no_money_or_feeder(self) -> None:
        for row in HOLDINGS_SEED:
            name = str(row["name"])
            self.assertNotIn("货币", name)
            self.assertNotIn("联接", name)
            self.assertNotIn("同业存单", name)

    def test_seed_unique_codes(self) -> None:
        codes = [str(r["code"]).zfill(6) for r in HOLDINGS_SEED]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertGreaterEqual(len(codes), 20)

    def test_seed_universe_ranks(self) -> None:
        rows = seed_universe()
        self.assertEqual(len(rows), len(HOLDINGS_SEED))
        bonds = [r for r in rows if r["category"] == "bond"]
        self.assertEqual(bonds[0]["rankInCategory"], 1)
        self.assertIn("固收+", bonds[0]["themes"])


class PositionAdviceTest(unittest.TestCase):
    def test_missing_nav_hold(self) -> None:
        out = decide_position_advice({"category": "hybrid", "error": "x"})
        self.assertEqual(out["advice"], ADVICE_HOLD)

    def test_soft_dip_add(self) -> None:
        out = decide_position_advice(
            {
                "category": "hybrid",
                "nav": 1.0,
                "estimateNav": 0.99,
                "estimateChangePct": -1.2,
                "themes": ["灵活配置"],
            }
        )
        self.assertEqual(out["advice"], ADVICE_ADD)

    def test_overheat_trim(self) -> None:
        out = decide_position_advice(
            {
                "category": "bond",
                "nav": 1.0,
                "estimateNav": 1.001,
                "estimateChangePct": 0.55,
                "themes": ["固收+"],
            }
        )
        self.assertEqual(out["advice"], ADVICE_TRIM)

    def test_extreme_hot_redeem(self) -> None:
        out = decide_position_advice(
            {
                "category": "equity",
                "nav": 1.0,
                "estimateNav": 1.03,
                "estimateChangePct": 3.5,
                "themes": ["白酒", "消费"],
            }
        )
        self.assertEqual(out["advice"], ADVICE_REDEEM)

    def test_mild_keep(self) -> None:
        out = decide_position_advice(
            {
                "category": "hybrid",
                "nav": 1.0,
                "estimateNav": 1.001,
                "estimateChangePct": 0.2,
                "themes": ["股债平衡"],
            }
        )
        self.assertEqual(out["advice"], ADVICE_KEEP)


class BuildMyHoldingsTest(unittest.TestCase):
    def test_build_with_fake_fetch(self) -> None:
        def fake_fetch(url: str) -> str:
            if "pingzhongdata" in url:
                code = url.rsplit("/", 1)[-1].replace(".js", "")
                # minimal pingzhong stub
                return (
                    f'var fS_name = "测试{code}";'
                    "var Data_netWorthTrend = "
                    '[{"x":1721779200000,"y":1.2345,"equityReturn":0.12}];'
                )
            if "hq.sinajs.cn" in url or "sinajs.cn" in url:
                # return empty → fall back to published as estimate
                return ""
            return ""

        result = build_my_holdings(fetch=fake_fetch)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["rows"]), len(HOLDINGS_SEED))
        self.assertIn("继续持有", result["adviceFramework"]["labels"])
        row0 = result["rows"][0]
        self.assertAlmostEqual(row0["nav"], 1.2345)
        self.assertTrue(row0.get("themes"))

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "my-holdings.json"
            write_my_holdings(path, result)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(loaded["rows"]), len(HOLDINGS_SEED))


if __name__ == "__main__":
    unittest.main()
