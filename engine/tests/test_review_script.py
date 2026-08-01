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
            "dataDate": "2099-01-15",
            "breadthPct": 40.0,
            "rows": rows,
            "citicMonthly": {
                "months": [
                    {
                        "label": "2099-01",
                        "month": 1,
                        "monthNet": 140,
                        "days": [
                            {"date": "2099-01-14", "citicTotal": 100, "stance": "净加多"},
                            {
                                "date": "2099-01-15",
                                "citicTotal": 40,
                                "stance": "净加多",
                                "otherTotal": -80,
                                "grandTotal": -40,
                            },
                        ],
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

        script = build_review_script(bundle, fetch_market=False)
        self.assertTrue(script["ok"])
        self.assertEqual(6, len(script["chapters"]))
        self.assertEqual(-60, script["citic"]["delta"])
        self.assertNotIn("波动领先", script["fullNarration"])
        self.assertTrue(all(c["id"] != "movers" for c in script["chapters"]))
        self.assertIn("技术候选", script["fullNarration"])
        self.assertNotIn("技术候选资金", script["fullNarration"])
        self.assertEqual("技术候选", next(c["title"] for c in script["chapters"] if c["id"] == "candidates"))
        self.assertIn("其它机构净加空80手", script["fullNarration"])
        self.assertIn("总体净加空40手", script["fullNarration"])
        self.assertIn("持仓量变动", script["fullNarration"])
        self.assertEqual("持仓量变动", next(c["title"] for c in script["chapters"] if c["id"] == "citic"))
        # 互斥口播：只出现净加多或净加空或持平，不同时念两边
        self.assertIn("中信净加多40手", script["fullNarration"])
        self.assertNotIn("中信净加空0手", script["fullNarration"])
        self.assertNotIn("净加多40手，净加空", script["fullNarration"])
        self.assertIn("本月总体净多140手", script["fullNarration"])
        self.assertNotIn("中信多空。", script["fullNarration"])
        self.assertNotIn("当日多空单总计", script["fullNarration"])
        # 实质消息口播不截断标题
        self.assertIn("利好甲", script["fullNarration"])
        self.assertIn("marketBoard", script)

    def test_collect_news_prefers_recent_dates(self) -> None:
        bundle = {
            "dataDate": "2026-07-27",
            "impactEvents": {
                "rows": [
                    {
                        "positiveEvents": [
                            {"sourceKey": "old", "title": "旧利好", "date": "2026-07-01"},
                            {"sourceKey": "live_new", "title": "新利好甲", "date": "2026-07-28"},
                            {"sourceKey": "live_new2", "title": "新利好乙", "date": "2026-07-27"},
                        ],
                        "negativeEvents": [
                            {"sourceKey": "oldn", "title": "旧利空", "date": "2026-06-01"},
                            {"sourceKey": "live_n", "title": "新利空", "date": "2026-07-28"},
                        ],
                    }
                ]
            },
        }
        news = collect_news(bundle, 5)
        self.assertEqual("新利好甲", news["positive"][0]["title"])
        self.assertEqual("2026-07-28", news["positive"][0]["date"])
        self.assertEqual("新利空", news["negative"][0]["title"])
        titles = [e["title"] for e in news["positive"]]
        self.assertNotIn("旧利好", titles[:2])


if __name__ == "__main__":
    unittest.main()
