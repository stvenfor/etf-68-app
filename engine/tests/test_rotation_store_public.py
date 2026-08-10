from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.rotation.config import XIAOXIN_PRESET_ID, ZHIBEI_CLONE_ID, validate_config
from src.rotation.public_xiaoxin import normalize_public
from src.rotation.store import delete_strategy, load_doc, save_strategy


class ConfigTests(unittest.TestCase):
    def test_validate_ma_bull_constraint(self) -> None:
        cfg = validate_config(None)
        cfg["condition_filter"]["ma_bull"] = True
        cfg["condition_filter"]["ma_fast"] = 60
        cfg["condition_filter"]["ma_slow"] = 20
        with self.assertRaises(ValueError):
            validate_config(cfg)


class StoreTests(unittest.TestCase):
    def test_builtin_and_custom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "strategies.json"
            doc = load_doc(path)
            self.assertEqual(doc["active_id"], ZHIBEI_CLONE_ID)
            self.assertTrue(any(i["id"] == ZHIBEI_CLONE_ID for i in doc["items"]))
            self.assertTrue(any(i["id"] == XIAOXIN_PRESET_ID for i in doc["items"]))
            item = save_strategy(
                strategy_id=None,
                name="我的策略",
                config=validate_config(None),
                path=path,
            )
            self.assertFalse(item["readonly"])
            doc2 = load_doc(path)
            self.assertEqual(doc2["active_id"], item["id"])
            delete_strategy(item["id"], path)
            doc3 = load_doc(path)
            self.assertEqual(doc3["active_id"], ZHIBEI_CLONE_ID)
            with self.assertRaises(PermissionError):
                delete_strategy(ZHIBEI_CLONE_ID, path)


class PublicNormalizeTests(unittest.TestCase):
    def test_normalize(self) -> None:
        raw = {
            "source": "zhibeiquant.com",
            "live": False,
            "strategy": {
                "strategy_name": "ETF轮动实盘",
                "total_return": 66.15,
                "max_drawdown": 22.54,
                "day_index": 634,
                "start_date": "2024-11-11",
                "returns": {"ytd": 11.17},
                "history": {"full_dates": ["2024-11-11"], "strategy": [1000.0]},
            },
            "momentum": {
                "date": "2026-08-07",
                "latest_trade_date": "2026-08-07",
                "update_time": "2026-08-09 17:22:44",
                "etf_pool": {"518880": "黄金ETF"},
                "rankings": [
                    {
                        "rank": 1,
                        "code": "518880",
                        "name": "黄金ETF",
                        "score": 0.003,
                        "annualized_return": 10.0,
                        "r_squared": 0.03,
                    }
                ],
            },
        }
        norm = normalize_public(raw)
        self.assertTrue(norm["ok"])
        self.assertEqual(norm["hold_code"], "518880")
        self.assertEqual(norm["total_return_pct"], 66.15)
        self.assertEqual(norm["rankings"][0]["code"], "518880")


if __name__ == "__main__":
    unittest.main()
