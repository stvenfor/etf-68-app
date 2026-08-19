from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from src.a_share_calendar import is_trading_day, recent_trading_days
from src.citic_sync import ensure_recent_cffex_exports, merge_cffex_into_citic_monthly
from src.market_snapshot import fetch_index_pct_by_date


class AShareCalendarTests(unittest.TestCase):
    def test_weekend_and_holiday(self) -> None:
        self.assertFalse(is_trading_day(date(2026, 8, 16)))  # Sunday
        self.assertFalse(is_trading_day(date(2026, 2, 17)))  # Spring Festival
        self.assertTrue(is_trading_day(date(2026, 2, 14)))  # makeup Saturday
        self.assertTrue(is_trading_day(date(2026, 8, 18)))

    def test_recent_trading_days_skips_weekend(self) -> None:
        days = recent_trading_days("2026-08-18", count=10)
        self.assertEqual(10, len(days))
        self.assertEqual(date(2026, 8, 18), days[-1])
        self.assertNotIn(date(2026, 8, 16), days)
        self.assertNotIn(date(2026, 8, 15), days)  # Saturday
        self.assertEqual(date(2026, 8, 5), days[0])


class CiticBackfillTests(unittest.TestCase):
    def test_ensure_fetches_only_missing_days(self) -> None:
        monthly = {
            "asOf": "2026-08-14",
            "months": [
                {
                    "month": 8,
                    "label": "2026-08",
                    "days": [
                        {
                            "date": "2026-08-14",
                            "weekday": "周五",
                            "citicTotal": -213,
                            "stance": "净加空",
                            "label": "加空单213手",
                            "IH": 1,
                            "IF": 2,
                            "IC": 3,
                            "IM": 4,
                            "isDelivery": False,
                        }
                    ],
                    "monthNet": -213,
                    "longDays": 0,
                    "shortDays": 1,
                    "n": 1,
                }
            ],
        }

        def fake_fetch(day: date) -> dict:
            return {
                "trade_date": day.strftime("%Y%m%d"),
                "citic_by_symbol": {"IH": 10, "IF": 20, "IC": -5, "IM": -15},
                "citic_total": 10,
                "net_buy_total": 30,
            }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache"
            cache.mkdir()
            # Pre-seed one missing day export → should be reused, not re-fetched.
            (cache / "citic-net-positions-20260818.json").write_text(
                json.dumps(
                    {
                        "trade_date": "20260818",
                        "citic_by_symbol": {"IH": 1, "IF": 1, "IC": 1, "IM": 1},
                        "citic_total": 4,
                        "net_buy_total": 8,
                    }
                ),
                encoding="utf-8",
            )
            fetch = mock.Mock(side_effect=fake_fetch)
            summary = ensure_recent_cffex_exports(
                monthly,
                as_of="2026-08-18",
                repo_root=root,
                cffex_dirs=[cache],
                lookback_trading_days=3,
                fetch_report=fetch,
            )
            # Window: 08-14, 08-17, 08-18. Have 08-14. Missing 08-17 + 08-18.
            # 08-18 reused from file; 08-17 fetched.
            self.assertEqual(["2026-08-17", "2026-08-18"], summary["missing"])
            self.assertEqual(["2026-08-18"], summary["reused"])
            self.assertEqual(["2026-08-17"], summary["fetched"])
            self.assertEqual([], summary["failed"])
            self.assertEqual(1, fetch.call_count)
            self.assertTrue((cache / "citic-net-positions-20260817.json").is_file())

            merged = merge_cffex_into_citic_monthly(
                monthly,
                cffex_dirs=[cache],
                as_of="2026-08-18",
            )
            assert merged is not None
            dates = [d["date"] for d in merged["months"][0]["days"]]
            self.assertEqual(["2026-08-14", "2026-08-17", "2026-08-18"], dates)
            self.assertEqual("2026-08-18", merged["asOf"])

    def test_ensure_soft_fails_without_fetcher(self) -> None:
        with mock.patch("src.citic_sync.fetch_cffex_report_direct", side_effect=RuntimeError("no_net")):
            with mock.patch("src.citic_sync._resolve_fetch_report", return_value=None):
                summary = ensure_recent_cffex_exports(
                    {"months": []},
                    as_of="2026-08-18",
                    repo_root=Path("/tmp/no-cffex-module"),
                    cffex_dirs=[Path("/tmp/no-cffex-exports")],
                    lookback_trading_days=2,
                    fetch_report=None,
                )
        self.assertTrue(summary["missing"])
        self.assertTrue(summary["failed"])

    def test_merge_backfills_index_pct_for_all_incomplete_days(self) -> None:
        """全量更新：缺涨跌、或四大指数全为 0 的占位行，都要用历史涨跌补齐。"""
        monthly = {
            "asOf": "2026-08-18",
            "months": [
                {
                    "month": 8,
                    "label": "2026-08",
                    "days": [
                        {
                            "date": "2026-08-13",
                            "weekday": "周四",
                            "citicTotal": 33,
                            "shPct": 1.12,
                            "szPct": 0.8,
                            "cybPct": 0.5,
                            "kcbPct": 0.05,
                        },
                        {
                            "date": "2026-08-14",
                            "weekday": "周五",
                            "citicTotal": -213,
                            "shPct": 0.0,
                            "szPct": 0.0,
                            "cybPct": 0.0,
                            "kcbPct": 0.0,
                        },
                        {
                            "date": "2026-08-17",
                            "weekday": "周一",
                            "citicTotal": -564,
                        },
                        {
                            "date": "2026-08-18",
                            "weekday": "周二",
                            "citicTotal": 4858,
                            "shPct": 0.22,
                            # 深证/创业板/科创缺一角
                        },
                    ],
                    "monthNet": 0,
                    "longDays": 2,
                    "shortDays": 2,
                    "n": 4,
                }
            ],
        }
        pct = {
            "2026-08-13": {"shPct": 9.99, "szPct": 9.99, "cybPct": 9.99, "kcbPct": 9.99},
            "2026-08-14": {"shPct": -0.31, "szPct": -0.42, "cybPct": -0.53, "kcbPct": -0.64},
            "2026-08-17": {"shPct": 0.51, "szPct": 0.62, "cybPct": 0.73, "kcbPct": 0.84},
            "2026-08-18": {"shPct": 1.11, "szPct": 0.44, "cybPct": 0.25, "kcbPct": -3.78},
        }
        with tempfile.TemporaryDirectory() as tmp:
            merged = merge_cffex_into_citic_monthly(
                monthly,
                cffex_dirs=[Path(tmp)],
                as_of="2026-08-18",
                index_pct_by_date=pct,
            )
        assert merged is not None
        days = {d["date"]: d for d in merged["months"][0]["days"]}
        # 已有真实涨跌不覆盖
        self.assertEqual(1.12, days["2026-08-13"]["shPct"])
        # 全 0 占位覆盖
        self.assertEqual(-0.31, days["2026-08-14"]["shPct"])
        self.assertEqual(-0.64, days["2026-08-14"]["kcbPct"])
        # 整行缺失补齐
        self.assertEqual(0.51, days["2026-08-17"]["shPct"])
        self.assertEqual(0.84, days["2026-08-17"]["kcbPct"])
        # 缺的键补上，已有非 0 保留
        self.assertEqual(0.22, days["2026-08-18"]["shPct"])
        self.assertEqual(0.44, days["2026-08-18"]["szPct"])
        self.assertEqual(-3.78, days["2026-08-18"]["kcbPct"])


class IndexPctHistoryTests(unittest.TestCase):
    def test_fetch_index_pct_by_date_from_kline(self) -> None:
        days = ["2026-08-14", "2026-08-17", "2026-08-18"]

        def fake_fetch(url: str) -> str:
            if "sh000001" in url:
                rows = [[d, "1", str(3800 + i * 10)] for i, d in enumerate(days)]
                return json.dumps({"data": {"sh000001": {"day": rows}}})
            if "sz399001" in url:
                rows = [[d, "1", str(14000 + i * 20)] for i, d in enumerate(days)]
                return json.dumps({"data": {"sz399001": {"day": rows}}})
            if "sz399006" in url:
                rows = [[d, "1", str(3400 + i * 30)] for i, d in enumerate(days)]
                return json.dumps({"data": {"sz399006": {"day": rows}}})
            if "sh000688" in url:
                rows = [[d, "1", str(1700 + i * 40)] for i, d in enumerate(days)]
                return json.dumps({"data": {"sh000688": {"day": rows}}})
            raise AssertionError(url)

        by_date = fetch_index_pct_by_date(fetch=fake_fetch, days=10)
        self.assertNotIn("2026-08-14", by_date)
        row = by_date["2026-08-17"]
        self.assertAlmostEqual((3810 / 3800 - 1) * 100, row["shPct"], places=2)
        self.assertAlmostEqual((14020 / 14000 - 1) * 100, row["szPct"], places=2)
        self.assertAlmostEqual((3430 / 3400 - 1) * 100, row["cybPct"], places=2)
        self.assertAlmostEqual((1740 / 1700 - 1) * 100, row["kcbPct"], places=2)


if __name__ == "__main__":
    unittest.main()
