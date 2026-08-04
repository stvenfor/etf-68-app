from __future__ import annotations

import unittest

from src.macro_flash_script import CHAPTER_IDS, build_macro_flash_script
from src.macro_pmi import build_pmi_snapshot, parse_em_pmi_payload


def _july_snap() -> dict:
    payload = {
        "result": {
            "data": [
                {
                    "REPORT_DATE": "2026-07-01 00:00:00",
                    "TIME": "2026年07月份",
                    "MAKE_INDEX": 49.2,
                    "NMAKE_INDEX": 49.0,
                },
                {
                    "REPORT_DATE": "2026-06-01 00:00:00",
                    "MAKE_INDEX": 50.3,
                    "NMAKE_INDEX": 50.2,
                },
            ]
        }
    }
    series = parse_em_pmi_payload(payload)
    return build_pmi_snapshot(
        series,
        month="2026-07",
        overlay={
            "composite": 49.3,
            "compositePrev": 50.6,
            "forwardWindowMonth": "2026-08",
            "details": [
                {"id": "new_orders", "label": "新订单指数", "value": 48.5, "prev": 51.2, "note": "逾三年最低"},
                {"id": "hi_tech", "label": "高技术制造PMI", "value": 53.3, "note": "扩张"},
            ],
            "interpretation": ["淡季解释一半", "新订单指向需求", "结构分化"],
            "signals": [
                {"label": "8月PMI", "value": "是否回五十", "note": "验证"},
            ],
        },
    )


class MacroFlashScriptTests(unittest.TestCase):
    def test_chapter_order_and_facts(self) -> None:
        script = build_macro_flash_script(_july_snap(), tone="neutral")
        self.assertTrue(script["ok"])
        self.assertTrue(script.get("oralPolish"))
        ids = [c["id"] for c in script["chapters"]]
        self.assertEqual(list(CHAPTER_IDS), ids)
        hook = script["chapters"][0]["narration"]
        self.assertIn("49.2", hook)
        self.assertIn("荣枯线", hook)
        self.assertIn("刚公布", hook)
        self.assertNotIn("黄灯", hook)  # neutral tone avoids copying source metaphor
        facts = script["chapters"][1]
        self.assertTrue(any(m.get("label") == "制造业PMI" for m in facts["body"]["metrics"]))
        self.assertIn("不构成投资建议", script["chapters"][-1]["narration"])
        self.assertIn("好，本期到这里", script["chapters"][-1]["narration"])

        raw = build_macro_flash_script(_july_snap(), tone="neutral", polish=False)
        self.assertFalse(raw.get("oralPolish"))
        self.assertIn("国家统计局公布采购经理指数", raw["chapters"][0]["narration"])
        self.assertNotIn("刚公布", raw["chapters"][0]["narration"])

    def test_caution_tone(self) -> None:
        script = build_macro_flash_script(_july_snap(), tone="caution")
        self.assertIn("转冷", script["chapters"][0]["body"]["metaphor"])

    def test_bad_snapshot(self) -> None:
        out = build_macro_flash_script({"ok": False, "error": "x"})
        self.assertFalse(out["ok"])


if __name__ == "__main__":
    unittest.main()
