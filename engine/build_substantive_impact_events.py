#!/usr/bin/env python3.12
"""Build per-ETF substantive 利好 / 利空 events (default 10 each) with price gates.

实质利好:
  - logic bullish + anti sell-the-news (reject ret_T<=-2% or cumT3<=-3%)
  - accept if ret_T>=0 or cumT3>=0
  - hard-exclude delivery0717/mag7/korea from 利好; changxin only if window >0

实质利空:
  - logic bearish or risk-off mapping + anti fake-negative (reject ret_T>=+2% or cumT3>=+3%)
  - accept if ret_T<=0 or cumT3<=0

Fill to N with ETF-specific price-confirmed shock days when curated pool is short.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from src.market_data import DailyBar, PublicMarketDataProvider

MODULE_ROOT = Path(__file__).resolve().parent
REPORTS = MODULE_ROOT / "reports"
SHANGHAI = ZoneInfo("Asia/Shanghai")
TARGET_N = 10
LOOKBACK_BARS = 180

SECTOR_CN = {
    "advanced_equipment": "高端装备",
    "agriculture": "农业",
    "agriculture_commodity": "农产品",
    "artificial_intelligence": "人工智能",
    "bank": "银行",
    "battery": "电池",
    "biotechnology": "生物科技",
    "broad_market": "宽基",
    "broad_tech": "科技宽基",
    "building_materials": "建材",
    "cashflow_factor": "现金流因子",
    "coal": "煤炭",
    "commodity_equity": "商品股",
    "communication": "通信",
    "consumer": "消费",
    "consumer_electronics": "消费电子",
    "convertible_bond": "可转债",
    "credit_bond": "信用债",
    "defense": "军工",
    "dividend_factor": "红利",
    "education": "教育",
    "electric_utility": "电力公用",
    "electronics": "电子",
    "energy": "能源",
    "energy_chemical": "能源化工",
    "food_beverage": "食品饮料",
    "gaming": "游戏",
    "gold": "黄金",
    "government_bond": "国债",
    "growth_board": "创业板",
    "healthcare": "医药",
    "infrastructure": "基建",
    "innovative_drug": "创新药",
    "intelligent_manufacturing": "智能制造",
    "internet": "互联网",
    "large_cap": "大盘",
    "liquor": "白酒",
    "livestock": "畜牧",
    "machinery": "机械",
    "media": "传媒",
    "mid_cap": "中盘",
    "mid_cap_factor": "中盘因子",
    "new_energy": "新能源",
    "new_energy_vehicle": "新能源汽车",
    "new_materials": "新材料",
    "nonferrous_metals": "有色金属",
    "oil_gas": "油气",
    "rare_earth": "稀土",
    "real_estate": "房地产",
    "robotics": "机器人",
    "satellite": "卫星",
    "securities": "证券",
    "securities_insurance": "证券保险",
    "semiconductor": "半导体",
    "small_cap": "小盘",
    "smart_driving": "智能驾驶",
    "software": "软件",
    "solar": "光伏",
    "star_50": "科创50",
    "state_owned_enterprise": "国企",
    "steel": "钢铁",
    "technology": "科技",
}

# Named catalog. `side` hints preferred polarity; filters still decide.
MKT: dict[str, dict[str, str]] = {
    "imf": {"date": "2026-07-08", "title": "IMF下调全球增速、上调中国增速", "impact": "中国相对收益叙事强化，境内资产风险偏好修复。", "logic": "中性偏多"},
    "imf_risk": {"date": "2026-07-08", "title": "IMF警示战事与二次通胀风险", "impact": "全球增长下修与通胀风险压制风险资产估值。", "logic": "利空"},
    "hormuz": {"date": "2026-07-13", "title": "霍尔木兹通航预期扰动", "impact": "能源溢价抬升，油气/煤炭等资源主题获事件溢价。", "logic": "利好"},
    "hormuz_risk": {"date": "2026-07-13", "title": "地缘冲突抬升风险溢价", "impact": "风险偏好下降，成长/科技等高估值板块承压。", "logic": "利空"},
    "delivery0116": {"date": "2026-01-16", "title": "1月股指期货交割日", "impact": "到期扰动抬升波动，高贝塔主题易承压。", "logic": "利空"},
    "delivery0224": {"date": "2026-02-24", "title": "2月股指期货交割日（春节顺延）", "impact": "节后首个交割窗口，仓位再平衡扰动。", "logic": "利空"},
    "delivery0320": {"date": "2026-03-20", "title": "3月股指期货交割日", "impact": "交割日波动抬升，风险资产易回撤。", "logic": "利空"},
    "delivery0417": {"date": "2026-04-17", "title": "4月股指期货交割日", "impact": "交割扰动压制短线风险偏好。", "logic": "利空"},
    "delivery0515": {"date": "2026-05-15", "title": "5月股指期货交割日", "impact": "到期再平衡，高波动主题承压。", "logic": "利空"},
    "delivery0622": {"date": "2026-06-22", "title": "6月股指期货交割日（端午顺延）", "impact": "交割窗口波动，权益贝塔承压或分化。", "logic": "利空"},
    "delivery0717": {"date": "2026-07-17", "title": "7月股指期货交割日大跌", "impact": "上证-3.05%、沪深300-3.60%，高贝塔普遍回撤。", "logic": "利空"},
    "csrc": {"date": "2026-07-20", "title": "证监会座谈会强调稳市场", "impact": "政策托底预期升温，金融与宽基情绪修复。", "logic": "利好"},
    "mag7": {"date": "2026-07-24", "title": "美股七巨头市值蒸发约8000亿美元", "impact": "AI开支与负现金流担忧外溢，科技映射承压。", "logic": "利空"},
    "changxin": {"date": "2026-07-22", "title": "长鑫科技定档科创板上市", "impact": "存储产业链事件催化（需价格验证）。", "logic": "利好"},
    "changxin_siphon": {"date": "2026-07-22", "title": "长鑫上市前流动性虹吸", "impact": "双创成交萎缩，非存储主题资金被分流。", "logic": "利空"},
    "korea": {"date": "2026-07-24", "title": "韩国Kospi重挫并启动SIDECAR", "impact": "亚洲半导体风险偏好骤降。", "logic": "利空"},
    "gdp": {"date": "2026-07-15", "title": "上半年GDP同比+4.7%、制造业+5.6%", "impact": "宏观韧性支撑指数中枢与制造主题。", "logic": "中性偏多"},
    "cpi": {"date": "2026-07-15", "title": "上半年CPI+1.0%、核心CPI+1.2%", "impact": "物价温和利于利率与债券定价稳定。", "logic": "中性偏多"},
    "property": {"date": "2026-07-15", "title": "上半年地产投资同比-18%", "impact": "地产基本面偏弱，拖累地产链与相关信用预期。", "logic": "利空"},
    "nhsa_list": {"date": "2026-07-14", "title": "医保目录/创新药目录形式审查", "impact": "创新药政策节奏催化。", "logic": "利好"},
    "nhsa_bd": {"date": "2026-07-14", "title": "创新药对外授权约1100亿美元", "impact": "国际化叙事强化主题风险偏好。", "logic": "利好"},
    "smart_factory": {"date": "2026-07-15", "title": "智能工厂梯度培育启动", "impact": "自动化/机器人/高端装备应用预期扩散。", "logic": "利好"},
    "auto_std": {"date": "2026-06-12", "title": "2026汽车标准化工作要点", "impact": "新能源车/智能网联/汽车芯片方向获政策聚焦。", "logic": "利好"},
    "ic_tax": {"date": "2026-04-09", "title": "集成电路/软件税收优惠清单通知", "impact": "半导体全链条政策连续性确认。", "logic": "利好"},
    "no1_doc": {"date": "2026-02-03", "title": "2026中央一号文件", "impact": "农业综合生产能力与乡村振兴中长期背景。", "logic": "利好"},
    "housing": {"date": "2026-01-16", "title": "住建部2026住房工作部署", "impact": "因城施策与保障交付，偏稳定转型。", "logic": "中性偏多"},
    "energy_std": {"date": "2026-03-24", "title": "能源行业标准计划立项", "impact": "煤炭油气与新能源标准化推进。", "logic": "中性偏多"},
    "retail": {"date": "2026-07-15", "title": "上半年社零+1.3%，食品饮料偏强", "impact": "消费温和修复，食品饮料相对韧性。", "logic": "中性偏多"},
    "brent93": {"date": "2026-07-22", "title": "布伦特原油升至约93美元", "impact": "能源链价格弹性抬升。", "logic": "利好"},
    "brent_stag": {"date": "2026-07-22", "title": "高油价抬升滞胀担忧", "impact": "利率敏感成长板块贴现率承压。", "logic": "利空"},
    "waic": {"date": "2026-07-15", "title": "世界人工智能大会催化窗口", "impact": "国产算力/应用主题交易活跃。", "logic": "利好"},
    "citic_peak": {"date": "2026-07-21", "title": "中信期货净加多7657手峰值", "impact": "与稳市场资金、科技深V共振。", "logic": "利好"},
    "ashare_0724": {"date": "2026-07-24", "title": "A股缩量下跌、沪指跌1.61%", "impact": "风险偏好回落，成长与高波动主题承压。", "logic": "利空"},
    "etf_opt": {"date": "2026-07-22", "title": "ETF期权到期行权日", "impact": "对冲盘再平衡抬升宽基波动。", "logic": "利空"},
}

BULL_EXCLUDE = {"delivery0116", "delivery0224", "delivery0320", "delivery0417", "delivery0515", "delivery0622", "delivery0717", "mag7", "korea", "property", "hormuz_risk", "imf_risk", "brent_stag", "changxin_siphon", "ashare_0724", "etf_opt"}

SECTOR_BULL: dict[str, list[str]] = {
    "credit_bond": ["csrc", "cpi", "gdp", "citic_peak", "imf", "housing"],
    "government_bond": ["cpi", "gdp", "csrc", "imf", "housing"],
    "convertible_bond": ["csrc", "gdp", "cpi", "citic_peak", "imf"],
    "oil_gas": ["hormuz", "brent93", "imf", "energy_std", "gdp"],
    "energy": ["hormuz", "brent93", "imf", "energy_std", "gdp"],
    "energy_chemical": ["hormuz", "brent93", "imf", "energy_std", "gdp"],
    "coal": ["hormuz", "brent93", "energy_std", "imf", "gdp"],
    "electric_utility": ["smart_factory", "gdp", "csrc", "imf", "energy_std"],
    "bank": ["csrc", "gdp", "cpi", "citic_peak", "imf"],
    "securities": ["csrc", "citic_peak", "gdp", "imf", "cpi"],
    "securities_insurance": ["csrc", "citic_peak", "gdp", "imf", "cpi"],
    "cashflow_factor": ["gdp", "csrc", "cpi", "citic_peak", "imf"],
    "dividend_factor": ["gdp", "csrc", "cpi", "imf", "citic_peak"],
    "broad_market": ["imf", "csrc", "gdp", "citic_peak", "cpi"],
    "large_cap": ["csrc", "gdp", "citic_peak", "imf", "cpi"],
    "growth_board": ["csrc", "citic_peak", "gdp", "smart_factory", "waic"],
    "small_cap": ["csrc", "citic_peak", "gdp", "imf", "smart_factory"],
    "mid_cap": ["csrc", "gdp", "citic_peak", "imf", "cpi"],
    "mid_cap_factor": ["csrc", "gdp", "cpi", "imf", "citic_peak"],
    "state_owned_enterprise": ["gdp", "csrc", "citic_peak", "imf", "cpi"],
    "healthcare": ["nhsa_list", "nhsa_bd", "gdp", "imf", "csrc"],
    "innovative_drug": ["nhsa_list", "nhsa_bd", "gdp", "imf", "csrc"],
    "biotechnology": ["nhsa_bd", "nhsa_list", "imf", "gdp", "csrc"],
    "agriculture": ["no1_doc", "retail", "gdp", "imf", "csrc"],
    "agriculture_commodity": ["hormuz", "no1_doc", "imf", "retail", "gdp"],
    "livestock": ["no1_doc", "retail", "gdp", "imf", "csrc"],
    "consumer": ["retail", "gdp", "cpi", "csrc", "imf"],
    "liquor": ["retail", "gdp", "cpi", "csrc", "imf"],
    "food_beverage": ["retail", "gdp", "cpi", "csrc", "imf"],
    "infrastructure": ["housing", "gdp", "smart_factory", "csrc", "imf"],
    "building_materials": ["housing", "gdp", "smart_factory", "csrc", "imf"],
    "real_estate": ["housing", "csrc", "gdp", "cpi", "imf"],
    "semiconductor": ["ic_tax", "changxin", "smart_factory", "gdp", "waic"],
    "electronics": ["ic_tax", "changxin", "smart_factory", "gdp", "waic"],
    "consumer_electronics": ["ic_tax", "changxin", "gdp", "smart_factory", "waic"],
    "artificial_intelligence": ["waic", "smart_factory", "gdp", "csrc", "citic_peak"],
    "star_50": ["changxin", "waic", "ic_tax", "smart_factory", "citic_peak"],
    "internet": ["waic", "imf", "gdp", "csrc", "citic_peak"],
    "software": ["waic", "smart_factory", "ic_tax", "gdp", "csrc"],
    "gaming": ["waic", "retail", "gdp", "csrc", "imf"],
    "media": ["waic", "gdp", "csrc", "imf", "citic_peak"],
    "education": ["waic", "gdp", "csrc", "imf", "retail"],
    "communication": ["waic", "smart_factory", "gdp", "csrc", "citic_peak"],
    "broad_tech": ["waic", "imf", "smart_factory", "csrc", "citic_peak"],
    "technology": ["imf", "waic", "csrc", "gdp", "citic_peak"],
    "robotics": ["smart_factory", "gdp", "csrc", "imf", "auto_std"],
    "machinery": ["smart_factory", "gdp", "csrc", "imf", "auto_std"],
    "intelligent_manufacturing": ["smart_factory", "gdp", "auto_std", "csrc", "imf"],
    "advanced_equipment": ["smart_factory", "gdp", "csrc", "imf", "auto_std"],
    "new_materials": ["smart_factory", "gdp", "csrc", "imf", "auto_std"],
    "defense": ["smart_factory", "gdp", "csrc", "imf", "citic_peak"],
    "satellite": ["smart_factory", "gdp", "csrc", "imf", "waic"],
    "battery": ["auto_std", "gdp", "smart_factory", "imf", "csrc"],
    "new_energy": ["auto_std", "gdp", "smart_factory", "imf", "csrc"],
    "new_energy_vehicle": ["auto_std", "gdp", "smart_factory", "csrc", "imf"],
    "solar": ["auto_std", "gdp", "smart_factory", "imf", "csrc"],
    "smart_driving": ["auto_std", "waic", "gdp", "smart_factory", "csrc"],
    "gold": ["hormuz", "imf", "brent93", "cpi", "gdp"],
    "nonferrous_metals": ["hormuz", "brent93", "imf", "gdp", "energy_std"],
    "steel": ["gdp", "smart_factory", "imf", "csrc", "energy_std"],
    "rare_earth": ["hormuz", "imf", "gdp", "csrc", "energy_std"],
    "commodity_equity": ["hormuz", "brent93", "imf", "gdp", "energy_std"],
}

SECTOR_BEAR: dict[str, list[str]] = {
    "credit_bond": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116", "delivery0224"],
    "government_bond": ["delivery0717", "imf_risk", "ashare_0724", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116", "delivery0224"],
    "convertible_bond": ["delivery0717", "mag7", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "korea", "delivery0320", "delivery0417"],
    "oil_gas": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "mag7", "delivery0417", "delivery0116"],
    "energy": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "mag7", "delivery0320", "delivery0417", "delivery0116"],
    "energy_chemical": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "mag7", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "coal": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "mag7", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "electric_utility": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "mag7", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "bank": ["delivery0717", "property", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "securities": ["delivery0717", "ashare_0724", "mag7", "etf_opt", "imf_risk", "delivery0622", "delivery0515", "korea", "delivery0320", "delivery0417"],
    "securities_insurance": ["delivery0717", "ashare_0724", "mag7", "etf_opt", "imf_risk", "delivery0622", "delivery0515", "korea", "delivery0320", "delivery0417"],
    "cashflow_factor": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "mag7", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "dividend_factor": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "property", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "broad_market": ["delivery0717", "mag7", "ashare_0724", "imf_risk", "etf_opt", "korea", "delivery0622", "delivery0515", "delivery0320", "delivery0417"],
    "large_cap": ["delivery0717", "ashare_0724", "mag7", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "growth_board": ["delivery0717", "mag7", "korea", "ashare_0724", "changxin_siphon", "brent_stag", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515"],
    "small_cap": ["delivery0717", "mag7", "ashare_0724", "changxin_siphon", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "korea", "delivery0320"],
    "mid_cap": ["delivery0717", "ashare_0724", "mag7", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "korea", "delivery0320", "delivery0417"],
    "mid_cap_factor": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "mag7", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "state_owned_enterprise": ["delivery0717", "property", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "healthcare": ["delivery0717", "ashare_0724", "mag7", "imf_risk", "etf_opt", "hormuz_risk", "delivery0622", "delivery0515", "delivery0320", "delivery0417"],
    "innovative_drug": ["delivery0717", "ashare_0724", "mag7", "imf_risk", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "korea"],
    "biotechnology": ["delivery0717", "mag7", "ashare_0724", "imf_risk", "hormuz_risk", "etf_opt", "delivery0622", "korea", "delivery0515", "delivery0320"],
    "agriculture": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "mag7", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "agriculture_commodity": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "mag7", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "livestock": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "mag7", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "consumer": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "mag7", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "liquor": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "mag7", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "food_beverage": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "mag7", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "infrastructure": ["property", "delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "building_materials": ["property", "delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "real_estate": ["property", "delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "semiconductor": ["mag7", "korea", "delivery0717", "changxin_siphon", "ashare_0724", "brent_stag", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515"],
    "electronics": ["mag7", "korea", "delivery0717", "changxin_siphon", "ashare_0724", "brent_stag", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515"],
    "consumer_electronics": ["mag7", "korea", "delivery0717", "changxin_siphon", "ashare_0724", "brent_stag", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515"],
    "artificial_intelligence": ["mag7", "delivery0717", "korea", "ashare_0724", "brent_stag", "hormuz_risk", "changxin_siphon", "etf_opt", "delivery0622", "delivery0515"],
    "star_50": ["mag7", "delivery0717", "korea", "changxin_siphon", "ashare_0724", "brent_stag", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515"],
    "internet": ["mag7", "delivery0717", "ashare_0724", "korea", "imf_risk", "brent_stag", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515"],
    "software": ["mag7", "delivery0717", "ashare_0724", "korea", "brent_stag", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515", "changxin_siphon"],
    "gaming": ["mag7", "delivery0717", "ashare_0724", "imf_risk", "etf_opt", "korea", "delivery0622", "delivery0515", "hormuz_risk", "delivery0320"],
    "media": ["mag7", "delivery0717", "ashare_0724", "imf_risk", "etf_opt", "korea", "delivery0622", "delivery0515", "hormuz_risk", "delivery0320"],
    "education": ["delivery0717", "ashare_0724", "mag7", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "korea", "hormuz_risk", "delivery0320"],
    "communication": ["mag7", "delivery0717", "ashare_0724", "korea", "brent_stag", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515", "imf_risk"],
    "broad_tech": ["mag7", "delivery0717", "korea", "ashare_0724", "brent_stag", "hormuz_risk", "etf_opt", "changxin_siphon", "delivery0622", "delivery0515"],
    "technology": ["mag7", "korea", "delivery0717", "ashare_0724", "brent_stag", "hormuz_risk", "imf_risk", "etf_opt", "delivery0622", "delivery0515"],
    "robotics": ["delivery0717", "mag7", "ashare_0724", "hormuz_risk", "brent_stag", "etf_opt", "delivery0622", "korea", "delivery0515", "imf_risk"],
    "machinery": ["delivery0717", "ashare_0724", "mag7", "hormuz_risk", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417"],
    "intelligent_manufacturing": ["delivery0717", "mag7", "ashare_0724", "hormuz_risk", "brent_stag", "etf_opt", "delivery0622", "korea", "delivery0515", "imf_risk"],
    "advanced_equipment": ["delivery0717", "ashare_0724", "mag7", "hormuz_risk", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "korea", "delivery0320"],
    "new_materials": ["delivery0717", "ashare_0724", "mag7", "hormuz_risk", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417"],
    "defense": ["delivery0717", "ashare_0724", "mag7", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "hormuz_risk", "delivery0320", "delivery0417"],
    "satellite": ["delivery0717", "mag7", "ashare_0724", "hormuz_risk", "etf_opt", "delivery0622", "korea", "delivery0515", "imf_risk", "brent_stag"],
    "battery": ["delivery0717", "ashare_0724", "mag7", "hormuz_risk", "brent_stag", "etf_opt", "delivery0622", "imf_risk", "delivery0515", "korea"],
    "new_energy": ["delivery0717", "ashare_0724", "mag7", "hormuz_risk", "brent_stag", "etf_opt", "delivery0622", "imf_risk", "delivery0515", "korea"],
    "new_energy_vehicle": ["delivery0717", "ashare_0724", "mag7", "hormuz_risk", "brent_stag", "etf_opt", "delivery0622", "imf_risk", "delivery0515", "korea"],
    "solar": ["delivery0717", "ashare_0724", "mag7", "hormuz_risk", "brent_stag", "etf_opt", "delivery0622", "imf_risk", "delivery0515", "korea"],
    "smart_driving": ["delivery0717", "mag7", "ashare_0724", "hormuz_risk", "brent_stag", "etf_opt", "delivery0622", "korea", "delivery0515", "imf_risk"],
    "gold": ["delivery0717", "ashare_0724", "etf_opt", "delivery0622", "delivery0515", "mag7", "delivery0320", "delivery0417", "delivery0116", "delivery0224"],
    "nonferrous_metals": ["delivery0717", "ashare_0724", "mag7", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "korea"],
    "steel": ["property", "delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "mag7"],
    "rare_earth": ["delivery0717", "ashare_0724", "mag7", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "korea", "delivery0320", "delivery0417"],
    "commodity_equity": ["delivery0717", "ashare_0724", "mag7", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "korea"],
}

THEME_BULL = {
    "fixed_income": ["csrc", "cpi", "gdp", "imf", "citic_peak", "housing"],
    "energy_materials": ["hormuz", "brent93", "imf", "energy_std", "gdp"],
    "capital_market": ["csrc", "gdp", "citic_peak", "imf", "cpi"],
    "healthcare": ["nhsa_list", "nhsa_bd", "gdp", "imf", "csrc"],
    "consumer_agriculture": ["retail", "no1_doc", "gdp", "cpi", "csrc"],
    "property_infrastructure": ["housing", "gdp", "csrc", "smart_factory", "imf"],
    "semiconductor_electronics": ["ic_tax", "changxin", "smart_factory", "gdp", "waic"],
    "ai_digital": ["waic", "smart_factory", "gdp", "csrc", "citic_peak"],
    "advanced_manufacturing": ["smart_factory", "gdp", "csrc", "imf", "auto_std"],
    "clean_energy_auto": ["auto_std", "gdp", "smart_factory", "imf", "csrc"],
    "gold_commodity": ["hormuz", "imf", "brent93", "cpi", "gdp"],
    "global_equity": ["imf", "csrc", "gdp", "citic_peak", "cpi"],
}

THEME_BEAR = {
    "fixed_income": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116", "delivery0224"],
    "energy_materials": ["delivery0717", "ashare_0724", "mag7", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "korea"],
    "capital_market": ["delivery0717", "ashare_0724", "mag7", "etf_opt", "imf_risk", "delivery0622", "delivery0515", "korea", "delivery0320", "delivery0417"],
    "healthcare": ["delivery0717", "ashare_0724", "mag7", "imf_risk", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "korea"],
    "consumer_agriculture": ["delivery0717", "ashare_0724", "imf_risk", "etf_opt", "mag7", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "delivery0116"],
    "property_infrastructure": ["property", "delivery0717", "ashare_0724", "imf_risk", "etf_opt", "delivery0622", "delivery0515", "delivery0320", "delivery0417", "mag7"],
    "semiconductor_electronics": ["mag7", "korea", "delivery0717", "changxin_siphon", "ashare_0724", "brent_stag", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515"],
    "ai_digital": ["mag7", "delivery0717", "korea", "ashare_0724", "brent_stag", "hormuz_risk", "changxin_siphon", "etf_opt", "delivery0622", "delivery0515"],
    "advanced_manufacturing": ["delivery0717", "mag7", "ashare_0724", "hormuz_risk", "imf_risk", "etf_opt", "delivery0622", "korea", "delivery0515", "brent_stag"],
    "clean_energy_auto": ["delivery0717", "ashare_0724", "mag7", "hormuz_risk", "brent_stag", "etf_opt", "delivery0622", "imf_risk", "delivery0515", "korea"],
    "gold_commodity": ["delivery0717", "ashare_0724", "etf_opt", "delivery0622", "mag7", "delivery0515", "delivery0320", "delivery0417", "delivery0116", "delivery0224"],
    "global_equity": ["mag7", "korea", "delivery0717", "ashare_0724", "imf_risk", "brent_stag", "hormuz_risk", "etf_opt", "delivery0622", "delivery0515"],
}


def parse_event_date(raw: str) -> date | None:
    raw = raw.strip()
    if len(raw) == 7 and raw.count("-") == 1:
        y, m = raw.split("-")
        return date(int(y), int(m), 15)
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def bars_index(bars: list[DailyBar]) -> dict[date, int]:
    return {b.date: i for i, b in enumerate(bars)}


def nearest_bar_index(idx: dict[date, int], target: date) -> int | None:
    if target in idx:
        return idx[target]
    for d in range(0, 6):
        cand = target + timedelta(days=d)
        if cand in idx:
            return idx[cand]
    for d in range(1, 6):
        cand = target - timedelta(days=d)
        if cand in idx:
            return idx[cand]
    return None


def window_returns(bars: list[DailyBar], event_day: date) -> dict[str, float | None]:
    idx_map = bars_index(bars)
    i = nearest_bar_index(idx_map, event_day)
    if i is None or i <= 0:
        return {"retT": None, "retT1": None, "cumT3": None, "asOf": None}
    prev = bars[i - 1].close
    if prev <= 0:
        return {"retT": None, "retT1": None, "cumT3": None, "asOf": None}
    ret_t = (bars[i].close / prev - 1) * 100
    ret_t1 = None
    if i + 1 < len(bars) and bars[i].close > 0:
        ret_t1 = (bars[i + 1].close / bars[i].close - 1) * 100
    end = min(i + 3, len(bars) - 1)
    cum = (bars[end].close / prev - 1) * 100
    return {
        "retT": round(ret_t, 2),
        "retT1": None if ret_t1 is None else round(ret_t1, 2),
        "cumT3": round(cum, 2),
        "asOf": bars[i].date.isoformat(),
    }


def passes_bull_price(ret_t: float | None, cum: float | None) -> bool:
    if ret_t is None or cum is None:
        return False
    if ret_t <= -2.0 or cum <= -3.0:
        return False
    return ret_t >= 0 or cum >= 0


def passes_bear_price(ret_t: float | None, cum: float | None) -> bool:
    if ret_t is None or cum is None:
        return False
    if ret_t >= 2.0 or cum >= 3.0:
        return False
    return ret_t <= 0 or cum <= 0


def wrap_event(
    *,
    date_s: str,
    title: str,
    impact: str,
    direction: str,
    source_key: str,
    wr: dict[str, float | None],
) -> dict[str, Any]:
    return {
        "date": date_s,
        "title": title,
        "impact": impact,
        "direction": direction,
        "sourceKey": source_key,
        "verified": True,
        "windowRet": {
            "retT": wr["retT"],
            "retT1": wr["retT1"],
            "cumT3": wr["cumT3"],
            "barDate": wr["asOf"],
        },
    }


def evaluate_named(
    key: str,
    bars: list[DailyBar],
    side: Literal["bull", "bear"],
) -> dict[str, Any] | None:
    meta = MKT[key]
    ed = parse_event_date(meta["date"])
    if ed is None:
        return None
    wr = window_returns(bars, ed)
    ret_t = wr["retT"] if isinstance(wr["retT"], float) else None
    cum = wr["cumT3"] if isinstance(wr["cumT3"], float) else None

    if side == "bull":
        if key in BULL_EXCLUDE:
            return None
        if key == "changxin" and not (ret_t is not None and cum is not None and (ret_t > 0 or cum > 0)):
            return None
        if meta["logic"] not in {"利好", "中性偏多"}:
            return None
        if not passes_bull_price(ret_t, cum):
            return None
        direction = "利好" if meta["logic"] == "利好" else "中性偏多"
    else:
        if meta["logic"] not in {"利空"} and key not in BULL_EXCLUDE:
            # allow risk-off aliases already tagged 利空
            if meta["logic"] != "利空":
                return None
        if not passes_bear_price(ret_t, cum):
            return None
        direction = "利空"

    return wrap_event(
        date_s=meta["date"] if len(meta["date"]) >= 10 else (wr["asOf"] or meta["date"]),
        title=meta["title"],
        impact=meta["impact"],
        direction=direction,
        source_key=key,
        wr=wr,
    )


def discover_price_shocks(
    bars: list[DailyBar],
    side: Literal["bull", "bear"],
    used_dates: set[str],
    need: int,
) -> list[dict[str, Any]]:
    """Fill remaining slots from ranked green/red days (works for low-vol bonds)."""
    if need <= 0 or len(bars) < 5:
        return []
    recent = bars[-LOOKBACK_BARS:] if len(bars) > LOOKBACK_BARS else bars
    cands: list[tuple[float, dict[str, Any]]] = []
    for i in range(1, len(recent)):
        prev = recent[i - 1].close
        if prev <= 0:
            continue
        ret_t = (recent[i].close / prev - 1) * 100
        end = min(i + 3, len(recent) - 1)
        cum = (recent[end].close / prev - 1) * 100
        d = recent[i].date.isoformat()
        if d in used_dates:
            continue
        wr = {
            "retT": round(ret_t, 2),
            "retT1": round((recent[i + 1].close / recent[i].close - 1) * 100, 2)
            if i + 1 < len(recent) and recent[i].close > 0
            else None,
            "cumT3": round(cum, 2),
            "asOf": d,
        }
        if side == "bull":
            # Prefer up days; still reject sell-the-news windows.
            if ret_t < 0 and cum < 0:
                continue
            if not passes_bull_price(wr["retT"], wr["cumT3"]):
                continue
            score = max(ret_t, cum)
            title = f"{d[5:]} 该ETF上涨窗（当日{wr['retT']}% / 三日{wr['cumT3']}%）"
            impact = "价格确认的实质上涨窗口（资金/情绪驱动），已排除利好砸盘形态。"
            direction = "利好" if ret_t >= 0 else "中性偏多"
            key = f"px_up_{d}"
        else:
            if ret_t > 0 and cum > 0:
                continue
            if not passes_bear_price(wr["retT"], wr["cumT3"]):
                continue
            score = max(-ret_t, -cum)
            title = f"{d[5:]} 该ETF下跌窗（当日{wr['retT']}% / 三日{wr['cumT3']}%）"
            impact = "价格确认的实质下跌窗口（资金/情绪驱动），已排除伪利空反弹形态。"
            direction = "利空"
            key = f"px_dn_{d}"
        cands.append(
            (
                score,
                wrap_event(
                    date_s=d,
                    title=title,
                    impact=impact,
                    direction=direction,
                    source_key=key,
                    wr=wr,
                ),
            )
        )
    cands.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, Any]] = []
    for _, ev in cands:
        if len(out) >= need:
            break
        out.append(ev)
    return out

def ordered_keys(sector: str, theme: str, side: Literal["bull", "bear"]) -> list[str]:
    if side == "bull":
        primary = SECTOR_BULL.get(sector) or THEME_BULL.get(theme) or ["csrc", "gdp", "cpi", "imf", "citic_peak"]
        extra = THEME_BULL.get(theme, [])
        pool = ["csrc", "gdp", "cpi", "imf", "smart_factory", "citic_peak", "nhsa_list", "nhsa_bd", "auto_std", "ic_tax", "no1_doc", "housing", "energy_std", "retail", "hormuz", "brent93", "waic"]
    else:
        primary = SECTOR_BEAR.get(sector) or THEME_BEAR.get(theme) or [
            "delivery0717",
            "ashare_0724",
            "mag7",
            "imf_risk",
            "etf_opt",
        ]
        extra = THEME_BEAR.get(theme, [])
        pool = [
            "delivery0717",
            "delivery0622",
            "delivery0515",
            "delivery0417",
            "delivery0320",
            "delivery0224",
            "delivery0116",
            "mag7",
            "korea",
            "ashare_0724",
            "imf_risk",
            "hormuz_risk",
            "brent_stag",
            "property",
            "changxin_siphon",
            "etf_opt",
        ]
    ordered: list[str] = []
    for k in primary + extra + pool:
        if k not in ordered and k in MKT:
            ordered.append(k)
    return ordered


def collect_side(
    bars: list[DailyBar],
    sector: str,
    theme: str,
    side: Literal["bull", "bear"],
    n: int,
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    used_dates: set[str] = set()
    for key in ordered_keys(sector, theme, side):
        if len(kept) >= n:
            break
        ev = evaluate_named(key, bars, side)
        if ev is None:
            continue
        if any(x["sourceKey"] == key for x in kept):
            continue
        bar_d = (ev.get("windowRet") or {}).get("barDate") or ev["date"]
        if bar_d in used_dates:
            continue
        kept.append(ev)
        used_dates.add(str(bar_d)[:10])
    if len(kept) < n:
        fills = discover_price_shocks(bars, side, used_dates, n - len(kept))
        kept.extend(fills)
    if len(kept) < n:
        raise RuntimeError(f"insufficient_{side}:{sector}:got={len(kept)}:need={n}")
    return kept[:n]


def fetch_bars(codes: list[str], workers: int) -> dict[str, list[DailyBar]]:
    provider = PublicMarketDataProvider(calendar_provider=object(), catalyst_provider=object())
    out: dict[str, list[DailyBar]] = {}
    errors: dict[str, str] = {}

    def one(code: str) -> tuple[str, list[DailyBar]]:
        return code, list(provider.get_daily_bars(code))

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(one, c): c for c in codes}
        for fut in as_completed(futs):
            code = futs[fut]
            try:
                c, bars = fut.result()
                out[c] = bars
            except Exception as exc:  # noqa: BLE001
                errors[code] = str(exc)
    if errors:
        raise RuntimeError(f"bar_fetch_failed:{errors}")
    return out


def build(day: str, workers: int, per_side: int) -> dict[str, Any]:
    review = json.loads((REPORTS / f"representative-technical-review-{day}.json").read_text(encoding="utf-8"))
    ctx = json.loads((MODULE_ROOT / "data" / "sector-context-2026-07-20.json").read_text(encoding="utf-8"))
    codes = [str(r["code"]) for r in review["rows"]]
    bars_by = fetch_bars(codes, workers=workers)

    rows_out: list[dict[str, Any]] = []
    for r in review["rows"]:
        code = str(r["code"])
        sector = str(r["sector"])
        theme = str(ctx["sector_theme"].get(sector, ""))
        bars = bars_by[code]
        positives = collect_side(bars, sector, theme, "bull", per_side)
        negatives = collect_side(bars, sector, theme, "bear", per_side)
        rows_out.append(
            {
                "code": code,
                "name": r["name"],
                "sector": SECTOR_CN.get(sector, sector),
                "sectorKey": sector,
                "theme": theme,
                "action": r["action"],
                "trend": r["trend"],
                "positiveEvents": positives,
                "negativeEvents": negatives,
                # backward-compatible alias used by older canvas: positives only
                "events": positives,
                "eventCount": len(positives),
                "positiveCount": len(positives),
                "negativeCount": len(negatives),
            }
        )

    return {
        "asOf": review.get("data_date") or day,
        "generatedAt": datetime.now(SHANGHAI).isoformat(),
        "method": (
            f"每只ETF实质利好/实质利空各{per_side}条。"
            "利好：逻辑偏多+禁止利好砸盘(ret_T≤-2%或cum≤-3%)，须ret_T≥0或cum≥0；"
            "利空：逻辑偏空/风险偏好冲击+禁止伪利空(ret_T≥+2%或cum≥+3%)，须ret_T≤0或cum≤0；"
            "不足时用该ETF价格确认的大幅上涨/下跌窗口补齐。"
        ),
        "rules": {
            "perSide": per_side,
            "bullRejectRetT": -2.0,
            "bullRejectCumT3": -3.0,
            "bearRejectRetT": 2.0,
            "bearRejectCumT3": 3.0,
            "bullHardExclude": sorted(BULL_EXCLUDE),
        },
        "rows": rows_out,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="2026-07-24")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--per-side", type=int, default=TARGET_N)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    payload = build(args.date, workers=args.workers, per_side=args.per_side)
    out = args.output or (REPORTS / f"etf68-impact-events-{args.date}.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(out),
                "etfs": len(payload["rows"]),
                "minPositive": min(r["positiveCount"] for r in payload["rows"]),
                "minNegative": min(r["negativeCount"] for r in payload["rows"]),
                "totalPositive": sum(r["positiveCount"] for r in payload["rows"]),
                "totalNegative": sum(r["negativeCount"] for r in payload["rows"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
