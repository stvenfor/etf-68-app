#!/usr/bin/env python3.12
"""Invert July major events → per-ETF 利好/利空/中性 matrix.

Uses the same SECTOR_BULL / SECTOR_BEAR keys as build_substantive_impact_events.py.
Optionally attaches price-window verification from etf68-impact-events-$DAY.json.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from build_substantive_impact_events import (
    MKT,
    SECTOR_BEAR,
    SECTOR_BULL,
    SECTOR_CN,
)

MODULE_ROOT = Path(__file__).resolve().parent
REPORTS = MODULE_ROOT / "reports"
SHANGHAI = ZoneInfo("Asia/Shanghai")

# July major events on the daily canvas, each may carry both bull and bear keys
# (same headline, different sector polarity — e.g. oil up vs growth discount rate).
JULY_MAJOR: list[dict[str, Any]] = [
    {
        "id": "delivery_notice",
        "date": "2026-07-01",
        "category": "交割日历",
        "title": "提示 IF/IH/IC/IM2607 最后交易日为 7/17",
        "impact": "交割月临近，移仓与到期波动升温。",
        "bullKeys": [],
        "bearKeys": [],
        "defaultDirection": "中性",
        "note": "日历提示本身不分板块；统一标中性，关注后续交割日波动。",
    },
    {
        "id": "imf",
        "date": "2026-07-08",
        "category": "外围市场",
        "title": "IMF 下调全球增长至 3.0%，上调中国至 4.6%",
        "impact": "压制全球风险偏好，强化中国相对收益叙事。",
        "bullKeys": ["imf"],
        "bearKeys": ["imf_risk"],
        "conflictPolicy": "prefer_bull",
        "defaultDirection": "中性偏多",
        "note": "主叙事：中国相对收益偏多；仅未被 imf 映射、却命中 imf_risk 的板块标利空。",
    },
    {
        "id": "imf_mideast",
        "date": "2026-07-08",
        "category": "军事地缘",
        "title": "中东战事写入 IMF 增长下修主因",
        "impact": "能源溢价抬升，成长股估值承压。",
        "bullKeys": ["hormuz"],
        "bearKeys": ["imf_risk", "hormuz_risk"],
        "conflictPolicy": "energy_bull_else_bear",
        "defaultDirection": "中性",
        "note": "资源链可获溢价；成长/科技贴现率承压。",
    },
    {
        "id": "us_strike",
        "date": "2026-07-12",
        "category": "军事地缘",
        "title": "美军宣布对伊朗新一轮打击",
        "impact": "霍尔木兹通航扰动，亚洲能源链先行定价。",
        "bullKeys": ["hormuz"],
        "bearKeys": ["hormuz_risk"],
        "conflictPolicy": "energy_bull_else_bear",
        "defaultDirection": "中性",
        "note": "油气/商品偏多；高估值成长偏空。",
    },
    {
        "id": "hormuz_close",
        "date": "2026-07-13",
        "category": "军事地缘",
        "title": "伊朗宣称霍尔木兹关闭，美方称仍开放",
        "impact": "油价波动放大，风险资产谨慎。",
        "bullKeys": ["hormuz"],
        "bearKeys": ["hormuz_risk"],
        "conflictPolicy": "energy_bull_else_bear",
        "defaultDirection": "中性",
        "note": "能源溢价 vs 风险偏好回落。",
    },
    {
        "id": "brent_week",
        "date": "2026-07-13",
        "category": "外围市场",
        "title": "布伦特周涨约 5%，WTI 突破 74 美元附近",
        "impact": "输入性通胀担忧，利率敏感成长承压。",
        "bullKeys": ["brent93", "hormuz"],
        "bearKeys": ["brent_stag"],
        "conflictPolicy": "energy_bull_else_bear",
        "defaultDirection": "中性",
        "note": "能源链利好；成长股滞胀担忧利空。",
    },
    {
        "id": "nhsa_list",
        "date": "2026-07-14",
        "category": "国内财经",
        "title": "医保局推进药品/创新药目录形式审查",
        "impact": "创新药事件驱动，准入定价仍有约束。",
        "bullKeys": ["nhsa_list"],
        "bearKeys": [],
        "defaultDirection": "中性",
        "note": "主利好医药/创新药/生物科技；其余中性。",
    },
    {
        "id": "nhsa_bd",
        "date": "2026-07-14",
        "category": "国内财经",
        "title": "上半年创新药对外授权约 1100 亿美元",
        "impact": "强化国际化叙事与主题风险偏好。",
        "bullKeys": ["nhsa_bd"],
        "bearKeys": [],
        "defaultDirection": "中性",
        "note": "主利好创新药链。",
    },
    {
        "id": "gdp",
        "date": "2026-07-15",
        "category": "国内财经",
        "title": "统计局：上半年 GDP +4.7%，制造业 +5.6%",
        "impact": "宏观韧性支撑中枢，地产仍弱。",
        "bullKeys": ["gdp"],
        "bearKeys": [],
        "defaultDirection": "中性偏多",
        "note": "多数权益板块逻辑偏多；债券偏中性偏多。",
    },
    {
        "id": "cpi",
        "date": "2026-07-15",
        "category": "国内财经",
        "title": "上半年 CPI +1.0%，核心 CPI +1.2%",
        "impact": "国内物价温和，与海外能源通胀温差。",
        "bullKeys": ["cpi"],
        "bearKeys": [],
        "defaultDirection": "中性",
        "note": "利率与债券定价偏稳；宽基/红利亦常映射。",
    },
    {
        "id": "property",
        "date": "2026-07-15",
        "category": "国内财经",
        "title": "地产投资 -18.0%，销售面积 -11.6%",
        "impact": "地产链拖累信用扩张预期。",
        "bullKeys": [],
        "bearKeys": ["property"],
        "defaultDirection": "中性",
        "note": "地产/建材/基建/银行等链上利空。",
    },
    {
        "id": "smart_factory",
        "date": "2026-07-15",
        "category": "产业政策",
        "title": "六部门启动智能工厂梯度培育",
        "impact": "利好自动化/机器人中长期预期。",
        "bullKeys": ["smart_factory"],
        "bearKeys": [],
        "defaultDirection": "中性",
        "note": "制造/机器人/装备/部分科技主题偏多。",
    },
    {
        "id": "delivery0717",
        "date": "2026-07-17",
        "category": "交割日历",
        "title": "股指期货/期权 2607 正式交割",
        "impact": "IF4555.58/IH2841.64/IC7593.39/IM7265.90；中信净加空1604手。",
        "bullKeys": [],
        "bearKeys": ["delivery0717"],
        "defaultDirection": "利空",
        "note": "交割踩踏日：高贝塔普遍承压；未映射板块亦默认偏空。",
    },
    {
        "id": "csrc",
        "date": "2026-07-20",
        "category": "国内财经",
        "title": "证监会座谈会：稳市场与强监管",
        "impact": "托底预期升温，降低极端下跌尾部风险。",
        "bullKeys": ["csrc"],
        "bearKeys": [],
        "defaultDirection": "中性偏多",
        "note": "金融/宽基/多数权益情绪修复。",
    },
    {
        "id": "citic_peak",
        "date": "2026-07-21",
        "category": "国内财经",
        "title": "稳市场资金介入，科技深 V 反弹",
        "impact": "中信四品种净加多7657手（月内峰值）。",
        "bullKeys": ["citic_peak"],
        "bearKeys": [],
        "defaultDirection": "中性偏多",
        "note": "与科技/宽基/券商共振偏多。",
    },
    {
        "id": "etf_opt",
        "date": "2026-07-22",
        "category": "交割日历",
        "title": "沪深 ETF 期权 7 月合约到期行权",
        "impact": "宽基/科创期权到期，对冲盘再平衡。",
        "bullKeys": [],
        "bearKeys": ["etf_opt"],
        "defaultDirection": "中性",
        "note": "到期扰动偏空波动；未映射标的标中性。",
    },
    {
        "id": "changxin",
        "date": "2026-07-22",
        "category": "产业政策",
        "title": "长鑫科技定档 7/27 上市",
        "impact": "存储链催化，虹吸短线流动性。",
        "bullKeys": ["changxin"],
        "bearKeys": ["changxin_siphon"],
        "conflictPolicy": "prefer_bull",
        "defaultDirection": "中性",
        "note": "存储/半导体主叙事偏多；仅虹吸映射、无长鑫催化的主题标利空。",
    },
    {
        "id": "brent93",
        "date": "2026-07-22",
        "category": "外围市场",
        "title": "布伦特升至约 93 美元",
        "impact": "能源冲击转向利率与盈利重定价。",
        "bullKeys": ["brent93"],
        "bearKeys": ["brent_stag"],
        "conflictPolicy": "energy_bull_else_bear",
        "defaultDirection": "中性",
        "note": "油气煤炭有色偏多；成长贴现率偏空。",
    },
    {
        "id": "hormuz_traffic",
        "date": "2026-07-23",
        "category": "军事地缘",
        "title": "霍尔木兹通航量显著下降",
        "impact": "供应中断风险量化，油气波动加大。",
        "bullKeys": ["hormuz"],
        "bearKeys": ["hormuz_risk"],
        "conflictPolicy": "energy_bull_else_bear",
        "defaultDirection": "中性",
        "note": "能源溢价 vs 风险资产谨慎。",
    },
    {
        "id": "mag7",
        "date": "2026-07-24",
        "category": "外围市场",
        "title": "美股七巨头单日蒸发约 8000 亿美元",
        "impact": "AI 开支与负现金流担忧向 A/H 科技传导。",
        "bullKeys": [],
        "bearKeys": ["mag7"],
        "defaultDirection": "中性",
        "note": "科技/半导体/AI/成长映射利空。",
    },
    {
        "id": "oman_fire",
        "date": "2026-07-24",
        "category": "军事地缘",
        "title": "特朗普称美军整装待发，阿曼湾开火",
        "impact": "谈判与加码打击并行，风险溢价难退。",
        "bullKeys": ["hormuz"],
        "bearKeys": ["hormuz_risk"],
        "conflictPolicy": "energy_bull_else_bear",
        "defaultDirection": "中性",
        "note": "油气避险溢价；成长风险溢价抬升。",
    },
    {
        "id": "korea",
        "date": "2026-07-24",
        "category": "外围市场",
        "title": "韩国 Kospi 盘中重挫超 6%",
        "impact": "亚洲风险偏好骤降，半导体映射承压。",
        "bullKeys": [],
        "bearKeys": ["korea"],
        "defaultDirection": "中性",
        "note": "半导体/科技/成长映射利空。",
    },
    {
        "id": "ashare_0724",
        "date": "2026-07-24",
        "category": "国内财经",
        "title": "A 股缩量至约 1.94 万亿，沪指跌 1.61%",
        "impact": "观望长鑫上市 + 外围抛售，缩量磨底。",
        "bullKeys": [],
        "bearKeys": ["ashare_0724"],
        "defaultDirection": "利空",
        "note": "当日系统性缩量下跌，未映射亦默认偏空。",
    },
    {
        "id": "waic",
        "date": "2026-07",
        "category": "产业政策",
        "title": "世界人工智能大会在上海举行",
        "impact": "国产算力反复交易，高拥挤度易受外围冲击。",
        "bullKeys": ["waic"],
        "bearKeys": [],
        "defaultDirection": "中性",
        "note": "AI/软件/通信/科创主题偏多；拥挤后亦易受 mag7 冲击。",
    },
]


def _lookup_verified(
    etf_row: dict[str, Any], keys: list[str]
) -> dict[str, Any] | None:
    pool = list(etf_row.get("positiveEvents") or []) + list(etf_row.get("negativeEvents") or [])
    by_key = {str(ev.get("sourceKey")): ev for ev in pool if ev.get("sourceKey")}
    for k in keys:
        if k in by_key:
            ev = by_key[k]
            return {
                "sourceKey": k,
                "verified": bool(ev.get("verified")),
                "windowRet": ev.get("windowRet"),
                "catalogTitle": ev.get("title"),
                "catalogImpact": ev.get("impact"),
            }
    return None


ENERGY_BULL_SECTORS = {
    "oil_gas",
    "energy",
    "energy_chemical",
    "coal",
    "gold",
    "nonferrous_metals",
    "rare_earth",
    "commodity_equity",
    "agriculture_commodity",
}


def _resolve_conflict(
    policy: str,
    sector_key: str,
    hit_bull: list[str],
    hit_bear: list[str],
) -> tuple[str, str, list[str]]:
    """Return direction, reason, verify_keys when both bull and bear keys hit."""
    both_note = f"多空键并存(利好{hit_bull}/利空{hit_bear})"
    if policy == "prefer_bull":
        reason = "；".join(MKT[k]["impact"] for k in hit_bull if k in MKT) or "主叙事偏多"
        return "利好", f"{reason}（{both_note}，按事件主叙事取利好）", hit_bull
    if policy == "prefer_bear":
        reason = "；".join(MKT[k]["impact"] for k in hit_bear if k in MKT) or "主叙事偏空"
        return "利空", f"{reason}（{both_note}，按事件主叙事取利空）", hit_bear
    if policy == "energy_bull_else_bear":
        if sector_key in ENERGY_BULL_SECTORS:
            reason = "；".join(MKT[k]["impact"] for k in hit_bull if k in MKT) or "能源/商品溢价"
            return "利好", f"{reason}（{both_note}）", hit_bull
        reason = "；".join(MKT[k]["impact"] for k in hit_bear if k in MKT) or "风险溢价抬升"
        return "利空", f"{reason}（{both_note}）", hit_bear
    return "分化", both_note, hit_bull + hit_bear


def classify_etf(
    sector_key: str,
    event: dict[str, Any],
    etf_row: dict[str, Any] | None,
) -> dict[str, Any]:
    bull_keys = list(event.get("bullKeys") or [])
    bear_keys = list(event.get("bearKeys") or [])
    sector_bull = set(SECTOR_BULL.get(sector_key, []))
    sector_bear = set(SECTOR_BEAR.get(sector_key, []))
    policy = str(event.get("conflictPolicy") or "split")

    hit_bull = [k for k in bull_keys if k in sector_bull]
    hit_bear = [k for k in bear_keys if k in sector_bear]

    if hit_bull and hit_bear:
        direction, reason, verify_keys = _resolve_conflict(policy, sector_key, hit_bull, hit_bear)
    elif hit_bull:
        direction = "利好"
        reason = "；".join(MKT[k]["impact"] for k in hit_bull if k in MKT) or "板块逻辑偏多"
        verify_keys = hit_bull
    elif hit_bear:
        direction = "利空"
        reason = "；".join(MKT[k]["impact"] for k in hit_bear if k in MKT) or "板块逻辑偏空"
        verify_keys = hit_bear
    else:
        direction = str(event.get("defaultDirection") or "中性")
        reason = str(event.get("note") or "未进入板块专属映射")
        verify_keys = bull_keys + bear_keys

    verified = None
    if etf_row is not None:
        verified = _lookup_verified(etf_row, verify_keys)

    return {
        "direction": direction,
        "reason": reason,
        "matchedBullKeys": hit_bull,
        "matchedBearKeys": hit_bear,
        "priceCheck": verified,
    }


def build(day: str) -> dict[str, Any]:
    review = json.loads((REPORTS / f"representative-technical-review-{day}.json").read_text(encoding="utf-8"))
    ctx = json.loads((MODULE_ROOT / "data" / "sector-context-2026-07-20.json").read_text(encoding="utf-8"))
    impact_path = REPORTS / f"etf68-impact-events-{day}.json"
    impact_by_code: dict[str, dict[str, Any]] = {}
    if impact_path.exists():
        impact = json.loads(impact_path.read_text(encoding="utf-8"))
        impact_by_code = {str(r["code"]): r for r in impact.get("rows", [])}

    etf_meta: list[dict[str, Any]] = []
    for r in review["rows"]:
        code = str(r["code"])
        sector = str(r["sector"])
        etf_meta.append(
            {
                "code": code,
                "name": r["name"],
                "sectorKey": sector,
                "sector": SECTOR_CN.get(sector, sector),
                "theme": str(ctx["sector_theme"].get(sector, "")),
            }
        )

    events_out: list[dict[str, Any]] = []
    for ev in JULY_MAJOR:
        etfs: list[dict[str, Any]] = []
        counts = {"利好": 0, "利空": 0, "分化": 0, "中性": 0, "中性偏多": 0, "中性偏空": 0}
        for meta in etf_meta:
            cls = classify_etf(meta["sectorKey"], ev, impact_by_code.get(meta["code"]))
            direction = cls["direction"]
            counts[direction] = counts.get(direction, 0) + 1
            wr = (cls.get("priceCheck") or {}).get("windowRet") or {}
            etfs.append(
                {
                    **meta,
                    "direction": direction,
                    "reason": cls["reason"],
                    "matchedBullKeys": cls["matchedBullKeys"],
                    "matchedBearKeys": cls["matchedBearKeys"],
                    "verified": (cls.get("priceCheck") or {}).get("verified"),
                    "retT": wr.get("retT"),
                    "cumT3": wr.get("cumT3"),
                    "barDate": wr.get("barDate"),
                }
            )
        # sort: 利好 → 分化 → 利空 → 其他
        order = {"利好": 0, "中性偏多": 1, "分化": 2, "中性": 3, "中性偏空": 4, "利空": 5}
        etfs.sort(key=lambda x: (order.get(x["direction"], 9), x["sector"], x["code"]))
        events_out.append(
            {
                "id": ev["id"],
                "date": ev["date"],
                "category": ev["category"],
                "title": ev["title"],
                "impact": ev["impact"],
                "note": ev.get("note"),
                "bullKeys": ev.get("bullKeys") or [],
                "bearKeys": ev.get("bearKeys") or [],
                "counts": {
                    "bull": counts.get("利好", 0),
                    "bear": counts.get("利空", 0),
                    "split": counts.get("分化", 0),
                    "neutral": sum(counts.get(k, 0) for k in ("中性", "中性偏多", "中性偏空")),
                    "neutralPlus": counts.get("中性偏多", 0),
                    "neutralMinus": counts.get("中性偏空", 0),
                },
                "etfs": etfs,
            }
        )

    return {
        "asOf": day,
        "generatedAt": datetime.now(SHANGHAI).isoformat(),
        "method": (
            "按 7 月重大事件 × 68 ETF 板块映射划分利好/利空/分化/中性；"
            "映射键与实质利好利空脚本一致；有窗口收益时附带价格验证。"
        ),
        "eventCount": len(events_out),
        "etfCount": len(etf_meta),
        "events": events_out,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-07-24")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    out = args.output or (REPORTS / f"etf68-event-etf-matrix-{args.date}.json")
    data = build(args.date)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} events={data['eventCount']} etfs={data['etfCount']}")
    for e in data["events"]:
        c = e["counts"]
        print(
            f"  {e['date']} {e['title'][:28]:28s} "
            f"利好{c['bull']:2d} 利空{c['bear']:2d} 分化{c['split']:2d} 中性{c['neutral']:2d}"
        )


if __name__ == "__main__":
    main()
