from __future__ import annotations

import json
import unittest
from datetime import date

from src.live_impact_news import (
    fetch_eastmoney_headlines,
    live_events_for_etf,
)


class LiveImpactNewsTests(unittest.TestCase):
    def test_classifies_and_maps_fast_and_column_news(self) -> None:
        fast = {
            "data": {
                "fastNewsList": [
                    {
                        "code": "a1",
                        "showTime": "2026-07-28 08:10:00",
                        "title": "韩国KOSPI暴跌，SK海力士大跌引发存储芯片抛售",
                        "summary": "亚洲半导体风险偏好骤降，芯片股承压。",
                        "stockList": ["0.159995", "1.512480"],
                    },
                    {
                        "code": "a2",
                        "showTime": "2026-07-28 07:00:00",
                        "title": "上半年规上工业企业利润大幅增长",
                        "summary": "全国规上工业企业利润同比增长，制造业回暖提振。",
                    },
                    {
                        "code": "noise",
                        "showTime": "2026-07-28 06:00:00",
                        "title": "新华财经早报：7月28日",
                        "summary": "早报汇总。",
                    },
                ]
            }
        }
        column = {
            "data": {
                "list": [
                    {
                        "code": "b1",
                        "showTime": "2026-07-28 08:40:00",
                        "title": "液冷从可选项到必选项 AI算力狂飙下的千亿赛道",
                        "summary": "智算中心液冷放量，催化算力与AI硬件增长。",
                    }
                ]
            }
        }
        payloads = [json.dumps(fast).encode(), json.dumps(column).encode(), json.dumps(column).encode(), json.dumps(column).encode()]

        def fake_fetch(_url: str) -> bytes:
            return payloads.pop(0) if payloads else json.dumps({"data": {}}).encode()

        live = fetch_eastmoney_headlines(as_of=date(2026, 7, 28), fetch=fake_fetch)
        titles = [e["title"] for e in live]
        self.assertIn("韩国KOSPI暴跌，SK海力士大跌引发存储芯片抛售", titles)
        self.assertIn("上半年规上工业企业利润大幅增长", titles)
        self.assertIn("液冷从可选项到必选项 AI算力狂飙下的千亿赛道", titles)
        self.assertTrue(all("早报" not in t for t in titles))

        chip = next(e for e in live if "KOSPI" in e["title"])
        self.assertEqual("利空", chip["logic"])
        self.assertIn("semiconductor", chip["sectors"])
        self.assertIn("159995", chip["codes"])

        ai = next(e for e in live if "液冷" in e["title"])
        self.assertIn(ai["logic"], {"利好", "中性偏多"})
        self.assertIn("artificial_intelligence", ai["sectors"])

        bear = live_events_for_etf(live, code="512480", sector="semiconductor", side="bear")
        self.assertTrue(any("KOSPI" in e["title"] for e in bear))
        bull = live_events_for_etf(live, code="515980", sector="artificial_intelligence", side="bull")
        self.assertTrue(any("液冷" in e["title"] for e in bull))


if __name__ == "__main__":
    unittest.main()
