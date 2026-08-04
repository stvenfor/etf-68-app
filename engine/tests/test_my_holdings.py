"""Unit tests for my_holdings + position_advice + portfolio profile (no network)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.fund_portfolio_profile import (
    enrich_portfolio_profile,
    parse_hypz_industries,
    parse_pingzhong_asset_mix,
    parse_risk_level,
)
from src.my_holdings import HOLDINGS_SEED, build_my_holdings, seed_universe, write_my_holdings
from src.position_advice import (
    ADVICE_ADD,
    ADVICE_HOLD,
    ADVICE_KEEP,
    ADVICE_REDEEM,
    ADVICE_TRIM,
    decide_position_advice,
)


class SeedTest(unittest.TestCase):
    def test_seed_no_money_or_feeder(self) -> None:
        for row in HOLDINGS_SEED:
            name = str(row["name"])
            self.assertNotIn("货币", name)
            self.assertNotIn("联接", name)
            self.assertNotIn("同业存单", name)

    def test_seed_unique_codes(self) -> None:
        codes = [str(r["code"]).zfill(6) for r in HOLDINGS_SEED]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertGreaterEqual(len(codes), 20)

    def test_seed_universe_ranks(self) -> None:
        rows = seed_universe()
        self.assertEqual(len(rows), len(HOLDINGS_SEED))
        bonds = [r for r in rows if r["category"] == "bond"]
        self.assertEqual(bonds[0]["rankInCategory"], 1)
        self.assertIn("固收+", bonds[0]["themes"])


class PortfolioProfileParseTest(unittest.TestCase):
    def test_parse_hypz_top_industries(self) -> None:
        payload = {
            "Data": {
                "QuarterInfos": [
                    {
                        "JZRQ": "2026-06-30",
                        "HYPZInfo": [
                            {"HYMC": "通讯", "ZJZBL": "22.99"},
                            {"HYMC": "食品饮料", "ZJZBL": "18.1"},
                            {"HYMC": "电子", "ZJZBL": "12.5"},
                            {"HYMC": "医药", "ZJZBL": "8.2"},
                            {"HYMC": "传媒", "ZJZBL": "5.1"},
                            {"HYMC": "其他", "ZJZBL": "1.0"},
                        ],
                    },
                    {
                        "JZRQ": "2026-03-31",
                        "HYPZInfo": [{"HYMC": "旧行业", "ZJZBL": "90"}],
                    },
                ]
            }
        }
        rows, as_of = parse_hypz_industries(payload, top_n=5)
        self.assertEqual(as_of, "2026-06-30")
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["name"], "通讯")
        self.assertAlmostEqual(rows[0]["weightPct"], 22.99)

    def test_parse_asset_mix(self) -> None:
        body = (
            "var Data_assetAllocation="
            '{"series":['
            '{"name":"股票占净比","data":[80,91.31]},'
            '{"name":"债券占净比","data":[0,0]},'
            '{"name":"现金占净比","data":[10,9.28]},'
            '{"name":"净资产","type":"line","data":[1,2]}'
            '],"categories":["2026-03-31","2026-06-30"]};'
        )
        mix = parse_pingzhong_asset_mix(body)
        assert mix is not None
        self.assertEqual(mix["asOf"], "2026-06-30")
        self.assertAlmostEqual(mix["stockPct"], 91.31)
        self.assertAlmostEqual(mix["bondPct"], 0.0)
        self.assertAlmostEqual(mix["cashPct"], 9.28)

    def test_parse_risk_level(self) -> None:
        out = parse_risk_level({"Datas": {"RISKLEVEL": "4"}})
        assert out is not None
        self.assertEqual(out["riskLevel"], "R4")
        self.assertEqual(out["riskLabel"], "中高风险")
        self.assertIn("波动", out["riskNote"])


class PositionAdviceTest(unittest.TestCase):
    def test_missing_nav_hold(self) -> None:
        out = decide_position_advice({"category": "hybrid", "error": "x"})
        self.assertEqual(out["advice"], ADVICE_HOLD)

    def test_soft_dip_add(self) -> None:
        out = decide_position_advice(
            {
                "category": "hybrid",
                "nav": 1.0,
                "estimateNav": 0.99,
                "estimateChangePct": -1.2,
                "themes": ["灵活配置"],
            }
        )
        self.assertEqual(out["advice"], ADVICE_ADD)

    def test_overheat_trim(self) -> None:
        out = decide_position_advice(
            {
                "category": "bond",
                "nav": 1.0,
                "estimateNav": 1.001,
                "estimateChangePct": 0.55,
                "themes": ["固收+"],
            }
        )
        self.assertEqual(out["advice"], ADVICE_TRIM)

    def test_extreme_hot_redeem(self) -> None:
        out = decide_position_advice(
            {
                "category": "equity",
                "nav": 1.0,
                "estimateNav": 1.03,
                "estimateChangePct": 3.5,
                "themes": ["白酒", "消费"],
            }
        )
        self.assertEqual(out["advice"], ADVICE_REDEEM)

    def test_mild_keep(self) -> None:
        out = decide_position_advice(
            {
                "category": "hybrid",
                "nav": 1.0,
                "estimateNav": 1.001,
                "estimateChangePct": 0.2,
                "themes": ["股债平衡"],
            }
        )
        self.assertEqual(out["advice"], ADVICE_KEEP)


class BuildMyHoldingsTest(unittest.TestCase):
    def test_build_with_fake_fetch_includes_profile(self) -> None:
        def fake_fetch(url: str) -> str:
            if "pingzhongdata" in url:
                code = url.rsplit("/", 1)[-1].replace(".js", "")
                return (
                    f'var fS_name = "测试{code}";'
                    "var Data_netWorthTrend = "
                    '[{"x":1721779200000,"y":1.2345,"equityReturn":0.12}];'
                    "var Data_assetAllocation="
                    '{"series":['
                    '{"name":"股票占净比","data":[20.0]},'
                    '{"name":"债券占净比","data":[70.0]},'
                    '{"name":"现金占净比","data":[8.0]}'
                    '],"categories":["2026-06-30"]};'
                )
            if "HYPZ" in url:
                return json.dumps(
                    {
                        "Data": {
                            "QuarterInfos": [
                                {
                                    "JZRQ": "2026-06-30",
                                    "HYPZInfo": [
                                        {"HYMC": "制造业", "ZJZBL": "15.5"},
                                        {"HYMC": "金融业", "ZJZBL": "8.2"},
                                    ],
                                }
                            ]
                        }
                    }
                )
            if "FundMNbasicInformation" in url:
                return json.dumps({"Datas": {"RISKLEVEL": "3", "FCODE": "000000"}})
            if "hq.sinajs.cn" in url or "sinajs.cn" in url:
                return ""
            return ""

        result = build_my_holdings(fetch=fake_fetch)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["rows"]), len(HOLDINGS_SEED))
        self.assertEqual(result["source"]["portfolio"], "eastmoney_f10_hypz_asset")
        row0 = result["rows"][0]
        self.assertAlmostEqual(row0["nav"], 1.2345)
        self.assertEqual(row0["riskLevel"], "R3")
        self.assertEqual(row0["riskLabel"], "中等风险")
        self.assertAlmostEqual(row0["assetMix"]["stockPct"], 20.0)
        self.assertAlmostEqual(row0["assetMix"]["bondPct"], 70.0)
        self.assertEqual(row0["industries"][0]["name"], "制造业")
        self.assertEqual(row0["industryAsOf"], "2026-06-30")

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "my-holdings.json"
            write_my_holdings(path, result)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(loaded["rows"]), len(HOLDINGS_SEED))

    def test_profile_failure_falls_back_to_previous(self) -> None:
        previous = {
            "rows": [
                {
                    "code": "011154",
                    "riskLevel": "R4",
                    "riskLabel": "中高风险",
                    "riskNote": "净值波动较大，回撤风险更高",
                    "assetMix": {"stockPct": 90.0, "bondPct": 0.0, "cashPct": 10.0, "asOf": "2026-03-31"},
                    "industries": [{"name": "通讯", "weightPct": 20.0}],
                    "industryAsOf": "2026-03-31",
                }
            ]
        }

        def fail_fetch(url: str) -> str:
            raise RuntimeError("offline")

        rows = enrich_portfolio_profile(
            [{"code": "011154", "name": "华宝新兴消费混合C"}],
            fetch=fail_fetch,
            previous_by_code={"011154": previous["rows"][0]},
            workers=1,
        )
        self.assertEqual(rows[0]["riskLevel"], "R4")
        self.assertEqual(rows[0]["industries"][0]["name"], "通讯")
        self.assertAlmostEqual(rows[0]["assetMix"]["stockPct"], 90.0)

    def test_profile_failure_without_previous_keeps_nav_path(self) -> None:
        def fake_fetch(url: str) -> str:
            if "pingzhongdata" in url:
                return (
                    'var fS_name = "测试";'
                    "var Data_netWorthTrend = "
                    '[{"x":1721779200000,"y":1.1,"equityReturn":0.01}];'
                )
            if "HYPZ" in url or "FundMNbasicInformation" in url:
                raise RuntimeError("profile down")
            return ""

        # Only one code via temporary universe path: build still uses full seed,
        # so assert soft-fail does not crash and nav remains.
        result = build_my_holdings(fetch=fake_fetch)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["rows"]), len(HOLDINGS_SEED))
        self.assertAlmostEqual(result["rows"][0]["nav"], 1.1)


if __name__ == "__main__":
    unittest.main()
