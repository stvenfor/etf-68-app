from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.citic_sync import merge_cffex_into_citic_monthly


class CiticSyncTests(unittest.TestCase):
    def test_merge_upserts_day_and_totals(self) -> None:
        monthly = {
            "asOf": "2026-07-24",
            "months": [
                {
                    "month": 7,
                    "label": "2026-07",
                    "days": [
                        {
                            "date": "2026-07-24",
                            "weekday": "周五",
                            "citicTotal": 178,
                            "stance": "净加多",
                            "label": "加多单178手",
                            "IH": 1,
                            "IF": 2,
                            "IC": 3,
                            "IM": 4,
                            "isDelivery": False,
                            "shPct": -1.61,
                        }
                    ],
                    "monthNet": 178,
                    "longDays": 1,
                    "shortDays": 0,
                    "n": 1,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "citic-net-positions-20260727.json").write_text(
                json.dumps(
                    {
                        "trade_date": "20260727",
                        "citic_by_symbol": {"IH": -1973, "IF": 110, "IC": -432, "IM": 1034},
                        "citic_total": -1261,
                        "net_buy_total": -2561,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            board = {
                "asOf": "2026-07-27",
                "indices": [
                    {"id": "sh", "changePct": 1.15},
                    {"id": "sz", "changePct": 2.72},
                    {"id": "cyb", "changePct": 3.16},
                    {"id": "kcb", "changePct": 1.16},
                ],
            }
            out = merge_cffex_into_citic_monthly(
                monthly,
                cffex_dirs=[root],
                market_board=board,
                as_of="2026-07-27",
            )
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(out["asOf"], "2026-07-27")
        days = out["months"][0]["days"]
        self.assertEqual(2, len(days))
        last = days[-1]
        self.assertEqual("2026-07-27", last["date"])
        self.assertEqual(-1261, last["citicTotal"])
        self.assertEqual("净加空", last["stance"])
        self.assertEqual(-1300, last["otherTotal"])
        self.assertEqual(-2561, last["grandTotal"])
        self.assertEqual(1.15, last["shPct"])
        self.assertEqual(-1083, out["months"][0]["monthNet"])


if __name__ == "__main__":
    unittest.main()
