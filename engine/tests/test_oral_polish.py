from __future__ import annotations

import unittest

from src.oral_polish import fact_tokens, polish_narration, polish_script


class OralPolishTests(unittest.TestCase):
    def test_review_openers_and_facts(self) -> None:
        open_only = polish_narration(
            "ETF六十八市场复盘。数据日期2099-01-15。市场温度百分之40.0。",
            kind="review",
            chapter_id="open",
        )
        self.assertIn("来看ETF六十八市场复盘", open_only)
        self.assertIn("今天市场温度差不多百分之40.0", open_only)
        self.assertIn("2099-01-15", open_only)

        sectors = polish_narration(
            "板块均涨跌。涨幅前三：传媒+6.50%。跌幅前三：煤炭行业-2.10%。",
            kind="review",
            chapter_id="sectors",
        )
        self.assertIn("先瞅一眼板块均涨跌", sectors)
        self.assertIn("涨得最猛的三个是", sectors)
        self.assertIn("传媒+6.50%", sectors)
        self.assertIn("煤炭行业-2.10%", sectors)

        news = polish_narration(
            "实质消息。利好：利好当日。利空：利空当日。",
            kind="review",
            chapter_id="news",
        )
        self.assertIn("消息面扫一眼", news)
        self.assertIn("利好当日", news)
        self.assertIn("利空当日", news)
        self.assertNotIn("利好当天", news)

        cand = polish_narration(
            "技术候选。某某ETF当日+1.00%，五日+2.00%。",
            kind="review",
            chapter_id="candidates",
        )
        self.assertIn("技术候选这边", cand)
        self.assertIn("当天", cand)
        self.assertIn("+1.00%", cand)

        empty_cand = polish_narration(
            "技术候选。今日暂无技术候选。",
            kind="review",
            chapter_id="candidates",
        )
        self.assertEqual("技术候选这边。今天暂时没有技术候选。", empty_cand)

        # Fact guard: if a rewrite would drop a token, keep original
        broken = polish_narration("涨幅是+6.50%。", kind="review")
        self.assertIn("+6.50%", broken)

    def test_macro_polish(self) -> None:
        hook = polish_narration(
            "2026年7月，国家统计局公布采购经理指数。制造业PMI报49.2%。荣枯线是五十。",
            kind="macro",
            chapter_id="hook",
        )
        self.assertIn("刚公布", hook)
        self.assertIn("49.2%", hook)
        self.assertIn("荣枯线", hook)

        close = polish_narration(
            "ETF-68 宏观快评本期到这里。数据来源于网络，不构成投资建议。",
            kind="macro",
            chapter_id="close",
        )
        self.assertIn("好，本期到这里", close)
        self.assertIn("不构成投资建议", close)

    def test_polish_script_flag(self) -> None:
        script = {
            "ok": True,
            "chapters": [
                {"id": "open", "narration": "ETF六十八市场复盘。数据日期2099-01-15。"},
                {"id": "close", "narration": "复盘结束。数据来源于网络，仅供参考。"},
            ],
        }
        out = polish_script(script, kind="review")
        self.assertTrue(out["oralPolish"])
        self.assertIn("来看ETF六十八", out["fullNarration"])
        self.assertIn("好，今天就聊到这儿", out["fullNarration"])
        self.assertIn("净加多40手", fact_tokens("中信净加多40手"))


if __name__ == "__main__":
    unittest.main()
