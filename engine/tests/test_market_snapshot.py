from __future__ import annotations

import json
import unittest
from src.market_snapshot import build_market_board, fmt_turnover_yi
from src.review_script import build_review_script


class MarketSnapshotTests(unittest.TestCase):
    def test_fmt_turnover(self) -> None:
        self.assertEqual("2.08万亿", fmt_turnover_yi(20766.2))
        self.assertEqual("850亿", fmt_turnover_yi(850.0))
        self.assertEqual("—", fmt_turnover_yi(None))

    def test_build_market_board_with_fake_fetch(self) -> None:
        sh_days = []
        sz_days = []
        for i, day in enumerate(
            ["2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24", "2026-07-27"]
        ):
            # amount field[8] in 万元
            sh_amt = (9000 + i * 100) * 10_000
            sz_amt = (8000 + i * 80) * 10_000
            sh_days.append(
                [day, "1", "2", "3", "4", "100", {}, "1.0", str(sh_amt), "0", "0"]
            )
            sz_days.append(
                [day, "1", "2", "3", "4", "100", {}, "1.0", str(sz_amt), "0", "0"]
            )

        def fake_fetch(url: str) -> str:
            if "newfqkline" in url and "sh000001" in url:
                return json.dumps({"data": {"sh000001": {"day": sh_days}}})
            if "newfqkline" in url and "sz399001" in url:
                return json.dumps({"data": {"sz399001": {"day": sz_days}}})
            if "newfqkline" in url and "sz399006" in url:
                cyb = [
                    [d, "1", str(3400 + i * 20), "3", "4", "100", {}, "1.0", "10000", "0", "0"]
                    for i, d in enumerate(
                        ["2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24", "2026-07-27"]
                    )
                ]
                return json.dumps({"data": {"sz399006": {"day": cyb}}})
            if "newfqkline" in url and "sh000688" in url:
                kcb = [
                    [d, "1", str(1700 + i * 10), "3", "4", "100", {}, "1.0", "10000", "0", "0"]
                    for i, d in enumerate(
                        ["2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24", "2026-07-27"]
                    )
                ]
                return json.dumps({"data": {"sh000688": {"day": kcb}}})
            if "qt.gtimg.cn" in url:
                raise AssertionError("live quote should not be used when as_of bars exist")
            raise AssertionError(url)

        # Patch SH/SZ bars to include realistic closes (field[2]) for index path.
        for i, row in enumerate(sh_days):
            row[2] = str(3800 + i * 10)
        for i, row in enumerate(sz_days):
            row[2] = str(14000 + i * 30)

        board = build_market_board(as_of="2026-07-27", fetch=fake_fetch)
        self.assertTrue(board["ok"])
        self.assertFalse(board.get("live"))
        self.assertEqual("2026-07-27", board["turnover"]["date"])
        self.assertAlmostEqual(17720.0, board["turnover"]["amountYi"], places=1)
        self.assertEqual(4, len(board["indices"]))
        self.assertEqual("up", board["indices"][0]["tone"])
        self.assertAlmostEqual(3840.0, board["indices"][0]["price"])
        self.assertAlmostEqual(0.26, board["indices"][0]["changePct"], places=2)

    def test_live_board_uses_tencent_quotes(self) -> None:
        def fake_fetch(url: str) -> str:
            if "newfqkline" in url and "sh000001" in url:
                days = [
                    [d, "1", "3800", "3", "4", "100", {}, "1.0", str(9000 * 10_000), "0", "0"]
                    for d in ["2026-07-24", "2026-07-27", "2026-07-28"]
                ]
                return json.dumps({"data": {"sh000001": {"day": days}}})
            if "newfqkline" in url and "sz399001" in url:
                days = [
                    [d, "1", "14000", "3", "4", "100", {}, "1.0", str(8000 * 10_000), "0", "0"]
                    for d in ["2026-07-24", "2026-07-27", "2026-07-28"]
                ]
                return json.dumps({"data": {"sz399001": {"day": days}}})
            if "qt.gtimg.cn" in url:
                # Minimal Tencent quote chunks for INDEX_SPECS codes
                return (
                    'v_sh000001="1~上证指数~000001~3819.67~3858.25~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~-1.00~0";'
                    'v_sz399001="1~深证成指~399001~13660.12~14148.00~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~-3.45~0";'
                    'v_sz399006="1~创业板指~399006~3395.82~3590.00~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~-5.43~0";'
                    'v_sh000688="1~科创50~000688~1734.43~1808.00~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~-4.07~0";'
                )
            raise AssertionError(url)

        board = build_market_board(as_of="2026-07-27", fetch=fake_fetch, live=True)
        self.assertTrue(board["live"])
        self.assertTrue(board.get("fetchedAt"))
        self.assertEqual(3819.67, board["indices"][0]["price"])
        self.assertEqual("dn", board["indices"][0]["tone"])

    def test_review_script_keeps_board_out_of_narration(self) -> None:
        board = {
            "ok": True,
            "asOf": "2026-07-27",
            "turnover": {
                "ok": True,
                "date": "2026-07-27",
                "amountYi": 20766.0,
                "amountLabel": "2.08万亿",
                "avg5Yi": 23627.0,
                "avg5Label": "2.36万亿",
            },
            "indices": [
                {
                    "id": "sh",
                    "code": "000001",
                    "name": "上证指数",
                    "price": 3858.25,
                    "changePct": 1.15,
                    "tone": "up",
                }
            ],
        }
        script = build_review_script(
            {
                "dataDate": "2026-07-27",
                "breadthPct": 44.4,
                "rows": [{"sector": "A", "ret1": 1.0, "action": "观察", "name": "x", "code": "1"}],
            },
            market_board=board,
            fetch_market=False,
        )
        self.assertTrue(script["ok"])
        self.assertEqual("2.08万亿", script["marketBoard"]["turnover"]["amountLabel"])
        self.assertNotIn("万亿", script["fullNarration"])
        self.assertNotIn("上证指数", script["fullNarration"])
        self.assertIn("市场温度", script["fullNarration"])


if __name__ == "__main__":
    unittest.main()
