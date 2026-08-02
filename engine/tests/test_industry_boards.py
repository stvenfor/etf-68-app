from __future__ import annotations

import json
import unittest

from src.industry_boards import (
    build_industry_sector_ranks,
    dedupe_hierarchical_boards,
    industry_stem,
    top_bottom_industry_boards,
)


class IndustryBoardsTests(unittest.TestCase):
    def test_stem_and_dedupe(self) -> None:
        self.assertEqual("银行", industry_stem("银行Ⅱ"))
        self.assertEqual("国有大型银行", industry_stem("国有大型银行Ⅲ"))
        rows = [
            {"code": "BK0475X", "name": "银行Ⅱ", "changePct": 1.1},
            {"code": "BK0475", "name": "银行", "changePct": 1.23},
            {"code": "BK0447", "name": "证券", "changePct": -0.5},
            {"code": "BKXXXX", "name": "国有大型银行Ⅲ", "changePct": -1.67},
        ]
        out = dedupe_hierarchical_boards(rows)
        names = [r["name"] for r in out]
        self.assertEqual(names.count("银行"), 1)
        self.assertNotIn("银行Ⅱ", names)
        self.assertIn("证券", names)
        self.assertIn("国有大型银行", names)
        self.assertNotIn("国有大型银行Ⅲ", names)
        bank = next(r for r in out if r["name"] == "银行")
        self.assertEqual(1.23, bank["changePct"])

    def test_top_bottom(self) -> None:
        boards = [
            {"code": "1", "name": "传媒", "changePct": 5.0},
            {"code": "2", "name": "软件", "changePct": 4.0},
            {"code": "3", "name": "煤炭", "changePct": -1.0},
            {"code": "4", "name": "银行", "changePct": -2.0},
            {"code": "5", "name": "机器人", "changePct": 3.0},
        ]
        tb = top_bottom_industry_boards(boards, 3)
        self.assertEqual(["传媒", "软件", "机器人"], [x["sector"] for x in tb["gainers"]])
        self.assertEqual(["银行", "煤炭"], [x["sector"] for x in tb["losers"][:2]])
        self.assertTrue(tb["ok"])
        self.assertEqual("eastmoney_industry", tb["source"])

    def test_fetch_with_fake(self) -> None:
        page1 = {
            "data": {
                "diff": [
                    {"f12": "BK0480", "f14": "传媒", "f2": 100, "f3": 6.5},
                    {"f12": "BK0737", "f14": "软件开发", "f2": 100, "f3": 5.1},
                    {"f12": "BK0475", "f14": "银行", "f2": 100, "f3": -1.2},
                    {"f12": "BK0475B", "f14": "银行Ⅱ", "f2": 100, "f3": -1.2},
                ]
                + [
                    {"f12": f"BK{i:04d}", "f14": f"板块{i}", "f2": 1, "f3": 0.01 * i}
                    for i in range(50)
                ]
            }
        }
        page2 = {"data": {"diff": []}}

        def fake_fetch(url: str) -> str:
            if "pn=1" in url:
                return json.dumps(page1)
            return json.dumps(page2)

        ranks = build_industry_sector_ranks(n=2, fetch=fake_fetch)
        self.assertTrue(ranks["ok"])
        self.assertEqual("传媒", ranks["gainers"][0]["sector"])
        self.assertEqual(6.5, ranks["gainers"][0]["avgRet1"])
        # 银行Ⅱ collapsed into 银行
        loser_names = [x["sector"] for x in ranks["losers"]]
        self.assertIn("银行", loser_names)
        self.assertNotIn("银行Ⅱ", loser_names)


if __name__ == "__main__":
    unittest.main()
