"""Unit tests for funds_top30 (no network)."""

from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from src.funds_top30 import (
    FORCE_EXCLUDE,
    FORCE_INCLUDE,
    QUOTA,
    approx_aum_yi,
    build_funds_top30,
    cap_estimate_clock_for_display,
    is_excluded_name_code,
    parse_pingzhong_nav,
    parse_sina_fund_quote,
    parse_sina_jsonp,
    select_category_top,
    share_class_key,
    write_funds_top30,
)


def _sina_row(symbol: str, sname: str, zjzfe: float, dwjz: float, jzrq: str = "2026-07-24") -> dict:
    return {
        "symbol": symbol,
        "sname": sname,
        "zjzfe": zjzfe,
        "dwjz": dwjz,
        "jzrq": f"{jzrq} 00:00:00",
    }


class FundsTop30HelpersTest(unittest.TestCase):
    def test_exclude_etf_money_and_cross_type(self) -> None:
        self.assertTrue(is_excluded_name_code("华泰柏瑞沪深300ETF", "510300", "equity"))
        self.assertTrue(is_excluded_name_code("华夏沪深300ETF联接A", "000051", "equity"))
        self.assertTrue(is_excluded_name_code("易方达深证100ETF联接A", "110019", "equity"))
        self.assertTrue(is_excluded_name_code("某指数联接A", "000999", "equity"))
        self.assertTrue(is_excluded_name_code("某货币基金A", "000001", "equity"))
        self.assertTrue(is_excluded_name_code("某债券基金", "110017", "equity"))
        self.assertTrue(is_excluded_name_code("某股票基金", "000001", "qdii"))
        self.assertFalse(is_excluded_name_code("易方达消费行业股票", "110022", "equity"))
        self.assertFalse(is_excluded_name_code("广发全球精选股票(QDII)人民币A", "270023", "qdii"))

    def test_select_pins_and_excludes(self) -> None:
        raw = [
            _sina_row("163406", "兴全合润混合A", 9e9, 2.0),  # excluded
            _sina_row("007119", "睿远成长价值混合A", 8e9, 2.0),  # excluded
            _sina_row("005827", "易方达蓝筹精选混合", 7e9, 2.0),  # excluded
            _sina_row("003096", "中欧医疗健康混合C", 6.5e9, 2.0),  # excluded
            _sina_row("009881", "广发中证医疗ETF联接C", 5e9, 2.0),  # excluded 联接
            _sina_row("001123", "鹏华弘利混合C", 1e8, 1.8),  # pinned, small AUM
            _sina_row("110023", "易方达医疗保健行业混合", 2e8, 1.2),  # pinned comprehensive medical
            _sina_row("011452", "华泰柏瑞质量成长混合C", 6e9, 2.0),
        ]
        picked = select_category_top(raw, "hybrid", 6)
        codes = [r["code"] for r in picked]
        for c in FORCE_EXCLUDE:
            self.assertNotIn(c, codes)
        # pins first (even if small / missing from raw)
        self.assertEqual(codes[0], FORCE_INCLUDE["hybrid"][0])
        self.assertIn("001123", codes)
        self.assertIn("001423", codes)  # stub pin not in raw
        self.assertIn("110023", codes)
        self.assertNotIn("003096", codes)
        self.assertNotIn("009881", codes)
        self.assertEqual(len(picked), 6)

    def test_equity_tech_pins(self) -> None:
        raw = [
            _sina_row("110022", "易方达消费行业股票", 9e9, 2.8),
            _sina_row("014855", "嘉实中证半导体指数增强发起式C", 1e8, 3.0),
        ]
        picked = select_category_top(raw, "equity", QUOTA["equity"])
        codes = [r["code"] for r in picked]
        self.assertEqual(codes, list(FORCE_INCLUDE["equity"]))
        self.assertNotIn("110022", codes)

    def test_select_allows_shortfall_under_quota(self) -> None:
        raw = [
            _sina_row("110022", "易方达消费行业股票", 3.6e9, 2.8),
            _sina_row("000051", "华夏沪深300ETF联接A", 9e9, 1.7),  # feeder excluded
            _sina_row("001938", "中欧时代先锋股票A", 3e9, 2.0),
        ]
        picked = select_category_top(raw, "equity", QUOTA["equity"], pin_codes=())
        self.assertEqual(len(picked), 2)  # under quota is OK
        self.assertEqual([r["code"] for r in picked], ["110022", "001938"])

    def test_share_class_key_collapses_ac(self) -> None:
        self.assertEqual(share_class_key("兴全合宜混合A"), share_class_key("兴全合宜混合C"))
        self.assertEqual(share_class_key("景顺长城景颐双利债券A类"), share_class_key("景顺长城景颐双利债券C类"))

    def test_approx_aum_yi(self) -> None:
        # 1e8 shares * 1.0 NAV = 1 亿
        self.assertAlmostEqual(approx_aum_yi(1e8, 1.0) or 0, 1.0)

    def test_select_quota_and_dedupe(self) -> None:
        raw = [
            _sina_row("110022", "易方达消费行业股票", 3.6e9, 2.8),  # ~100.8亿
            _sina_row("110022C", "易方达消费行业股票C", 1e8, 2.8),  # smaller twin — code ok as name key
            _sina_row("001938", "中欧时代先锋股票A", 3e9, 2.0),
            _sina_row("001939", "中欧时代先锋股票C", 5e8, 2.0),  # same family, smaller
            _sina_row("510300", "华泰柏瑞沪深300ETF", 9e10, 4.0),  # ETF excluded
            _sina_row("000628", "大成高鑫股票A", 2e9, 5.0),
        ]
        # fix invalid code for C share — use real-looking codes
        raw[1] = _sina_row("011022", "易方达消费行业股票C", 1e8, 2.8)
        picked = select_category_top(raw, "equity", QUOTA["equity"], pin_codes=())
        codes = [r["code"] for r in picked]
        self.assertNotIn("510300", codes)
        self.assertIn("110022", codes)
        self.assertNotIn("011022", codes)  # smaller share class dropped
        self.assertIn("001938", codes)
        self.assertNotIn("001939", codes)
        self.assertEqual(len(picked), 3)
        self.assertEqual(picked[0]["rankInCategory"], 1)
        self.assertEqual(picked[0]["categoryLabel"], "股票型")


class FundsTop30BuildTest(unittest.TestCase):
    def test_build_with_fixture_fetch(self) -> None:
        # Extra hybrid rows so AUM fill can reach quota after 5 pins.
        hybrid_rows = [
            _sina_row(c, n, aum, 1.5)
            for c, n, aum in [
                ("005827", "易方达蓝筹精选混合", 7e9),  # excluded
                ("017811", "东方人工智能主题混合C", 6.5e9),
                ("025209", "永赢先锋半导体智选混合发起C", 6e9),
                ("022365", "永赢科技智选混合发起C", 5.5e9),
                ("013841", "银华集成电路混合C", 5e9),
                ("011452", "华泰柏瑞质量成长混合C", 4.5e9),
                ("012951", "汇添富鑫享添利六个月持有混合A", 4e9),
                ("001123", "鹏华弘利混合C", 1e8),
                ("001423", "景顺长城安享回报混合C", 1.1e8),
                ("001407", "景顺长城稳健回报混合C", 1.2e8),
                ("009690", "易方达瑞锦混合C", 1.3e8),
                ("001638", "前海开源优势蓝筹股票C", 1.4e8),
                ("163406", "兴全合润混合A", 9e9),  # excluded
                ("007119", "睿远成长价值混合A", 8.5e9),  # excluded
                ("003095", "中欧医疗健康混合A", 8e9),  # excluded
                ("003096", "中欧医疗健康混合C", 7.8e9),  # excluded
                ("009881", "广发中证医疗ETF联接C", 7.6e9),  # excluded 联接
                ("110023", "易方达医疗保健行业混合", 2e8),  # pinned comprehensive medical
                ("002910", "易方达供给改革混合", 7.5e9),  # excluded
                ("008989", "大成科技创新混合C", 7.2e9),  # excluded
                ("019001", "测试混合补位1A", 3.9e9),
                ("019002", "测试混合补位2A", 3.8e9),
                ("019003", "测试混合补位3A", 3.7e9),
                ("019004", "测试混合补位4A", 3.6e9),
                ("019005", "测试混合补位5A", 3.5e9),
                ("019006", "测试混合补位6A", 3.4e9),
            ]
        ]
        sina_payloads = {
            "2": [
                _sina_row("014855", "嘉实中证半导体指数增强发起式C", 7e9, 3.0),
                _sina_row("014193", "汇添富中证芯片产业指数增强发起式A", 2e9, 2.0),
                _sina_row("020899", "天弘中证全指通信设备指数发起A", 1.5e9, 3.0),
                _sina_row("020256", "中欧中证机器人指数发起C", 1.2e9, 1.4),
                _sina_row("110022", "易方达消费行业股票", 9e9, 2.8),
                _sina_row("510300", "华泰柏瑞沪深300ETF", 9e10, 4.0),
            ],
            "3": [
                _sina_row(f"{i:06d}", f"测试债券{i}A", (400 - i) * 1e8, 1.1)
                for i in range(1, 8)
            ],
            "1": hybrid_rows,
            "6": [
                _sina_row("270023", "广发全球精选股票(QDII)人民币A", 2e9, 6.0),
                _sina_row("005698", "华夏全球科技先锋混合(QDII)A", 1e9, 2.8),
                _sina_row("100055", "富国全球科技互联网股票(QDII)A", 9e8, 5.0),
                _sina_row("006373", "国富全球科技互联混合(QDII)人民币A", 8e8, 7.0),
                _sina_row("513330", "华夏恒生互联网科技业ETF(QDII)", 9e10, 0.3),
            ],
        }

        def fake_fetch(url: str) -> str:
            if "NetValueReturnOpen" in url:
                qs = parse_qs(urlparse(url).query)
                type2 = (qs.get("type2") or ["2"])[0]
                rows = sina_payloads[type2]
                return "IO.XSRV2.CallbackList['J2cW8KXheoWKdSHc'](" + json.dumps({"data": rows}) + ")"
            if "pingzhongdata" in url:
                code = url.rsplit("/", 1)[-1].replace(".js", "")
                return (
                    f'var fS_name = "基金{code}";var fS_code = "{code}";'
                    "Data_netWorthTrend="
                    '[{"x":1784822400000,"y":1.234,"equityReturn":0.56,"unitMoney":""}];'
                )
            if "sinajs.cn" in url:
                # list=fu_110022,fu_001938,...
                parts = url.split("list=", 1)[-1].split(",")
                lines = []
                for p in parts:
                    code = p.replace("fu_", "").strip()
                    # name,time,est,prev,prev,flag,chgPct,date,...
                    lines.append(
                        f'var hq_str_fu_{code}="基金{code},15:00:00,1.250,1.234,1.234,0,1.2966,2026-07-24,1.250,1.3";'
                    )
                return "\n".join(lines)
            raise AssertionError(f"unexpected url: {url}")

        result = build_funds_top30(rebuild=True, fetch=fake_fetch)
        self.assertTrue(result["ok"])
        self.assertEqual(result["quota"], QUOTA)
        self.assertEqual(result["counts"]["equity"], QUOTA["equity"])
        self.assertEqual(result["counts"]["bond"], QUOTA["bond"])
        self.assertEqual(result["counts"]["hybrid"], QUOTA["hybrid"])
        self.assertEqual(result["counts"]["qdii"], QUOTA["qdii"])
        expected_total = sum(QUOTA.values())
        self.assertEqual(len(result["rows"]), expected_total)
        hybrid_codes = [r["code"] for r in result["rows"] if r["category"] == "hybrid"]
        for c in FORCE_INCLUDE["hybrid"]:
            self.assertIn(c, hybrid_codes)
        for c in FORCE_EXCLUDE:
            self.assertNotIn(c, hybrid_codes)
        self.assertIn("110023", hybrid_codes)
        self.assertNotIn("003096", hybrid_codes)
        self.assertNotIn("009881", hybrid_codes)
        equity_codes = [r["code"] for r in result["rows"] if r["category"] == "equity"]
        self.assertEqual(equity_codes, list(FORCE_INCLUDE["equity"]))
        self.assertIn("adviceFramework", result)
        self.assertTrue(result.get("adviceCounts"))
        for row in result["rows"]:
            self.assertIsNotNone(row.get("nav"))
            self.assertEqual(row.get("navDate"), "2026-07-24")
            self.assertEqual(row.get("dayChangePct"), 0.56)
            self.assertAlmostEqual(row.get("estimateNav") or 0, 1.25)
            self.assertAlmostEqual(row.get("estimateChange") or 0, 0.016)  # 1.25 - 1.234
            self.assertAlmostEqual(row.get("estimateChangePct") or 0, 1.2966, places=3)
            self.assertTrue(row.get("estimateTime"))
            self.assertNotIn("刷新", row.get("estimateTime") or "")
            self.assertNotIn("·", row.get("estimateTime") or "")
            # Quote clock 15:00 is capped to 14:50 for display; raw kept in estimateQuoteTime.
            self.assertEqual(row.get("estimateTime"), "2026-07-24 14:50:00")
            self.assertEqual(row.get("estimateQuoteTime"), "2026-07-24 15:00:00")
            self.assertIn(row.get("advice"), {"可关注", "相对友好", "观望", "不追高", "暂缓"})
            self.assertTrue(row.get("adviceDetail"))
            self.assertTrue(row.get("adviceRisk"))
            name_u = (row.get("name") or "").upper()
            # 池内默认排除 ETF/联接；强制钉选也不应再钉联接类
            self.assertNotIn("ETF", name_u)
            self.assertNotIn("联接", row.get("name") or "")
            self.assertFalse(str(row["code"]).startswith(("15", "51", "56", "58")))

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "funds-top30.json"
            write_funds_top30(path, result)
            cached = json.loads(path.read_text(encoding="utf-8"))
            refreshed = build_funds_top30(rebuild=False, previous=cached, fetch=fake_fetch)
            self.assertEqual(len(refreshed["rows"]), expected_total)
            self.assertEqual(
                [r["code"] for r in refreshed["rows"]],
                [r["code"] for r in result["rows"]],
            )

    def test_parse_helpers(self) -> None:
        body = 'cb({"data":[{"symbol":"110022","sname":"易方达消费","zjzfe":1,"dwjz":2}]})'
        rows = parse_sina_jsonp(body)
        self.assertEqual(rows[0]["symbol"], "110022")
        nav = parse_pingzhong_nav(
            'var fS_name = "易方达消费";Data_netWorthTrend=[{"x":1784822400000,"y":2.88,"equityReturn":-1.03}];'
        )
        self.assertEqual(nav["nav"], 2.88)
        self.assertEqual(nav["dayChangePct"], -1.03)
        self.assertEqual(nav["navDate"], "2026-07-24")
        quote = parse_sina_fund_quote(
            'var hq_str_fu_110022="易方达消费行业股票,15:00:00,2.912,2.882,2.882,0,1.041,2026-07-24,2.91,1.0";',
            "110022",
        )
        self.assertEqual(quote["estimateNav"], 2.912)
        self.assertEqual(quote["prevNav"], 2.882)
        self.assertAlmostEqual(quote["estimateChange"] or 0, 0.03)
        self.assertAlmostEqual(quote["estimateChangePct"] or 0, 1.041)
        self.assertEqual(quote["estimateTime"], "2026-07-24 15:00:00")
        # empty fu_ (e.g. some bond funds)
        with self.assertRaises(ValueError):
            parse_sina_fund_quote('var hq_str_fu_000385="";', "000385")

    def test_cap_estimate_clock_at_1450(self) -> None:
        self.assertEqual(cap_estimate_clock_for_display("2026-07-24 14:49:30"), "2026-07-24 14:49:30")
        self.assertEqual(cap_estimate_clock_for_display("2026-07-24 14:50:00"), "2026-07-24 14:50:00")
        self.assertEqual(cap_estimate_clock_for_display("2026-07-24 15:00:00"), "2026-07-24 14:50:00")
        self.assertEqual(cap_estimate_clock_for_display("2026-07-27 16:04:00"), "2026-07-27 14:50:00")
        from src.funds_top30 import format_estimate_time_only

        self.assertEqual(format_estimate_time_only("2026-07-27 16:04:00 · 刷新09:35"), "2026-07-27 14:50:00")
        # time-only uses today + capped clock
        out = format_estimate_time_only("16:04:00")
        self.assertTrue(out.endswith("14:50:00"), out)

    def test_nav_vs_estimate_error_always_when_both_present(self) -> None:
        from src.funds_top30 import compute_estimate_vs_nav_error, compute_nav_vs_1450_error

        # Cross-day still computes: 估值误差 = 估值相对净值
        cross = compute_nav_vs_1450_error(
            nav=1.10,
            nav_date="2026-07-31",
            estimate_1450_nav=1.105,
            estimate_1450_date="2026-08-03",
        )
        self.assertEqual(cross["estimateErrorStatus"], "ready")
        self.assertAlmostEqual(cross["estimateErrorAbs"] or 0, 0.005)

        ready = compute_estimate_vs_nav_error(nav=1.10, estimate_nav=1.105)
        self.assertEqual(ready["estimateErrorStatus"], "ready")
        self.assertAlmostEqual(ready["estimateErrorPct"] or 0, 0.4545, places=3)

        pending = compute_estimate_vs_nav_error(nav=None, estimate_nav=1.1)
        self.assertEqual(pending["estimateErrorStatus"], "pending")

    def test_morning_uses_prev_session_1450(self) -> None:
        from src.funds_top30 import enrich_nav
        from zoneinfo import ZoneInfo

        sh = ZoneInfo("Asia/Shanghai")
        morning = datetime(2026, 8, 4, 9, 30, tzinfo=sh)

        def fake_fetch(url: str) -> str:
            if "pingzhongdata" in url:
                # Latest NAV is previous trading day 08-03
                return (
                    'var fS_name = "测试";'
                    "Data_netWorthTrend=["
                    '{"x":1784937600000,"y":1.00,"equityReturn":0.1},'
                    '{"x":1785024000000,"y":1.10,"equityReturn":1.0}'
                    "];"
                )
            if "sinajs.cn" in url:
                # Today's early quote must NOT be used before noon
                return 'var hq_str_fu_011154="测试,09:30:00,1.20,1.10,1.10,0,9.09,2026-08-04,1.2,1";'
            return ""

        prev = {
            "011154": {
                "estimate1450Date": "2026-08-03",
                "estimate1450Nav": 1.105,
                "estimate1450Frozen": True,
                "estimateChangePct": 0.45,
                "estimateNav": 1.105,
                "estimateTime": "2026-08-03 14:50:00",
            }
        }
        rows = enrich_nav(
            [{"code": "011154", "name": "测试"}],
            fetch=fake_fetch,
            previous_by_code=prev,
            now=morning,
        )
        row = rows[0]
        self.assertAlmostEqual(row["estimateNav"], 1.105)
        self.assertEqual(row["estimateTime"], "2026-08-03 14:50:00")
        self.assertAlmostEqual(row["nav"], 1.10)
        self.assertEqual(row["estimateErrorStatus"], "ready")
        self.assertAlmostEqual(row["estimateErrorAbs"] or 0, 0.005)

    def test_morning_rolls_back_same_day_nav(self) -> None:
        from src.funds_top30 import enrich_nav
        from zoneinfo import ZoneInfo

        sh = ZoneInfo("Asia/Shanghai")
        morning = datetime(2026, 8, 4, 10, 0, tzinfo=sh)
        # 2026-08-04 and 2026-08-03 midnight Shanghai as ms
        t_today = int(datetime(2026, 8, 4, tzinfo=sh).timestamp() * 1000)
        t_prev = int(datetime(2026, 8, 3, tzinfo=sh).timestamp() * 1000)

        def fake_fetch(url: str) -> str:
            if "pingzhongdata" in url:
                return (
                    'var fS_name = "测试";'
                    "Data_netWorthTrend=["
                    f'{{"x":{t_prev},"y":1.10,"equityReturn":1.0}},'
                    f'{{"x":{t_today},"y":1.12,"equityReturn":1.8}}'
                    "];"
                )
            if "sinajs.cn" in url:
                return ""
            return ""

        prev = {
            "011154": {
                "estimate1450Date": "2026-08-03",
                "estimate1450Nav": 1.105,
                "estimateTime": "2026-08-03 14:50:00",
                "estimateNav": 1.105,
            }
        }
        rows = enrich_nav(
            [{"code": "011154"}],
            fetch=fake_fetch,
            previous_by_code=prev,
            now=morning,
        )
        self.assertEqual(rows[0]["navDate"], "2026-08-03")
        self.assertAlmostEqual(rows[0]["nav"], 1.10)


if __name__ == "__main__":
    unittest.main()
