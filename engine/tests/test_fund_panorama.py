"""Tests for open-end fund NAV panorama."""

from __future__ import annotations

import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.fund_panorama import build_fund_panorama, parse_net_worth_trend

SH = ZoneInfo("Asia/Shanghai")


def _ms(y: int, m: int, d: int) -> int:
    return int(datetime(y, m, d, tzinfo=SH).timestamp() * 1000)


class FundPanoramaTests(unittest.TestCase):
    def test_parse_and_summary(self) -> None:
        points = []
        nav = 1.0
        for i, (y, m, d, chg) in enumerate(
            [
                (2025, 1, 2, 0.0),
                (2025, 1, 3, 1.0),
                (2025, 1, 6, 1.0),
                (2025, 1, 7, -2.0),
                (2025, 1, 8, -1.0),
            ]
        ):
            if i > 0:
                nav = round(nav * (1 + chg / 100.0), 6)
            points.append({"x": _ms(y, m, d), "y": nav, "equityReturn": chg})

        body = 'var fS_name = "测试基金";' + f"Data_netWorthTrend={json.dumps(points)};"

        def fake_fetch(url: str) -> str:
            self.assertIn("000043", url)
            return body

        out = build_fund_panorama("43", fetch=fake_fetch, meta={"name": "嘉实美国成长"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["code"], "000043")
        self.assertEqual(out["meta"]["name"], "嘉实美国成长")
        self.assertEqual(out["summary"]["points"], 5)
        self.assertEqual(out["series"][0]["date"], "2025-01-02")
        self.assertGreater(out["summary"]["maxDrawdownPct"], 0)

    def test_fetch_error(self) -> None:
        def boom(_: str) -> str:
            raise RuntimeError("network")

        out = build_fund_panorama("110022", fetch=boom)
        self.assertFalse(out["ok"])
        self.assertIn("network", out["error"] or "")


if __name__ == "__main__":
    unittest.main()
