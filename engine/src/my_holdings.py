"""Personal open-end fund holdings archive (separate from 30 representative pool).

Excludes money-market and ETF feeders. Static seed + Eastmoney NAV + Sina estimate
+ position-side advice labels.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .fund_portfolio_profile import enrich_portfolio_profile
from .funds_top30 import CATEGORY_LABELS, FetchFn, _default_fetch, enrich_nav
from .position_advice import FRAMEWORK as ADVICE_FRAMEWORK
from .position_advice import apply_position_advice

SHANGHAI = ZoneInfo("Asia/Shanghai")

CATEGORY_ORDER = ("equity", "bond", "hybrid", "qdii")

# Personal holdings from screenshots (2026-07). No 货币 / 同业存单现金类 / ETF联接.
# A/C share classes kept separate; amounts not stored.
HOLDINGS_SEED: tuple[dict[str, Any], ...] = (
    # —— bond / 固收+ ——
    {
        "code": "018846",
        "name": "华泰保兴尊睿6个月持有期债券A",
        "category": "bond",
        "themes": ["固收+", "信用债"],
        "styleNote": "6个月持有期债券；偏债增强",
    },
    {
        "code": "018847",
        "name": "华泰保兴尊睿6个月持有期债券C",
        "category": "bond",
        "themes": ["固收+", "信用债"],
        "styleNote": "同尊睿A的C份额；销售服务费更高",
    },
    {
        "code": "010011",
        "name": "景顺长城景颐招利6个月持有期债券A",
        "category": "bond",
        "themes": ["固收+", "转债增强"],
        "styleNote": "二级债基；可配转债与少量股票",
    },
    {
        "code": "008999",
        "name": "景顺长城景颐嘉利6个月持有期债券A",
        "category": "bond",
        "themes": ["固收+", "转债增强"],
        "styleNote": "二级债基；与招利同系列风格相近",
    },
    {
        "code": "000386",
        "name": "景顺长城景颐双利债券C",
        "category": "bond",
        "themes": ["固收+", "转债增强"],
        "styleNote": "景颐系列开放式债券C",
    },
    {
        "code": "002277",
        "name": "中邮纯债恒利债券C",
        "category": "bond",
        "themes": ["纯债", "利率债"],
        "styleNote": "纯债；权益仓位极低",
    },
    {
        "code": "014847",
        "name": "博时恒乐债券C",
        "category": "bond",
        "themes": ["固收+", "信用债"],
        "styleNote": "债券型；固收+风格",
    },
    {
        "code": "019500",
        "name": "招商安瑞进取债券C",
        "category": "bond",
        "themes": ["固收+", "转债增强"],
        "styleNote": "进取型债基；波动高于纯债",
    },
    # —— hybrid ——
    {
        "code": "012951",
        "name": "汇添富鑫享添利六个月持有期混合A",
        "category": "hybrid",
        "themes": ["固收+", "偏债混合"],
        "styleNote": "6个月持有期偏债混合",
    },
    {
        "code": "009690",
        "name": "易方达瑞锦灵活配置混合C",
        "category": "hybrid",
        "themes": ["灵活配置", "股债平衡"],
        "styleNote": "灵活配置混合",
    },
    {
        "code": "001286",
        "name": "易方达新鑫灵活配置混合E",
        "category": "hybrid",
        "themes": ["灵活配置", "股债平衡"],
        "styleNote": "灵活配置混合E份额",
    },
    {
        "code": "004011",
        "name": "华泰柏瑞鼎利灵活配置混合C",
        "category": "hybrid",
        "themes": ["灵活配置", "股债平衡"],
        "styleNote": "灵活配置混合",
    },
    {
        "code": "012525",
        "name": "融通稳信增益6个月持有期混合C",
        "category": "hybrid",
        "themes": ["固收+", "偏债混合"],
        "styleNote": "6个月持有期偏债混合",
    },
    {
        "code": "002010",
        "name": "中欧瑾通灵活配置混合C",
        "category": "hybrid",
        "themes": ["固收+", "灵活配置"],
        "styleNote": "偏债/固收+灵活配置",
    },
    {
        "code": "002176",
        "name": "华商双翼平衡混合C",
        "category": "hybrid",
        "themes": ["股债平衡", "平衡混合"],
        "styleNote": "平衡型混合",
    },
    {
        "code": "002834",
        "name": "华夏新锦绣灵活配置混合C",
        "category": "hybrid",
        "themes": ["灵活配置"],
        "styleNote": "灵活配置混合",
    },
    {
        "code": "001407",
        "name": "景顺长城稳健回报灵活配置混合C",
        "category": "hybrid",
        "themes": ["灵活配置", "股债平衡"],
        "styleNote": "灵活配置混合；定投常见",
    },
    {
        "code": "011154",
        "name": "华宝新兴消费混合C",
        "category": "hybrid",
        "themes": ["消费"],
        "styleNote": "消费主题主动混合",
    },
    {
        "code": "017090",
        "name": "景顺长城能源基建混合C",
        "category": "hybrid",
        "themes": ["能源基建"],
        "styleNote": "能源与基建主题混合",
    },
    # —— batch 2：其它账户截图（去货币/同业存单/联接）——
    {
        "code": "013149",
        "name": "鹏华双债加利债券C",
        "category": "bond",
        "themes": ["信用债", "可转债"],
        "styleNote": "双债加利；信用债+转债",
    },
    {
        "code": "015716",
        "name": "华夏稳享增利6个月债券A",
        "category": "bond",
        "themes": ["固收+", "信用债"],
        "styleNote": "6个月滚动持有债券A",
    },
    {
        "code": "090021",
        "name": "大成月添利一个月滚动持有中短债A",
        "category": "bond",
        "themes": ["中短债", "利率债"],
        "styleNote": "一个月滚动持有中短债；偏稳健",
    },
    {
        "code": "018561",
        "name": "中信保诚多策略混合(LOF)C",
        "category": "hybrid",
        "themes": ["多策略", "灵活配置"],
        "styleNote": "多策略混合 LOF 的 C 份额（非联接）",
    },
    {
        "code": "010870",
        "name": "汇添富稳健鑫添益六个月持有混合A",
        "category": "hybrid",
        "themes": ["固收+", "偏债混合"],
        "styleNote": "6个月持有期偏债混合",
    },
    {
        "code": "012607",
        "name": "汇添富保鑫灵活配置混合C",
        "category": "hybrid",
        "themes": ["固收+", "灵活配置"],
        "styleNote": "保鑫灵活配置混合",
    },
    {
        "code": "019787",
        "name": "上银丰瑞一年持有期混合发起式A",
        "category": "hybrid",
        "themes": ["固收+", "偏债混合"],
        "styleNote": "一年持有期偏债混合A",
    },
    {
        "code": "019788",
        "name": "上银丰瑞一年持有期混合发起式C",
        "category": "hybrid",
        "themes": ["固收+", "偏债混合"],
        "styleNote": "一年持有期偏债混合C",
    },
    {
        "code": "011192",
        "name": "广发恒荣三个月持有期混合A",
        "category": "hybrid",
        "themes": ["固收+", "偏债混合"],
        "styleNote": "三个月持有期偏债混合A",
    },
    {
        "code": "011193",
        "name": "广发恒荣三个月持有期混合C",
        "category": "hybrid",
        "themes": ["固收+", "偏债混合"],
        "styleNote": "三个月持有期偏债混合C",
    },
    {
        "code": "001123",
        "name": "鹏华弘利混合C",
        "category": "hybrid",
        "themes": ["灵活配置", "股债平衡"],
        "styleNote": "灵活配置混合",
    },
    {
        "code": "001423",
        "name": "景顺长城安享回报混合C",
        "category": "hybrid",
        "themes": ["固收+", "偏债混合"],
        "styleNote": "安享回报偏债混合",
    },
    {
        "code": "010941",
        "name": "大成安享得利六个月持有混合C",
        "category": "hybrid",
        "themes": ["固收+", "偏债混合"],
        "styleNote": "六个月持有期偏债混合",
    },
    {
        "code": "022365",
        "name": "永赢科技智选混合发起C",
        "category": "hybrid",
        "themes": ["科技", "光模块"],
        "styleNote": "科技智选；光模块等成长主题",
    },
    {
        "code": "018603",
        "name": "永赢鑫欣混合C",
        "category": "hybrid",
        "themes": ["灵活配置"],
        "styleNote": "灵活配置混合",
    },
    {
        "code": "025369",
        "name": "东财启和混合C",
        "category": "hybrid",
        "themes": ["灵活配置"],
        "styleNote": "灵活配置混合",
    },
    {
        "code": "010658",
        "name": "海富通欣睿混合C",
        "category": "hybrid",
        "themes": ["固收+", "偏债混合"],
        "styleNote": "欣睿偏债/固收+混合",
    },
    # —— equity ——
    {
        "code": "016858",
        "name": "国金量化多因子股票C",
        "category": "equity",
        "themes": ["量化多因子"],
        "styleNote": "量化多因子股票",
    },
    {
        "code": "012414",
        "name": "招商中证白酒指数C",
        "category": "equity",
        "themes": ["白酒", "消费"],
        "styleNote": "中证白酒指数C（LOF场外C份额，非联接）",
    },
    # —— QDII ——
    {
        "code": "012922",
        "name": "易方达全球成长精选混合(QDII)C",
        "category": "qdii",
        "themes": ["全球成长", "海外主动"],
        "styleNote": "QDII 人民币C；全球成长精选",
    },
    {
        "code": "008254",
        "name": "华宝致远混合(QDII)C",
        "category": "qdii",
        "themes": ["海外主动"],
        "styleNote": "QDII 主动混合",
    },
    {
        "code": "018147",
        "name": "建信新兴市场优选混合(QDII)C",
        "category": "qdii",
        "themes": ["新兴市场"],
        "styleNote": "QDII 新兴市场；定投常见",
    },
)


def seed_universe() -> list[dict[str, Any]]:
    """Expand HOLDINGS_SEED into enrich_nav-ready rows."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    rank_by_cat: dict[str, int] = {k: 0 for k in CATEGORY_ORDER}
    for raw in HOLDINGS_SEED:
        code = str(raw.get("code") or "").zfill(6)
        if not code.isdigit() or code in seen:
            continue
        seen.add(code)
        category = str(raw.get("category") or "hybrid")
        if category not in CATEGORY_ORDER:
            category = "hybrid"
        rank_by_cat[category] = rank_by_cat.get(category, 0) + 1
        themes = [str(t) for t in (raw.get("themes") or []) if t]
        out.append(
            {
                "code": code,
                "name": str(raw.get("name") or ""),
                "category": category,
                "categoryLabel": CATEGORY_LABELS.get(category, category),
                "themes": themes,
                "styleNote": str(raw.get("styleNote") or ""),
                "rankInCategory": rank_by_cat[category],
                "aumYi": None,
            }
        )
    return out


def build_my_holdings(
    *,
    fetch: FetchFn = _default_fetch,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    universe = seed_universe()
    prev_by: dict[str, dict[str, Any]] = {}
    if previous and isinstance(previous.get("rows"), list):
        for r in previous["rows"]:
            if isinstance(r, dict) and r.get("code"):
                prev_by[str(r["code"]).zfill(6)] = r
    valued = enrich_nav(universe, fetch=fetch, previous_by_code=prev_by)
    valued = enrich_portfolio_profile(valued, fetch=fetch, previous_by_code=prev_by, workers=5)
    valued = apply_position_advice(valued)
    counts = {k: 0 for k in CATEGORY_ORDER}
    advice_counts: dict[str, int] = {}
    for row in valued:
        cat = str(row.get("category") or "")
        if cat in counts:
            counts[cat] += 1
        label = str(row.get("advice") or "继续持有")
        advice_counts[label] = advice_counts.get(label, 0) + 1

    return {
        "ok": True,
        "asOf": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "counts": counts,
        "adviceCounts": advice_counts,
        "adviceFramework": ADVICE_FRAMEWORK,
        "source": {
            "universe": "personal_holdings_seed",
            "nav": "eastmoney_pingzhong",
            "estimate": "sina_hq_fu",
            "portfolio": "eastmoney_f10_hypz_asset",
            "risk": "eastmoney_fund_mn_basic",
        },
        "excludedNote": (
            "已排除货币基金、同业存单现金类与ETF联接；不存储持仓金额与盈亏。"
            "行业占比与股债仓位取最新公开报告，可能滞后于净值日。"
        ),
        "rows": valued,
    }


def write_my_holdings(path: Any, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
