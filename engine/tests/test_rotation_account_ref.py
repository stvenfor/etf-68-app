from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.rotation.account_ref import import_account_reference, normalize_account_payload


class AccountRefImportTests(unittest.TestCase):
    def test_import_result_with_history(self) -> None:
        payload = {
            "items": [
                {
                    "id": "d71a16a0-2595-4f15-9114-d75bf481464d",
                    "name": "我的策略",
                    "config": {
                        "codes": ["510300.XSHG", "159915.XSHE", "513100.XSHG"],
                        "scoring_method": "log_trend",
                        "momentum_days": 25,
                    },
                    "result": {
                        "strategy": {
                            "total_return": 12.3,
                            "max_drawdown": 8.1,
                            "day_index": 3,
                            "returns": {"ytd": 11.0},
                            "history": {
                                "labels": ["01-02", "01-03", "01-06"],
                                "full_dates": ["2025-01-02", "2025-01-03", "2025-01-06"],
                                "strategy": [1.0, 1.02, 1.05],
                            },
                        },
                        "momentum": {
                            "date": "2025-01-06",
                            "rankings": [
                                {
                                    "rank": 1,
                                    "code": "513100",
                                    "name": "纳指",
                                    "score": 0.01,
                                    "annualized_return": 10.0,
                                    "r_squared": 0.5,
                                }
                            ],
                        },
                    },
                }
            ]
        }
        snap = normalize_account_payload(payload)
        self.assertEqual(snap["equity_source"], "account_import")
        self.assertEqual(len(snap["equity"]["dates"]), 3)
        self.assertAlmostEqual(snap["total_return_pct"], 12.3)
        self.assertEqual(snap["hold_code"], "513100")

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "zhibei-reference.json"
            saved = import_account_reference(payload, path=path)
            self.assertTrue(path.exists())
            self.assertEqual(saved["equity_source"], "account_import")

    def test_result_null_keeps_empty_equity(self) -> None:
        snap = normalize_account_payload(
            {"id": "x", "name": "我的策略", "result": None, "rankings": []}
        )
        self.assertEqual(snap["equity_source"], "none")
        self.assertEqual(snap["equity"]["dates"], [])

    def test_simulation_active_uses_latest_close_rankings(self) -> None:
        snap = normalize_account_payload(
            {
                "items": [
                    {
                        "id": "d71a16a0-2595-4f15-9114-d75bf481464d",
                        "name": "我的策略",
                        "config": {"codes": ["513100.XSHG"], "scoring_method": "log_trend"},
                        "simulation": {
                            "status": "active",
                            "simulation_start_date": "2026-08-09",
                            "last_refreshed_at": None,
                            "latest_close_date": "2026-08-07",
                            "latest_close_rankings": [
                                {
                                    "rank": 1,
                                    "code": "513100",
                                    "name": "纳指100 ETF",
                                    "score": 0.0006,
                                    "annualized_return": 8.21,
                                    "r_squared": 0.01,
                                }
                            ],
                            "result": None,
                            "metrics": {},
                        },
                    }
                ]
            }
        )
        self.assertEqual(snap["equity_source"], "none")
        self.assertEqual(snap["hold_code"], "513100")
        self.assertEqual(snap["as_of"], "2026-08-07")
        self.assertIn("向前模拟盘", snap["note"])

    def test_persisted_run_equity_curve(self) -> None:
        payload = {
            "kind": "persisted_run",
            "status": "completed",
            "run": {
                "strategy_id": "d71a16a0-2595-4f15-9114-d75bf481464d",
                "strategy_name": "我的策略",
            },
            "result": {
                "config": {
                    "codes": ["510300.XSHG", "159915.XSHE", "513100.XSHG"],
                    "scoring_method": "log_trend",
                    "momentum_days": 25,
                    "hold_count": 1,
                    "start": "2025-01-01",
                    "end": "2026-08-07",
                },
                "metrics": {
                    "annualized_return": 0.475,
                    "max_drawdown": -0.216,
                    "sharpe_ratio": 1.58,
                    "trade_count": 15,
                },
                "equity_curve": [
                    {"date": "2025-01-02", "strategy_value": 1.0, "benchmark_value": 1.0},
                    {"date": "2025-01-03", "strategy_value": 1.1, "benchmark_value": 1.01},
                    {"date": "2026-08-07", "strategy_value": 1.86, "benchmark_value": 1.2},
                ],
                "current_suggestion": {
                    "date": "2026-08-07",
                    "target_holdings": ["513100.XSHG"],
                    "scores": [
                        {
                            "code": "513100.XSHG",
                            "score": -0.0006,
                            "annualized_return": -0.072,
                            "r_squared": 0.01,
                        }
                    ],
                },
                "trades": [
                    {
                        "date": "2025-01-02",
                        "target_holdings": ["513100.XSHG"],
                        "target_holding_details": [{"code": "513100.XSHG", "name": "纳指100 ETF"}],
                    }
                ],
            },
        }
        snap = normalize_account_payload(payload)
        self.assertEqual(snap["equity_source"], "account_import")
        self.assertEqual(len(snap["equity"]["dates"]), 3)
        self.assertAlmostEqual(snap["equity"]["nav"][-1], 1.86)
        self.assertAlmostEqual(snap["total_return_pct"], 86.0, places=1)
        self.assertAlmostEqual(snap["max_drawdown_pct"], 21.6, places=1)
        self.assertAlmostEqual(snap["annualized_return_pct"], 47.5, places=1)
        self.assertEqual(snap["hold_code"], "513100")
        self.assertEqual(snap["hold_name"], "纳指ETF")
        self.assertEqual(snap["rankings"][0]["name"], "纳指ETF")
        self.assertEqual(snap["equity"]["codes"][-1], "513100")
        self.assertEqual(snap["equity"]["names"][-1], "纳指100 ETF")
        self.assertEqual(snap["trade_count"], 15)
        self.assertIn("网站回测净值", snap["note"] or "")

    def test_runs_list_summary_without_equity_curve(self) -> None:
        payload = {
            "items": [
                {
                    "id": "9c372fad-3744-4f6c-92cc-23fa6619ecf3",
                    "strategy_id": "514c372c-0d6e-4b30-810d-774a0c7418ae",
                    "strategy_name": "我的策略",
                    "config_snapshot": {
                        "codes": ["159915.XSHE", "513100.XSHG", "512890.XSHG", "518880.XSHG"],
                        "scoring_method": "log_trend",
                        "momentum_days": 25,
                        "hold_count": 1,
                        "end": "2026-08-07",
                    },
                    "result": {
                        "metrics": {
                            "annualized_return": 0.3477,
                            "max_drawdown": -0.2084,
                            "trade_count": 25,
                        },
                        "equity_curve": [],
                        "current_suggestion": {
                            "date": "2026-08-07",
                            "target_holdings": ["512890.XSHG"],
                            "scores": [
                                {
                                    "code": "512890.XSHG",
                                    "score": 1.06,
                                    "annualized_return": 1.36,
                                    "r_squared": 0.78,
                                }
                            ],
                        },
                    },
                    "updated_at": "2026-08-10T07:33:35+00:00",
                }
            ]
        }
        snap = normalize_account_payload(
            payload, strategy_id="514c372c-0d6e-4b30-810d-774a0c7418ae"
        )
        self.assertEqual(snap["strategy_id"], "514c372c-0d6e-4b30-810d-774a0c7418ae")
        self.assertEqual(snap["equity_source"], "none")
        self.assertEqual(snap["hold_code"], "512890")
        self.assertEqual(snap["hold_name"], "红利低波ETF")
        self.assertEqual(snap["rankings"][0]["name"], "红利低波ETF")
        self.assertAlmostEqual(snap["annualized_return_pct"], 34.77, places=1)
        self.assertAlmostEqual(snap["max_drawdown_pct"], 20.84, places=1)
        self.assertEqual(snap["trade_count"], 25)
        self.assertEqual(snap["pool"], ["159915", "513100", "512890", "518880"])
        self.assertIn("equity_curve 置空", snap["note"] or "")


if __name__ == "__main__":
    unittest.main()
