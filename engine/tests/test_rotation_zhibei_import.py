from __future__ import annotations

import unittest

from src.rotation.zhibei_import import from_zhibei_config


class ZhibeiImportTests(unittest.TestCase):
    def test_official_clone_mapping(self) -> None:
        raw = {
            "codes": ["510300.XSHG", "159915.XSHE", "513100.XSHG"],
            "benchmark_code": "510300.XSHG",
            "start": "2025-01-01",
            "end": "2026-08-07",
            "momentum_days": 25,
            "hold_count": 1,
            "scoring_method": "log_trend",
            "slippage_rate": 0.001,
            "commission_rate": 0.0002,
        }
        cfg = from_zhibei_config(raw)
        self.assertEqual(cfg["etf_pool"], ["510300", "159915", "513100"])
        self.assertEqual(cfg["momentum"]["method"], "slope")
        self.assertEqual(cfg["momentum"]["window"], 25)
        self.assertEqual(cfg["selection"]["top_n"], 1)
        self.assertEqual(cfg["holding"]["min_hold_days"], 1)
        self.assertEqual(cfg["costs"]["slippage_rate"], 0.001)
        self.assertEqual(cfg["costs"]["commission_rate"], 0.0002)
        self.assertEqual(cfg["backtest"]["start_date"], "2025-01-01")
        self.assertEqual(cfg["backtest"]["end_date"], "2026-08-07")
        self.assertNotIn("518880", cfg["etf_pool"])

    def test_list_picks_new_four_pool_by_id(self) -> None:
        payload = {
            "items": [
                {
                    "id": "514c372c-0d6e-4b30-810d-774a0c7418ae",
                    "updated_at": "2026-08-10T07:30:11+00:00",
                    "config": {
                        "codes": ["159915.XSHE", "513100.XSHG", "512890.XSHG", "518880.XSHG"],
                        "scoring_method": "log_trend",
                        "momentum_days": 25,
                        "hold_count": 1,
                    },
                },
                {
                    "id": "d71a16a0-2595-4f15-9114-d75bf481464d",
                    "updated_at": "2026-08-09T13:36:09+00:00",
                    "config": {
                        "codes": ["510300.XSHG", "159915.XSHE", "513100.XSHG"],
                        "scoring_method": "log_trend",
                        "momentum_days": 25,
                        "hold_count": 1,
                    },
                },
            ]
        }
        cfg = from_zhibei_config(payload)
        self.assertEqual(cfg["etf_pool"], ["159915", "513100", "512890", "518880"])
        self.assertEqual(cfg["etf_names"]["512890"], "红利低波ETF")
        self.assertNotIn("510300", cfg["etf_pool"])


if __name__ == "__main__":
    unittest.main()
