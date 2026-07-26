from __future__ import annotations

import unittest

from src.tts_edge import build_ssml, cache_key


class TtsEdgeTests(unittest.TestCase):
    def test_build_ssml_inserts_breaks(self) -> None:
        ssml = build_ssml("第一句。第二句！第三句")
        self.assertIn('<break time="320ms"/>', ssml)
        self.assertIn("第一句。", ssml)
        self.assertIn("第二句！", ssml)
        self.assertIn('rate="-8%"', ssml)

    def test_build_ssml_escapes_xml(self) -> None:
        ssml = build_ssml("涨幅>5%与A&B")
        self.assertIn("&gt;", ssml)
        self.assertIn("&amp;", ssml)
        self.assertNotIn("涨幅>5%", ssml)

    def test_cache_key_stable(self) -> None:
        a = cache_key("你好", "zh-CN-XiaoxiaoNeural", "-8%", "+0Hz")
        b = cache_key("你好", "zh-CN-XiaoxiaoNeural", "-8%", "+0Hz")
        c = cache_key("你好啊", "zh-CN-XiaoxiaoNeural", "-8%", "+0Hz")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


if __name__ == "__main__":
    unittest.main()
