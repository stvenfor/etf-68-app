from __future__ import annotations

import unittest

from src.review_script import build_review_script, collect_news, top_bottom_sectors, sector_averages


class ReviewScriptTests(unittest.TestCase):
    def test_sectors_and_exact_day_chapters(self) -> None:
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
                            {"sourceKey": "x", "title": "利好甲", "date": "2099-01-14"},
                            {"sourceKey": "x2", "title": "利好当日", "date": "2099-01-15"},
                        ],
                        "negativeEvents": [
                            {"sourceKey": "y", "title": "利空乙", "date": "2099-01-10"},
                            {"sourceKey": "z", "title": "利空当日", "date": "2099-01-15"},
                        ],
                    }
                ]
            },
        }
        news = collect_news(bundle, 5)
        self.assertEqual(1, len(news["positive"]))
        self.assertEqual("利好当日", news["positive"][0]["title"])
        self.assertEqual("2099-01-15", news["positive"][0]["date"])
        self.assertEqual(1, len(news["negative"]))
        self.assertEqual("利空当日", news["negative"][0]["title"])

        industry_sectors = {
            "ok": True,
            "source": "eastmoney_industry",
            "gainers": [
                {"sector": "传媒", "avgRet1": 6.5, "count": 1, "code": "BK0480"},
                {"sector": "软件开发", "avgRet1": 5.1, "count": 1, "code": "BK0737"},
                {"sector": "互联网服务", "avgRet1": 4.2, "count": 1, "code": "BK0447"},
            ],
            "losers": [
                {"sector": "煤炭行业", "avgRet1": -2.1, "count": 1, "code": "BK0437"},
                {"sector": "银行", "avgRet1": -1.2, "count": 1, "code": "BK0475"},
                {"sector": "保险", "avgRet1": -0.8, "count": 1, "code": "BK0474"},
            ],
        }
        script = build_review_script(
            bundle,
            fetch_market=False,
            industry_sectors=industry_sectors,
        )
        self.assertTrue(script["ok"])
        chapter_ids = [c["id"] for c in script["chapters"]]
        self.assertEqual(
            ["open", "sectors", "citic", "news", "candidates", "close"],
            chapter_ids,
        )
        self.assertIn("传媒+6.50%", script["fullNarration"])
        self.assertIn("煤炭行业-2.10%", script["fullNarration"])
        self.assertEqual("eastmoney_industry", script["sectors"].get("source"))
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
        self.assertNotIn("暂无当日持仓数据", script["fullNarration"])
        self.assertNotIn("利好暂无", script["fullNarration"])
        self.assertNotIn("利空暂无", script["fullNarration"])
        # 实质消息口播不截断标题；非复盘日标题不得入镜
        self.assertIn("利好当日", script["fullNarration"])
        self.assertIn("利空当日", script["fullNarration"])
        self.assertNotIn("利好甲", script["fullNarration"])
        self.assertNotIn("利空乙", script["fullNarration"])
        self.assertIn("marketBoard", script)
        # kickers renumbered sequentially
        self.assertEqual("01 · 日期", script["chapters"][0]["kicker"])
        self.assertEqual("03 · 持仓", script["chapters"][2]["kicker"])
        self.assertEqual("06 · 结束", script["chapters"][-1]["kicker"])

    def test_citic_omitted_without_exact_day(self) -> None:
        bundle = {
            "dataDate": "2099-01-15",
            "breadthPct": 40.0,
            "rows": [{"sector": "A", "ret1": 1.0, "action": "观察", "name": "a", "code": "1"}],
            "citicMonthly": {
                "months": [
                    {
                        "label": "2099-01",
                        "monthNet": 100,
                        "days": [
                            {
                                "date": "2099-01-14",
                                "citicTotal": 100,
                                "otherTotal": -20,
                                "grandTotal": 80,
                                "stance": "净加多",
                            },
                        ],
                    }
                ]
            },
            "impactEvents": {"rows": []},
        }
        script = build_review_script(bundle, fetch_market=False)
        self.assertFalse(script["citic"].get("ok"))
        self.assertEqual("citic_day_missing", script["citic"].get("error"))
        self.assertTrue(all(c["id"] != "citic" for c in script["chapters"]))
        self.assertNotIn("持仓量变动", script["fullNarration"])
        self.assertNotIn("暂无当日持仓数据", script["fullNarration"])

    def test_citic_omitted_when_incomplete(self) -> None:
        bundle = {
            "dataDate": "2099-01-15",
            "rows": [],
            "citicMonthly": {
                "months": [
                    {
                        "label": "2099-01",
                        "days": [{"date": "2099-01-15", "citicTotal": 40}],
                    }
                ]
            },
            "impactEvents": {"rows": []},
        }
        script = build_review_script(bundle, fetch_market=False)
        self.assertFalse(script["citic"].get("ok"))
        self.assertEqual("citic_day_incomplete", script["citic"].get("error"))
        self.assertTrue(all(c["id"] != "citic" for c in script["chapters"]))

    def test_collect_news_exact_data_date_only(self) -> None:
        bundle = {
            "dataDate": "2026-07-27",
            "impactEvents": {
                "rows": [
                    {
                        "positiveEvents": [
                            {"sourceKey": "old", "title": "旧利好", "date": "2026-07-01"},
                            {"sourceKey": "live_new", "title": "次日利好", "date": "2026-07-28"},
                            {"sourceKey": "live_new2", "title": "当日利好", "date": "2026-07-27"},
                        ],
                        "negativeEvents": [
                            {"sourceKey": "oldn", "title": "旧利空", "date": "2026-06-01"},
                            {"sourceKey": "live_n", "title": "次日利空", "date": "2026-07-28"},
                        ],
                    }
                ]
            },
        }
        news = collect_news(bundle, 5)
        self.assertEqual(["当日利好"], [e["title"] for e in news["positive"]])
        self.assertEqual([], news["negative"])

        script = build_review_script(
            {
                **bundle,
                "breadthPct": 10.0,
                "rows": [],
                "citicMonthly": {"months": []},
            },
            fetch_market=False,
        )
        self.assertIn("news", [c["id"] for c in script["chapters"]])
        self.assertIn("利好：当日利好", script["fullNarration"])
        self.assertNotIn("利空", script["fullNarration"])
        self.assertNotIn("利好暂无", script["fullNarration"])
        self.assertNotIn("利空暂无", script["fullNarration"])
        self.assertNotIn("次日利好", script["fullNarration"])

    def test_news_chapter_omitted_when_empty(self) -> None:
        bundle = {
            "dataDate": "2026-07-27",
            "breadthPct": 10.0,
            "rows": [],
            "citicMonthly": {"months": []},
            "impactEvents": {
                "rows": [
                    {
                        "positiveEvents": [
                            {"sourceKey": "old", "title": "旧利好", "date": "2026-07-01"},
                        ],
                        "negativeEvents": [],
                    }
                ]
            },
        }
        script = build_review_script(bundle, fetch_market=False)
        self.assertEqual([], script["news"]["positive"])
        self.assertEqual([], script["news"]["negative"])
        self.assertTrue(all(c["id"] != "news" for c in script["chapters"]))
        self.assertNotIn("实质消息", script["fullNarration"])
        # open + sectors + candidates + close
        self.assertEqual(
            ["open", "sectors", "candidates", "close"],
            [c["id"] for c in script["chapters"]],
        )
        self.assertEqual("04 · 结束", script["chapters"][-1]["kicker"])


if __name__ == "__main__":
    unittest.main()
