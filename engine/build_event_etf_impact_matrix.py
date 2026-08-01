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

# 事件键 × 板块：该 ETF 板块如何被事件传导（避免复用事件级通用 impact）
KEY_SECTOR_CHANNEL: dict[str, dict[str, str]] = {
    "hormuz": {
        "oil_gas": "海峡通航扰动推升油价，油气持仓直接受益",
        "energy": "能源价格弹性抬升，能源股盈利预期修复",
        "energy_chemical": "原油成本与价差重定价，能源化工弹性放大",
        "coal": "油价溢价外溢，煤炭作为替代能源联动走强",
        "gold": "地缘避险升温，黄金定价获支撑",
        "nonferrous_metals": "商品风险溢价抬升，有色金属联动受益",
        "rare_earth": "战略资源避险溢价，稀土主题获事件弹性",
        "commodity_equity": "大宗商品风险溢价抬升，商品股受益",
        "agriculture_commodity": "能源成本与农产品通胀预期抬升，农产品主题获溢价",
        "_default": "{sector}作为资源/商品链，受海峡扰动带来的溢价传导",
    },
    "hormuz_risk": {
        "semiconductor": "地缘风险偏好回落，高估值半导体贴现率承压",
        "electronics": "避险情绪压制电子成长股估值",
        "consumer_electronics": "风险溢价抬升，消费电子成长定价承压",
        "artificial_intelligence": "避险压制 AI/算力等高波动主题",
        "star_50": "科创高估值对风险溢价最敏感，承压优先",
        "software": "成长股贴现率抬升，软件估值承压",
        "communication": "科技映射回落，通信设备主题承压",
        "broad_tech": "科技宽基贝塔承压，风险偏好下降",
        "technology": "科技成长贴现率抬升，主题承压",
        "growth_board": "创业板高贝塔在避险中先行回撤",
        "robotics": "成长制造主题风险偏好回落",
        "battery": "新能源成长估值对风险溢价敏感",
        "new_energy": "新能源成长贴现率承压",
        "new_energy_vehicle": "高估值成长车链在避险中承压",
        "solar": "成长新能源估值承压",
        "smart_driving": "智能驾驶成长主题风险偏好回落",
        "innovative_drug": "成长医药估值对风险溢价敏感",
        "biotechnology": "生物科技高波动主题避险承压",
        "_default": "{sector}属成长/高波动主题，地缘风险溢价抬升时承压",
    },
    "brent93": {
        "oil_gas": "布伦特上行直接抬升油气价格弹性与盈利预期",
        "energy": "油价中枢上移，能源板块盈利弹性释放",
        "energy_chemical": "原油价格上行，能源化工价差与库存重估",
        "coal": "油气溢价外溢，煤炭联动定价走强",
        "gold": "能源通胀预期抬升，黄金抗通胀叙事强化",
        "nonferrous_metals": "商品通胀溢价，有色金属联动受益",
        "rare_earth": "商品价格弹性抬升，稀土主题联动",
        "commodity_equity": "大宗商品价格中枢上移，商品股受益",
        "agriculture_commodity": "能源成本推升农产品通胀预期",
        "_default": "{sector}处资源/商品链，油价上行带来价格弹性",
    },
    "brent_stag": {
        "semiconductor": "高油价抬升滞胀担忧，半导体成长贴现率承压",
        "electronics": "利率敏感电子成长股估值承压",
        "artificial_intelligence": "滞胀担忧压制 AI 成长估值",
        "star_50": "科创高估值对滞胀/利率最敏感",
        "software": "成长软件贴现率承压",
        "communication": "科技成长映射回落",
        "broad_tech": "科技宽基在滞胀叙事下承压",
        "technology": "科技成长贴现率抬升",
        "growth_board": "创业板成长贝塔对滞胀敏感",
        "battery": "新能源成长估值承压",
        "new_energy": "新能源成长贴现率承压",
        "new_energy_vehicle": "成长车链估值对利率敏感",
        "solar": "光伏成长估值承压",
        "smart_driving": "智能驾驶成长主题承压",
        "robotics": "高端制造成长估值承压",
        "_default": "{sector}属利率敏感成长，高油价滞胀担忧下估值承压",
    },
    "imf": {
        "broad_market": "中国增速上修强化境内相对收益，宽基风险偏好修复",
        "large_cap": "宏观相对优势叙事支撑大盘蓝筹",
        "bank": "境内宏观韧性叙事利好银行基本面预期",
        "securities": "风险偏好修复利好券商成交与情绪",
        "oil_gas": "中国需求韧性叙事支撑能源需求预期",
        "gold": "全球增长下修下，境内资产与黄金相对吸引力上升",
        "_default": "中国相对收益叙事强化，{sector}作为境内主题风险偏好修复",
    },
    "imf_risk": {
        "semiconductor": "全球增长下修与二次通胀风险压制半导体估值",
        "growth_board": "全球风险资产承压，创业板高贝塔先行",
        "technology": "全球风险偏好回落压制科技主题",
        "credit_bond": "全球风险资产波动外溢，信用债情绪谨慎",
        "government_bond": "海外滞胀担忧扰动利率定价预期",
        "_default": "全球增长下修与通胀风险压制{sector}风险资产定价",
    },
    "nhsa_list": {
        "healthcare": "医保/创新药目录审查直接催化医药持仓",
        "innovative_drug": "创新药准入节奏事件，创新药 ETF 直接受益",
        "biotechnology": "创新药政策节奏外溢至生物科技主题",
        "_default": "医保目录政策节奏利好{sector}医药链",
    },
    "nhsa_bd": {
        "healthcare": "创新药对外授权强化医药国际化叙事",
        "innovative_drug": "BD 金额验证创新药出海逻辑，主题风险偏好抬升",
        "biotechnology": "创新药出海叙事外溢至生物科技",
        "_default": "创新药国际化叙事利好{sector}",
    },
    "gdp": {
        "broad_market": "GDP 韧性支撑指数中枢，宽基贝塔获宏观背书",
        "intelligent_manufacturing": "制造业 +5.6% 直接利好智能制造主题",
        "machinery": "制造业景气支撑机械装备需求预期",
        "robotics": "制造韧性强化机器人/自动化中长期需求",
        "advanced_equipment": "制造景气利好高端装备资本开支预期",
        "bank": "宏观韧性支撑银行资产质量与信贷预期",
        "steel": "制造与投资韧性支撑钢铁需求预期",
        "_default": "宏观韧性支撑{sector}中枢与景气预期",
    },
    "cpi": {
        "government_bond": "物价温和利于利率稳定，国债定价环境友好",
        "credit_bond": "通胀温和降低利率波动，信用债定价偏稳",
        "convertible_bond": "利率环境稳定，转债估值波动收敛",
        "dividend_factor": "物价温和利于红利资产相对吸引力",
        "bank": "温和通胀利于银行净息差与资产质量预期",
        "broad_market": "通胀温和降低宏观扰动，宽基定价环境改善",
        "_default": "国内物价温和，{sector}利率敏感定价环境偏稳",
    },
    "property": {
        "real_estate": "地产投资与销售双弱，房地产 ETF 基本面直接承压",
        "building_materials": "地产销售疲弱拖累建材需求预期",
        "infrastructure": "地产链信用收缩外溢，基建相关预期谨慎",
        "bank": "地产基本面偏弱拖累银行地产相关资产质量预期",
        "steel": "地产需求疲弱拖累钢铁终端需求",
        "state_owned_enterprise": "地产链拖累部分国企持仓景气预期",
        "dividend_factor": "地产链信用担忧外溢，红利资产情绪谨慎",
        "_default": "地产基本面偏弱，拖累{sector}链上需求与信用预期",
    },
    "smart_factory": {
        "robotics": "智能工厂培育直接利好机器人/自动化渗透预期",
        "intelligent_manufacturing": "智能工厂政策直达智能制造主题",
        "machinery": "工厂自动化资本开支预期抬升，机械受益",
        "advanced_equipment": "高端装备国产替代与智能工厂共振",
        "semiconductor": "智能工厂拉动工业半导体/工控芯片需求预期",
        "electronics": "工业电子与自动化器件需求预期扩散",
        "communication": "工业互联与工厂数字化拉动通信设备",
        "new_materials": "高端制造材料需求预期扩散",
        "_default": "智能工厂政策扩散，利好{sector}自动化/装备逻辑",
    },
    "delivery0717": {
        "broad_market": "股指交割日系统性大跌，宽基贝塔直接回撤",
        "growth_board": "交割踩踏日高贝塔创业板承压更甚",
        "semiconductor": "交割日高波动，半导体等高贝塔主题回撤",
        "securities": "交割日波动抬升，券商贝塔与情绪承压",
        "star_50": "交割日科创高贝塔普遍回撤",
        "_default": "股指交割日系统性回撤，{sector}高贝塔持仓承压",
    },
    "csrc": {
        "securities": "稳市场政策直接利好券商成交与风险偏好",
        "securities_insurance": "金融情绪修复，证券保险主题受益",
        "bank": "稳市场托底降低极端尾部风险，银行情绪修复",
        "broad_market": "政策托底预期升温，宽基尾部风险下降",
        "large_cap": "稳市场利好大盘蓝筹风险偏好",
        "_default": "证监会稳市场托底，{sector}风险偏好与情绪修复",
    },
    "citic_peak": {
        "securities": "期货净加多与稳市场资金共振，券商情绪修复",
        "broad_market": "机构净加多峰值支撑宽基风险偏好",
        "growth_board": "科技深 V 与机构加多共振，创业板弹性释放",
        "artificial_intelligence": "科技反弹窗口，AI 主题弹性优先",
        "semiconductor": "科技深 V 反弹，半导体主题联动",
        "star_50": "科创反弹窗口与机构加多共振",
        "_default": "机构净加多与科技反弹共振，利好{sector}风险偏好",
    },
    "etf_opt": {
        "broad_market": "宽基 ETF 期权到期，对冲盘再平衡抬升波动",
        "star_50": "科创相关期权到期扰动，科创 ETF 波动抬升",
        "growth_board": "期权到期对冲扰动创业板波动",
        "large_cap": "宽基期权到期再平衡，大盘波动抬升",
        "_default": "ETF 期权到期再平衡扰动，{sector}波动抬升",
    },
    "changxin": {
        "semiconductor": "长鑫上市催化存储链，半导体 ETF 直接受益",
        "electronics": "存储事件外溢至电子产业链定价",
        "consumer_electronics": "存储涨价预期外溢消费电子成本与景气叙事",
        "star_50": "长鑫科创板上市直接催化科创存储映射",
        "_default": "长鑫存储事件催化，利好{sector}存储/半导体映射",
    },
    "changxin_siphon": {
        "growth_board": "长鑫上市前虹吸双创流动性，创业板成交分流",
        "artificial_intelligence": "非存储主题资金被分流，AI 短线承压",
        "software": "双创流动性虹吸，软件主题短线承压",
        "small_cap": "小盘流动性被存储事件分流",
        "broad_tech": "科技内部虹吸，非存储科技主题承压",
        "_default": "长鑫上市虹吸流动性，非存储的{sector}主题短线承压",
    },
    "mag7": {
        "semiconductor": "美股科技巨头暴跌外溢，A 股半导体映射承压",
        "artificial_intelligence": "AI 开支担忧直接冲击国产算力/AI 主题",
        "electronics": "全球科技抛售外溢电子产业链",
        "star_50": "科创科技映射美股科技回撤",
        "software": "全球科技风险偏好回落压制软件估值",
        "communication": "AI/光通信映射美股科技抛售",
        "broad_tech": "科技宽基承接美股科技抛售外溢",
        "technology": "科技主题映射美股七巨头回撤",
        "internet": "全球科技风险偏好回落压制互联网估值",
        "growth_board": "创业板科技贝塔映射外围科技抛售",
        "consumer_electronics": "消费电子映射全球科技抛售",
        "smart_driving": "智能驾驶成长主题映射科技抛售",
        "_default": "美股科技抛售外溢，{sector}科技/成长映射承压",
    },
    "korea": {
        "semiconductor": "韩国半导体股灾直接冲击 A 股半导体风险偏好",
        "electronics": "亚洲电子风险偏好骤降，电子主题承压",
        "consumer_electronics": "韩股电子抛售外溢消费电子",
        "star_50": "亚洲科技股灾冲击科创映射",
        "artificial_intelligence": "亚洲科技风险偏好骤降压制 AI 主题",
        "broad_tech": "亚洲科技抛售冲击科技宽基",
        "technology": "韩股科技股灾外溢科技主题",
        "growth_board": "亚洲风险偏好骤降冲击创业板科技贝塔",
        "_default": "韩国科技股灾外溢，{sector}半导体/科技映射承压",
    },
    "ashare_0724": {
        "broad_market": "A 股缩量下跌，宽基系统性风险偏好回落",
        "growth_board": "缩量磨底下创业板高波动主题承压",
        "semiconductor": "观望长鑫+外围抛售，半导体短线承压",
        "securities": "成交萎缩直接利空券商佣金与情绪",
        "star_50": "缩量下跌中科创高贝塔承压",
        "_default": "A 股缩量下跌，{sector}风险偏好与流动性承压",
    },
    "waic": {
        "artificial_intelligence": "AI 大会直接催化国产算力/应用主题交易",
        "software": "AI 应用落地预期强化软件主题",
        "communication": "算力网络与光通信受益 AI 大会叙事",
        "star_50": "科创算力映射 AI 大会交易活跃",
        "internet": "AI 应用叙事强化互联网主题风险偏好",
        "smart_driving": "AI+智驾叙事共振",
        "media": "AI 内容/传媒应用主题获关注",
        "gaming": "AI+游戏应用叙事获事件窗口",
        "broad_tech": "科技宽基承接 AI 大会主题交易",
        "semiconductor": "算力芯片映射 AI 大会催化",
        "_default": "AI 大会催化窗口，利好{sector}算力/应用映射",
    },
    "ic_tax": {
        "semiconductor": "集成电路税收优惠确认半导体全链条政策连续性",
        "electronics": "集成电路政策连续性利好电子产业链",
        "software": "软件税收优惠清单利好软件主题",
        "star_50": "科创半导体政策连续性强化",
        "_default": "集成电路/软件税收政策连续性利好{sector}",
    },
    "auto_std": {
        "new_energy_vehicle": "汽车标准化要点直接聚焦新能源车与智能网联",
        "battery": "车规与新能源车标准推进利好电池链",
        "smart_driving": "智能网联标准推进直接利好智驾主题",
        "new_energy": "新能源车政策聚焦外溢新能源主题",
        "solar": "新能源车/清洁能源政策叙事外溢光伏",
        "robotics": "汽车智能化拉动自动化/机器人应用预期",
        "_default": "汽车智能化标准推进，利好{sector}车链映射",
    },
    "no1_doc": {
        "agriculture": "中央一号文件强化农业综合生产能力中长期背景",
        "livestock": "乡村振兴与农业产能政策利好畜牧主题",
        "agriculture_commodity": "农业政策背景支撑农产品主题",
        "_default": "一号文件农业政策背景利好{sector}",
    },
    "housing": {
        "real_estate": "住房工作部署偏稳，地产政策预期边际改善",
        "building_materials": "保障交付与因城施策，建材需求预期边际稳定",
        "infrastructure": "住房与城建政策外溢基建相关预期",
        "bank": "地产政策托底降低银行地产尾部风险",
        "_default": "住房政策偏稳，{sector}地产链预期边际改善",
    },
    "energy_std": {
        "oil_gas": "能源行业标准推进，油气规范化与中长期景气叙事",
        "coal": "煤炭行业标准化推进，中长期定价机制完善",
        "energy": "能源标准立项强化能源主题政策背景",
        "energy_chemical": "能源化工标准化推进，产业秩序预期改善",
        "_default": "能源标准化政策背景利好{sector}",
    },
    "retail": {
        "consumer": "社零温和修复，消费主题相对韧性",
        "food_beverage": "食品饮料社零偏强，主题直接受益",
        "liquor": "消费修复叙事支撑白酒风险偏好",
        "agriculture": "食品消费韧性外溢农业主题",
        "livestock": "食品消费韧性支撑畜牧需求预期",
        "_default": "消费温和修复，利好{sector}消费映射",
    },
}


def _channel(key: str, sector_key: str, sector_cn: str) -> str:
    """板块专属传导句；无专属则用默认模板填入板块名。"""
    table = KEY_SECTOR_CHANNEL.get(key) or {}
    if sector_key in table:
        return table[sector_key]
    tmpl = table.get("_default") or (MKT.get(key) or {}).get("impact") or f"事件键 {key} 映射至{{sector}}"
    return tmpl.format(sector=sector_cn or sector_key)


def _format_channels(keys: list[str], sector_key: str, sector_cn: str) -> str:
    parts = [_channel(k, sector_key, sector_cn) for k in keys]
    # 去重保序
    seen: set[str] = set()
    uniq: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return "；".join(uniq)


def _etf_reason_prefix(name: str, sector_cn: str) -> str:
    label = (name or "").strip() or "该ETF"
    sec = (sector_cn or "").strip()
    if sec:
        return f"「{label}」属{sec}"
    return f"「{label}」"


def _neutral_reason(
    name: str,
    sector_cn: str,
    event: dict[str, Any],
    direction: str,
) -> str:
    """中性依据：说明本 ETF 为何未进映射，而不是复用事件对其他板块的 note。"""
    prefix = _etf_reason_prefix(name, sector_cn)
    impact = str(event.get("impact") or "").strip().rstrip("。")
    sec = (sector_cn or "该板块").strip()
    if impact:
        return (
            f"{prefix}：事件主叙事「{impact}」；"
            f"{sec}未进入本事件专属映射，与该ETF无直接传导，标{direction}"
        )
    return f"{prefix}：本事件无直接板块映射，标{direction}"


def _resolve_conflict(
    policy: str,
    sector_key: str,
    sector_cn: str,
    name: str,
    hit_bull: list[str],
    hit_bear: list[str],
) -> tuple[str, str, list[str]]:
    """Return direction, reason, verify_keys when both bull and bear keys hit."""
    prefix = _etf_reason_prefix(name, sector_cn)
    bull_txt = _format_channels(hit_bull, sector_key, sector_cn)
    bear_txt = _format_channels(hit_bear, sector_key, sector_cn)
    if policy == "prefer_bull":
        reason = f"{prefix}：{bull_txt}（同事件亦有利空映射，按主叙事取利好）"
        return "利好", reason, hit_bull
    if policy == "prefer_bear":
        reason = f"{prefix}：{bear_txt}（同事件亦有利好映射，按主叙事取利空）"
        return "利空", reason, hit_bear
    if policy == "energy_bull_else_bear":
        if sector_key in ENERGY_BULL_SECTORS:
            reason = f"{prefix}：{bull_txt}（同事件成长侧承压，本板块取能源/商品溢价）"
            return "利好", reason, hit_bull
        reason = f"{prefix}：{bear_txt}（同事件能源侧溢价，本板块取风险溢价/贴现率承压）"
        return "利空", reason, hit_bear
    reason = f"{prefix}：多空并存——利好侧 {bull_txt}；利空侧 {bear_txt}"
    return "分化", reason, hit_bull + hit_bear


def classify_etf(
    sector_key: str,
    event: dict[str, Any],
    etf_row: dict[str, Any] | None,
    *,
    name: str = "",
    sector_cn: str = "",
) -> dict[str, Any]:
    bull_keys = list(event.get("bullKeys") or [])
    bear_keys = list(event.get("bearKeys") or [])
    sector_bull = set(SECTOR_BULL.get(sector_key, []))
    sector_bear = set(SECTOR_BEAR.get(sector_key, []))
    policy = str(event.get("conflictPolicy") or "split")
    sector_label = sector_cn or SECTOR_CN.get(sector_key, sector_key)

    hit_bull = [k for k in bull_keys if k in sector_bull]
    hit_bear = [k for k in bear_keys if k in sector_bear]

    if hit_bull and hit_bear:
        direction, reason, verify_keys = _resolve_conflict(
            policy, sector_key, sector_label, name, hit_bull, hit_bear
        )
    elif hit_bull:
        direction = "利好"
        channel = _format_channels(hit_bull, sector_key, sector_label)
        reason = f"{_etf_reason_prefix(name, sector_label)}：{channel}"
        verify_keys = hit_bull
    elif hit_bear:
        direction = "利空"
        channel = _format_channels(hit_bear, sector_key, sector_label)
        reason = f"{_etf_reason_prefix(name, sector_label)}：{channel}"
        verify_keys = hit_bear
    else:
        direction = str(event.get("defaultDirection") or "中性")
        # 日历类无多空键：用事件 note，但仍带 ETF 前缀
        if not bull_keys and not bear_keys:
            note = str(event.get("note") or "日历/提示类事件，不分板块")
            reason = f"{_etf_reason_prefix(name, sector_label)}：{note}"
        else:
            reason = _neutral_reason(name, sector_label, event, direction)
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
            cls = classify_etf(
                meta["sectorKey"],
                ev,
                impact_by_code.get(meta["code"]),
                name=str(meta["name"]),
                sector_cn=str(meta["sector"]),
            )
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
            "依据按「ETF名称+板块」写专属传导逻辑，不再复用事件级通用 impact；"
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
