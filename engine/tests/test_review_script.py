from __future__ import annotations

import unittest

from src.review_script import build_review_script, collect_news, top_bottom_sectors, sector_averages


class ReviewScriptTests(unittest.TestCase):
    def test_sectors_and_news_dedupe(self) -> None:
        rows = [
            {"sector": "A", "ret1": 2.0, "action": "观察", "name": "a1", "code": "1"},
            {"sector": "A", "ret1": 0.0, "action": "观察", "name": "a2", "code": "2"},
            {"sector": "B", "ret1": -1.0, "action": "观察", "name": "b1", "code": "3"},
            {"sector": "C", "ret1": 3.0, "action": "技术候选", "name": "c1", "code": "4", "flow1": 1.2, "flow5": 2.0},
            {"sector": "D", "ret1": -2.5, "action": "观察", "name": "d1", "code": "5"},
        ]
        avgs = sector_averages(rows)
        tb = top_bottom_sectors(avgs, 2)
        self.assertEqual("C", tb["gainers"][0]["sector"])
        self.assertEqual("D", tb["losers"][0]["sector"])

        bundle = {
            "dataDate": "2026-07-24",
            "breadthPct": 40.0,
            "rows": rows,
            "citicMonthly": {
                "months": [
                    {
                        "days": [
                            {"date": "2026-07-23", "citicTotal": 100, "stance": "净加多"},
                            {"date": "2026-07-24", "citicTotal": 40, "stance": "净加多"},
                        ]
                    }
                ]
            },
            "impactEvents": {
                "rows": [
                    {
                        "positiveEvents": [
                            {"sourceKey": "x", "title": "利好甲", "date": "2026-07-01"},
                            {"sourceKey": "x", "title": "利好甲", "date": "2026-07-20"},
                        ],
                        "negativeEvents": [
                            {"sourceKey": "y", "title": "利空乙", "date": "2026-07-10"},
                            {"sourceKey": "z", "title": "利空乙", "date": "2026-07-11"},
                        ],
                    }
                ]
            },
        }
        news = collect_news(bundle, 5)
        self.assertEqual(1, len(news["positive"]))
        self.assertEqual("2026-07-20", news["positive"][0]["date"])
        self.assertEqual(1, len(news["negative"]))  # same title deduped

        script = build_review_script(bundle)
        self.assertTrue(script["ok"])
        self.assertEqual(6, len(script["chapters"]))
        self.assertEqual(-60, script["citic"]["delta"])
        self.assertNotIn("波动领先", script["fullNarration"])
        self.assertTrue(all(c["id"] != "movers" for c in script["chapters"]))
        self.assertIn("技术候选资金", script["fullNarration"])
        self.assertIn("其它机构多空单", script["fullNarration"])
        self.assertIn("当日多空单总计", script["fullNarration"])


if __name__ == "__main__":
    unittest.main()
