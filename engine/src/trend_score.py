"""Multi-dimension market trend score card (0–100).

Dimensions & weights
--------------------
- 周线趋势 25%: daily MA20 direction + price vs MA20 (周线级均线代理)
- 月线趋势 25%: daily MA60 direction + price vs MA60 (月线级均线代理)
- 日线动能 20%: MACD state + histogram sign
- 资金面 15%: 5-day share-flow net inflow
- 估值面 15%: relative crowding proxy (RSI + distance to MA20);
  undervalued → higher score. PE/PB percentile is not yet available;
  flagged in ``missing``.

Output
------
total, rating, advice, per-dimension scores, weights, missing notes.
"""

from __future__ import annotations

import math
from statistics import fmean
from typing import Any, Mapping, Optional, Sequence

WEIGHT_WEEKLY = 0.25
WEIGHT_MONTHLY = 0.25
WEIGHT_MOMENTUM = 0.20
WEIGHT_FLOW = 0.15
WEIGHT_VALUATION = 0.15

WEIGHTS: dict[str, float] = {
    "weekly": WEIGHT_WEEKLY,
    "monthly": WEIGHT_MONTHLY,
    "momentum": WEIGHT_MOMENTUM,
    "flow": WEIGHT_FLOW,
    "valuation": WEIGHT_VALUATION,
}

DIM_LABELS: dict[str, str] = {
    "weekly": "周线趋势",
    "monthly": "月线趋势",
    "momentum": "日线动能",
    "flow": "资金面",
    "valuation": "估值面",
}

MACD_STATE_SCORES = {
    "金叉": 82.0,
    "零轴上多头": 76.0,
    "收敛": 50.0,
    "死叉": 24.0,
    "零轴下空头": 18.0,
}


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    if not math.isfinite(value):
        return 50.0
    return max(lo, min(hi, value))


def score_ma_axis(*, above: bool, rising: bool | None) -> float:
    """Price vs MA + MA slope → 0–100."""

    if rising is None:
        return 72.0 if above else 28.0
    if above and rising:
        return 90.0
    if above and not rising:
        return 62.0
    if not above and rising:
        return 42.0
    return 15.0


def score_macd_momentum(*, state: str | None, histogram: float | None) -> float:
    base = MACD_STATE_SCORES.get(str(state or ""), 50.0)
    if histogram is not None and math.isfinite(histogram):
        if histogram > 0:
            base = min(100.0, base + 8.0)
        elif histogram < 0:
            base = max(0.0, base - 8.0)
    return _clamp(base)


def score_flow(*, flow_5d_cny: float | None, aum_cny: float | None) -> float | None:
    if flow_5d_cny is None or not math.isfinite(flow_5d_cny):
        return None
    if aum_cny is not None and math.isfinite(aum_cny) and aum_cny > 0:
        return _clamp(50.0 + 2500.0 * flow_5d_cny / aum_cny)
    if flow_5d_cny > 0:
        return 70.0
    if flow_5d_cny < 0:
        return 30.0
    return 50.0


def score_valuation_proxy(
    *, rsi14: float | None, distance_ma20_pct: float | None
) -> float | None:
    """Undervalued / oversold → high; extended / overbought → low.

    Stand-in until PE/PB historical percentiles are wired.
    """

    parts: list[float] = []
    if rsi14 is not None and math.isfinite(rsi14):
        parts.append(_clamp(50.0 - (rsi14 - 50.0) * 1.5))
    if distance_ma20_pct is not None and math.isfinite(distance_ma20_pct):
        parts.append(_clamp(50.0 - distance_ma20_pct * 4.0))
    if not parts:
        return None
    return fmean(parts)


def rating_for(score: float) -> str:
    if score >= 80:
        return "强烈看涨"
    if score >= 60:
        return "看涨"
    if score >= 40:
        return "中性"
    if score >= 20:
        return "看跌"
    return "强烈看跌"


def _axis_phrase(score: float, up: str, down: str, flat: str = "走平") -> str:
    if score >= 65:
        return up
    if score <= 35:
        return down
    return flat


def build_advice(dimensions: Mapping[str, float]) -> str:
    week = float(dimensions.get("weekly", 50))
    month = float(dimensions.get("monthly", 50))
    mom = float(dimensions.get("momentum", 50))
    flow = float(dimensions.get("flow", 50))
    val = float(dimensions.get("valuation", 50))

    week_p = _axis_phrase(week, "周线向上", "周线偏弱", "周线震荡")
    month_p = _axis_phrase(month, "月线向上", "月线偏弱", "月线震荡")
    mom_p = _axis_phrase(mom, "日线动能转强", "日线动能偏弱", "日线动能中性")
    flow_p = _axis_phrase(flow, "资金净流入", "资金净流出", "资金面中性")
    val_p = _axis_phrase(val, "相对位置不高", "短线拥挤偏贵", "估值位置中性")

    if month >= 60 and week < 50 and mom >= 45:
        return f"{month_p}，周线回调企稳，建议逢低布局"
    if month >= 60 and week >= 60 and mom >= 60:
        action = "建议积极布局" if flow >= 50 else "建议分批布局、关注资金跟进"
        return f"月线与周线共振向上，{mom_p}，{action}"
    if month >= 60 and week >= 60 and mom < 45:
        return f"{month_p}且{week_p}，但{mom_p}，建议等待日线买点"
    if month < 40 and week < 40:
        return f"{month_p}、{week_p}，趋势尚未修复，建议观望或控制仓位"
    if val <= 35 and (month >= 55 or week >= 55):
        return f"趋势尚可但{val_p}，不宜追高，等待回撤再动手"
    if flow >= 65 and (week >= 55 or mom >= 55):
        return f"{week_p}，{flow_p}，可顺势关注强势品种"
    if month >= 50 and week >= 50:
        return f"{month_p}，{week_p}，{mom_p}，宜持有观察、择机加减"
    return f"{month_p}，{week_p}，{mom_p}；{flow_p}，{val_p}"


def _row_flow_5d(row: Mapping[str, Any]) -> float | None:
    flows = row.get("flows")
    if not isinstance(flows, Mapping):
        return None
    window = flows.get("5") or flows.get(5)
    if not isinstance(window, Mapping):
        return None
    value = window.get("value_cny")
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _row_macd(row: Mapping[str, Any]) -> tuple[str | None, float | None]:
    macd = row.get("macd")
    if isinstance(macd, Mapping):
        state = macd.get("state")
        hist = macd.get("histogram")
        try:
            h = float(hist) if hist is not None else None
        except (TypeError, ValueError):
            h = None
        if h is not None and not math.isfinite(h):
            h = None
        return (str(state) if state else None, h)
    if isinstance(macd, str) and macd:
        return macd, None
    return None, None


def score_row(row: Mapping[str, Any]) -> dict[str, float | None]:
    close = row.get("close")
    ma20 = row.get("ma20")
    ma60 = row.get("ma60")
    try:
        close_f = float(close) if close is not None else None
        ma20_f = float(ma20) if ma20 is not None else None
        ma60_f = float(ma60) if ma60 is not None else None
    except (TypeError, ValueError):
        close_f = ma20_f = ma60_f = None

    above_ma20 = (
        close_f is not None and ma20_f is not None and close_f > ma20_f
        if close_f is not None and ma20_f is not None
        else None
    )
    above_ma60 = (
        close_f is not None and ma60_f is not None and close_f > ma60_f
        if close_f is not None and ma60_f is not None
        else None
    )
    ma20_rising = row.get("ma20_rising")
    ma60_rising = row.get("ma60_rising")
    if isinstance(ma20_rising, bool):
        rising20: bool | None = ma20_rising
    else:
        rising20 = None
    if isinstance(ma60_rising, bool):
        rising60: bool | None = ma60_rising
    else:
        rising60 = None

    weekly = (
        score_ma_axis(above=bool(above_ma20), rising=rising20)
        if above_ma20 is not None
        else None
    )
    monthly = (
        score_ma_axis(above=bool(above_ma60), rising=rising60)
        if above_ma60 is not None
        else None
    )

    state, hist = _row_macd(row)
    momentum = score_macd_momentum(state=state, histogram=hist)

    aum = row.get("aum_estimate_cny")
    try:
        aum_f = float(aum) if aum is not None else None
    except (TypeError, ValueError):
        aum_f = None
    flow = score_flow(flow_5d_cny=_row_flow_5d(row), aum_cny=aum_f)

    try:
        rsi = float(row["rsi14"]) if row.get("rsi14") is not None else None
    except (TypeError, ValueError, KeyError):
        rsi = None
    try:
        dist = (
            float(row["distance_ma20_pct"])
            if row.get("distance_ma20_pct") is not None
            else None
        )
    except (TypeError, ValueError, KeyError):
        dist = None
    valuation = score_valuation_proxy(rsi14=rsi, distance_ma20_pct=dist)

    return {
        "weekly": weekly,
        "momentum": momentum,
        "monthly": monthly,
        "flow": flow,
        "valuation": valuation,
    }


def _mean_present(values: Sequence[Optional[float]]) -> float | None:
    present = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not present:
        return None
    return fmean(present)


def build_trend_score_card(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate 68-ETF rows into one market trend score card."""

    per_dim: dict[str, list[float | None]] = {k: [] for k in WEIGHTS}
    for row in rows:
        scored = score_row(row)
        for key in WEIGHTS:
            per_dim[key].append(scored.get(key))

    dim_scores: dict[str, float] = {}
    missing: list[str] = ["pe_pb_percentile"]
    for key, weight in WEIGHTS.items():
        mean_v = _mean_present(per_dim[key])
        if mean_v is None:
            missing.append(key)
        else:
            dim_scores[key] = round(mean_v, 1)

    usable = [(dim_scores[k], w) for k, w in WEIGHTS.items() if k in dim_scores]
    if not usable:
        total = 50.0
    else:
        total = sum(v * w for v, w in usable) / sum(w for _, w in usable)
    total = round(_clamp(total), 1)
    rating = rating_for(total)
    # Fill missing dims with neutral for advice phrasing only
    advice_dims = {k: dim_scores.get(k, 50.0) for k in WEIGHTS}
    advice = build_advice(advice_dims)

    dimensions = []
    for key, weight in WEIGHTS.items():
        dimensions.append(
            {
                "key": key,
                "label": DIM_LABELS[key],
                "weight": weight,
                "score": dim_scores.get(key),
                "note": (
                    "相对拥挤度代理（RSI+距MA20）；PE/PB分位待接入"
                    if key == "valuation"
                    else None
                ),
            }
        )

    return {
        "total": total,
        "rating": rating,
        "advice": advice,
        "dimensions": dimensions,
        "weights": dict(WEIGHTS),
        "missing": missing,
        "framework": {
            "weekly": "MA20方向 + 价格相对MA20（日线周线级代理）",
            "monthly": "MA60方向 + 价格相对MA60（日线月线级代理）",
            "momentum": "MACD状态 + 柱状线正负",
            "flow": "近5日份额变动×收盘价净流入",
            "valuation": "暂用RSI与距MA20拥挤度代理；低估加分、高估减分",
        },
    }
