"""Personal-holdings「仓位建议」labels (持仓侧规则化观察，非投资建议).

Distinct from fund_advice (申购侧). Same valuation inputs / category thresholds,
mapped to hold / add / trim / redeem style labels.
"""

from __future__ import annotations

from typing import Any, Optional

from .fund_advice import (
    DISCOUNT_OK_PCT,
    OVERHEAT_PCT,
    PREMIUM_HOT_PCT,
    SOFT_DIP_PCT,
    _chg_for_advice,
    estimate_premium_pct,
)

ADVICE_HOLD = "暂缓"
ADVICE_REDEEM = "考虑赎回"
ADVICE_TRIM = "减仓观察"
ADVICE_ADD = "可加仓"
ADVICE_KEEP = "继续持有"

# Themes that amplify overheat → redeem threshold (more sensitive).
_HIGH_VOL_THEMES = frozenset({"白酒", "消费", "量化多因子", "能源基建", "港股科技", "新兴市场"})

FRAMEWORK: dict[str, Any] = {
    "rule": "按类别波动门槛，结合公布涨跌、盘中估值涨跌与估值相对净值溢折价，给出持仓侧观察标签（继续持有/可加仓/减仓观察/考虑赎回）",
    "labels": [ADVICE_KEEP, ADVICE_ADD, ADVICE_TRIM, ADVICE_REDEEM, ADVICE_HOLD],
    "notInvestmentAdvice": True,
    "risks": [
        "实时估值≠当日最终公布净值，收盘后可能大幅修正",
        "QDII / 海外主题估值常滞后，溢折价参考性更弱",
        "标签用于规则化观察，不构成申购/赎回建议或收益承诺",
        "未纳入持仓金额与浮盈亏；集中度与锁定期需自行核对",
        "高波动主题（白酒/消费/量化等）过热时更易触发减仓或赎回观察",
    ],
}


def _num(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def _theme_vol_boost(row: dict[str, Any]) -> float:
    themes = row.get("themes") or []
    if not isinstance(themes, (list, tuple)):
        return 1.0
    for t in themes:
        if str(t) in _HIGH_VOL_THEMES:
            return 0.85  # tighter overheat → redeem sooner
    return 1.0


def decide_position_advice(row: dict[str, Any]) -> dict[str, Any]:
    """Return advice / adviceDetail / adviceRisk / estimatePremiumPct."""
    category = str(row.get("category") or "hybrid")
    overheat = OVERHEAT_PCT.get(category, OVERHEAT_PCT["hybrid"])
    soft_dip = SOFT_DIP_PCT.get(category, SOFT_DIP_PCT["hybrid"])
    prem_hot = PREMIUM_HOT_PCT.get(category, PREMIUM_HOT_PCT["hybrid"])
    disc_ok = DISCOUNT_OK_PCT.get(category, DISCOUNT_OK_PCT["hybrid"])
    boost = _theme_vol_boost(row)
    redeem_chg = overheat * (1.35 if boost >= 1.0 else 1.15)
    redeem_prem = prem_hot * (1.4 if boost >= 1.0 else 1.2)

    premium = estimate_premium_pct(row.get("estimateNav"), row.get("nav"))
    chg, chg_src = _chg_for_advice(row)
    cat_label = str(row.get("categoryLabel") or category)
    themes = row.get("themes") or []
    theme_txt = "、".join(str(t) for t in themes[:4]) if themes else ""

    if row.get("error") or _num(row.get("nav")) is None:
        return {
            "advice": ADVICE_HOLD,
            "adviceDetail": "净值缺失或拉取异常，暂不给仓位方向",
            "adviceRisk": "数据不可用时勿盲申盲赎；先核对官方净值与锁定期",
            "estimatePremiumPct": premium,
        }

    # 考虑赎回：强过热 + 高溢价（或其一极端）
    hot_chg = chg is not None and chg > redeem_chg * boost
    hot_prem = premium is not None and premium > redeem_prem * boost
    if hot_chg and (premium is None or premium > prem_hot * 0.5 * boost):
        detail = f"{chg_src}{chg:+.2f}% 超赎回观察线{redeem_chg * boost:.2f}%"
        if theme_txt:
            detail += f"；主题 {theme_txt}"
        return {
            "advice": ADVICE_REDEEM,
            "adviceDetail": detail,
            "adviceRisk": "短线过热时赎回观察≠必卖；需核对锁定期、赎回费与自身仓位",
            "estimatePremiumPct": premium,
        }
    if hot_prem and (chg is None or chg > overheat * 0.5 * boost):
        detail = f"估值相对净值溢价{premium:+.2f}% 超赎回溢价线{redeem_prem * boost:.2f}%"
        if theme_txt:
            detail += f"；主题 {theme_txt}"
        return {
            "advice": ADVICE_REDEEM,
            "adviceDetail": detail,
            "adviceRisk": "高溢价按估值操作，结算净值回落会造成额外损失",
            "estimatePremiumPct": premium,
        }

    # 减仓观察：过热或溢价偏高
    if chg is not None and chg > overheat * boost:
        detail = f"{chg_src}{chg:+.2f}% 超{cat_label}过热线{overheat * boost:.2f}%"
        if theme_txt:
            detail += f"；主题 {theme_txt}"
        return {
            "advice": ADVICE_TRIM,
            "adviceDetail": detail,
            "adviceRisk": "减仓观察≠立即卖出；可先停定投或分批，避免追涨加仓",
            "estimatePremiumPct": premium,
        }
    if premium is not None and premium > prem_hot * boost:
        detail = f"估值相对净值溢价{premium:+.2f}% 超{prem_hot * boost:.2f}%"
        if theme_txt:
            detail += f"；主题 {theme_txt}"
        return {
            "advice": ADVICE_TRIM,
            "adviceDetail": detail,
            "adviceRisk": "溢价偏高时加仓成本不利；已有仓位宜观察而非加码",
            "estimatePremiumPct": premium,
        }

    # 可加仓：回落或折价
    if chg is not None and chg < soft_dip:
        detail = f"{chg_src}{chg:+.2f}% 低于回落线{soft_dip:g}%"
        if theme_txt:
            detail += f"；主题 {theme_txt}"
        return {
            "advice": ADVICE_ADD,
            "adviceDetail": detail,
            "adviceRisk": "回落≠见底；定投续作需能承受继续波动，主题集中风险仍在",
            "estimatePremiumPct": premium,
        }
    if premium is not None and premium < disc_ok:
        detail = f"估值相对净值折价{premium:+.2f}%（线{disc_ok:g}%）"
        if theme_txt:
            detail += f"；主题 {theme_txt}"
        return {
            "advice": ADVICE_ADD,
            "adviceDetail": detail,
            "adviceRisk": "折价可能来自估值滞后；不等于低估值安全垫",
            "estimatePremiumPct": premium,
        }

    parts: list[str] = []
    if chg is not None:
        parts.append(f"{chg_src}{chg:+.2f}%")
    if premium is not None:
        parts.append(f"溢折价{premium:+.2f}%")
    if theme_txt:
        parts.append(f"主题 {theme_txt}")
    detail = "、".join(parts) if parts else "涨跌与溢折价均不显著"
    return {
        "advice": ADVICE_KEEP,
        "adviceDetail": detail,
        "adviceRisk": "继续持有表示规则未触发强弱信号，仍有净值波动与申赎成本",
        "estimatePremiumPct": premium,
    }


def apply_position_advice(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.update(decide_position_advice(item))
        out.append(item)
    return out
