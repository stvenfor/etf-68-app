from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.macro_pmi import (
    build_pmi_snapshot,
    fetch_macro_pmi,
    load_overlay,
    parse_em_pmi_payload,
)


SAMPLE_PAYLOAD = {
    "result": {
        "data": [
            {
                "REPORT_DATE": "2026-07-01 00:00:00",
                "TIME": "2026年07月份",
                "MAKE_INDEX": 49.2,
                "NMAKE_INDEX": 49.0,
                "MAKE_SAME": -0.2,
                "NMAKE_SAME": -2.1,
            },
            {
                "REPORT_DATE": "2026-06-01 00:00:00",
                "TIME": "2026年06月份",
                "MAKE_INDEX": 50.3,
                "NMAKE_INDEX": 50.2,
            },
        ]
    }
}


class MacroPmiTests(unittest.TestCase):
    def test_parse_and_mom(self) -> None:
        series = parse_em_pmi_payload(SAMPLE_PAYLOAD)
        self.assertEqual("2026-07", series[0]["month"])
        snap = build_pmi_snapshot(series, month="2026-07", overlay={"composite": 49.3, "compositePrev": 50.6})
        self.assertTrue(snap["ok"])
        self.assertEqual(49.2, snap["manufacturing"]["value"])
        self.assertEqual(-1.1, snap["manufacturing"]["momPp"])
        self.assertTrue(snap["manufacturing"]["below50"])
        self.assertEqual(49.3, snap["composite"]["value"])
        self.assertTrue(snap["flags"]["syncContract"])

    def test_overlay_details(self) -> None:
        series = parse_em_pmi_payload(SAMPLE_PAYLOAD)
        ov = {
            "details": [
                {"id": "new_orders", "label": "新订单指数", "value": 48.5, "prev": 51.2, "note": "逾三年最低"}
            ],
            "syncContract": True,
        }
        snap = build_pmi_snapshot(series, month="2026-07", overlay=ov)
        self.assertEqual(1, len(snap["details"]))
        self.assertEqual(-2.7, snap["details"][0]["momPp"])
        self.assertTrue(snap["details"][0]["below50"])

    def test_missing_month(self) -> None:
        series = parse_em_pmi_payload(SAMPLE_PAYLOAD)
        snap = build_pmi_snapshot(series, month="2025-01")
        self.assertFalse(snap["ok"])

    def test_fetch_with_fake(self) -> None:
        def fake(_url: str) -> str:
            return json.dumps(SAMPLE_PAYLOAD)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "macro-pmi-overlay-2026-07.json").write_text(
                json.dumps({"composite": 49.3, "forwardWindowMonth": "2026-08"}),
                encoding="utf-8",
            )
            snap = fetch_macro_pmi("2026-07", fetch=fake, overlay_dir=root)
        self.assertTrue(snap["ok"])
        self.assertEqual("2026-08", snap["forwardWindowMonth"])
        self.assertEqual(49.3, snap["composite"]["value"])

    def test_load_overlay_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual({}, load_overlay("2099-01", overlay_dir=Path(td)))


if __name__ == "__main__":
    unittest.main()
