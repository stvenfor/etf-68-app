"""Open-end fund pool「建议」labels (申购侧规则化观察，非投资建议).

Inputs
------
- Published day change (`dayChangePct`)
- Intraday estimate change (`estimateChangePct`) and estimate vs NAV premium
- Category (equity / bond / hybrid / qdii) — thresholds differ by volatility

Labels (priority high → low)
----------------------------
- 暂缓: missing/broken NAV or marked error
- 不追高: estimate/NAV day move too hot, or estimate far above last NAV
- 相对友好: estimate/NAV soft, or estimate below last NAV (相对申购成本偏低)
- 可关注: mild positive move, premium near flat
- 观望: everything else

Risks are attached per row for UI tooltip / legend — estimates ≠ final NAV,
QDII lags, and large AUM ≠ better forward return.
"""

from __future__ import annotations

from typing import Any, Optional

ADVICE_HOLD = "暂缓"
ADVICE_NO_CHASE = "不追高"
ADVICE_FRIENDLY = "相对友好"
ADVICE_WATCH = "可关注"
ADVICE_NEUTRAL = "观望"

# Day-move / estimate-move thresholds (%). Bond is tighter.
OVERHEAT_PCT: dict[str, float] = {
    "equity": 2.0,
    "hybrid": 1.5,
    "bond": 0.4,
    "qdii": 2.0,
}
SOFT_DIP_PCT: dict[str, float] = {
    "equity": -1.0,
    "hybrid": -0.8,
    "bond": -0.2,
    "qdii": -1.0,
}
# (estimateNav - nav) / nav * 100
PREMIUM_HOT_PCT: dict[str, float] = {
    "equity": 1.5,
    "hybrid": 1.2,
    "bond": 0.3,
    "qdii": 2.0,
}
DISCOUNT_OK_PCT: dict[str, float] = {
    "equity": -1.0,
    "hybrid": -0.8,
    "bond": -0.2,
    "qdii": -1.2,
}
MILD_POS_PCT: dict[str, float] = {
    "equity": 1.0,
    "hybrid": 0.8,
    "bond": 0.2,
    "qdii": 1.0,
}

FRAMEWORK: dict[str, Any] = {
    "rule": "按类别阈值门槛，结合公布涨跌、盘中估值涨跌与估值相对净值溢折价，给出申购侧观察标签",
    "labels": [ADVICE_WATCH, ADVICE_FRIENDLY, ADVICE_NEUTRAL, ADVICE_NO_CHASE, ADVICE_HOLD],
    "notInvestmentAdvice": True,
    "risks": [
        "实时估值≠当日最终公布净值，收盘后可能大幅修正",
        "QDII / 海外主题估值常滞后，溢折价参考性更弱",
        "规模靠前≠未来收益更优，代表池仅为观察样本",
        "股票型固定科技主题（半导体/芯片/通信设备/机器人），行业集中风险高",
        "债券型波动小，阈值按更严门槛；仍受利率与信用风险影响",
        "标签用于规则化观察，不构成申购/赎回建议或收益承诺",
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


def estimate_premium_pct(estimate_nav: Any, nav: Any) -> Optional[float]:
    """Intraday estimate vs last published NAV, percent."""
    est = _num(estimate_nav)
    px = _num(nav)
    if est is None or px is None or px == 0:
        return None
    return round((est - px) / px * 100.0, 4)


def _chg_for_advice(row: dict[str, Any]) -> tuple[Optional[float], str]:
    """Prefer live estimate change; fall back to published day change."""
    est = _num(row.get("estimateChangePct"))
    if est is not None:
        return est, "估值涨跌"
    pub = _num(row.get("dayChangePct"))
    if pub is not None:
        return pub, "净值涨跌"
    return None, "无涨跌"


def decide_fund_advice(row: dict[str, Any]) -> dict[str, Any]:
    """Return advice / adviceDetail / adviceRisk / estimatePremiumPct."""
    category = str(row.get("category") or "hybrid")
    overheat = OVERHEAT_PCT.get(category, OVERHEAT_PCT["hybrid"])
    soft_dip = SOFT_DIP_PCT.get(category, SOFT_DIP_PCT["hybrid"])
    prem_hot = PREMIUM_HOT_PCT.get(category, PREMIUM_HOT_PCT["hybrid"])
    disc_ok = DISCOUNT_OK_PCT.get(category, DISCOUNT_OK_PCT["hybrid"])
    mild_pos = MILD_POS_PCT.get(category, MILD_POS_PCT["hybrid"])

    premium = estimate_premium_pct(row.get("estimateNav"), row.get("nav"))
    chg, chg_src = _chg_for_advice(row)
    cat_label = str(row.get("categoryLabel") or category)

    if row.get("error") or _num(row.get("nav")) is None:
        return {
            "advice": ADVICE_HOLD,
            "adviceDetail": "净值缺失或拉取异常，暂不给方向",
            "adviceRisk": "数据不可用时盲目申购风险极高；先核对官方净值",
            "estimatePremiumPct": premium,
        }

    est_time = str(row.get("estimateTime") or "")
    no_live = "已公布" in est_time or "无盘中" in est_time

    if chg is not None and chg > overheat:
        return {
            "advice": ADVICE_NO_CHASE,
            "adviceDetail": f"{chg_src}{chg:+.2f}% 超{cat_label}过热线{overheat:g}%",
            "adviceRisk": "追高申购易买在短线高点；估值还可能被最终净值下修",
            "estimatePremiumPct": premium,
        }
    if premium is not None and premium > prem_hot:
        return {
            "advice": ADVICE_NO_CHASE,
            "adviceDetail": f"估值相对净值溢价{premium:+.2f}% 超{prem_hot:g}%",
            "adviceRisk": "溢价过高时按估值申购，结算净值若回落会造成额外损失",
            "estimatePremiumPct": premium,
        }

    if chg is not None and chg < soft_dip:
        return {
            "advice": ADVICE_FRIENDLY,
            "adviceDetail": f"{chg_src}{chg:+.2f}% 低于回落线{soft_dip:g}%",
            "adviceRisk": "回落≠见底；若趋势转弱，所谓友好窗口仍可能继续下跌",
            "estimatePremiumPct": premium,
        }
    if premium is not None and premium < disc_ok:
        return {
            "advice": ADVICE_FRIENDLY,
            "adviceDetail": f"估值相对净值折价{premium:+.2f}%（线{disc_ok:g}%）",
            "adviceRisk": "折价可能来自估值滞后或情绪冲击，不等于低估值安全垫",
            "estimatePremiumPct": premium,
        }

    if (
        chg is not None
        and 0 < chg <= mild_pos
        and (premium is None or abs(premium) <= prem_hot * 0.5)
    ):
        detail = f"{chg_src}{chg:+.2f}% 温和"
        if premium is not None:
            detail += f"，溢折价{premium:+.2f}%"
        if no_live:
            detail += "（无可用盘中估值，仅按公布净值）"
        return {
            "advice": ADVICE_WATCH,
            "adviceDetail": detail,
            "adviceRisk": "可关注≠应申购；需结合自身风险承受力与持仓集中度",
            "estimatePremiumPct": premium,
        }

    parts: list[str] = []
    if chg is not None:
        parts.append(f"{chg_src}{chg:+.2f}%")
    if premium is not None:
        parts.append(f"溢折价{premium:+.2f}%")
    if no_live:
        parts.append("无盘中估值")
    detail = "、".join(parts) if parts else "涨跌与溢折价均不显著"
    return {
        "advice": ADVICE_NEUTRAL,
        "adviceDetail": detail,
        "adviceRisk": "观望表示规则未触发强弱信号，仍有净值波动与流动性/申赎费成本",
        "estimatePremiumPct": premium,
    }


def apply_fund_advice(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.update(decide_fund_advice(item))
        out.append(item)
    return out
