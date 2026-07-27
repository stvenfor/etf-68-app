"""MA direction + MACD buy point + volume authenticity advice.

Framework
---------
- MA（定方向）: daily MA20/MA60 alignment (`daily_ma_trend`)
  - 多头: close > MA20 > MA60 and MA20 rising
  - 空头: close below both MAs → 暂缓
  - else → 方向未齐
- MACD（找买点）: daily MACD state
  - 买点: 金叉 / 零轴上多头
  - else (死叉 / 零轴下空头 / 收敛) → 等买点 once direction is long
- 成交量（验真伪）: volume-price label
  - 量升价增 → 确认
  - 量升价不涨 → 量能存疑
  - 中性 → 等量能

Labels
------
- 可买入: MA多头 + MACD买点 + 量升价增
- 等量能: MA多头 + MACD买点 + 量能中性
- 量能存疑: MA多头 + MACD买点 + 量升价不涨
- 等买点: MA多头 + MACD未出买点
- 方向未齐: MA震荡
- 暂缓: MA空头
"""

from __future__ import annotations

from typing import Any

ADVICE_BUY = "可买入"
ADVICE_WAIT_VOL = "等量能"
ADVICE_VOL_DOUBT = "量能存疑"
ADVICE_WAIT_MACD = "等买点"
ADVICE_DIR_MIXED = "方向未齐"
ADVICE_HOLD = "暂缓"

MACD_BUY_STATES = frozenset({"金叉", "零轴上多头"})

ADVICE_FRAMEWORK: dict[str, Any] = {
    "rule": "MA定方向 + MACD找买点 + 成交量验真伪",
    "ma": "日线 close>MA20>MA60 且 MA20 上行 → 多头",
    "macd": "金叉或零轴上多头视为买点",
    "volume": "量升价增确认；量升价不涨存疑；中性等量能",
    "signals": [
        ADVICE_BUY,
        ADVICE_WAIT_VOL,
        ADVICE_VOL_DOUBT,
        ADVICE_WAIT_MACD,
        ADVICE_DIR_MIXED,
        ADVICE_HOLD,
    ],
}


def decide_ma_macd_vol(
    *,
    daily_trend: str,
    macd_state: str,
    volume_price_bullish: bool = False,
    volume_price_bearish: bool = False,
) -> str:
    """Compose MA direction, MACD buy point, and volume authenticity."""

    if daily_trend == "空头":
        return ADVICE_HOLD
    if daily_trend != "多头":
        return ADVICE_DIR_MIXED

    if macd_state not in MACD_BUY_STATES:
        return ADVICE_WAIT_MACD

    if volume_price_bearish:
        return ADVICE_VOL_DOUBT
    if volume_price_bullish:
        return ADVICE_BUY
    return ADVICE_WAIT_VOL


def compute_ma_macd_vol_fields(
    *,
    daily_trend: str,
    macd_state: str,
    volume_price_label: str,
    volume_price_bullish: bool = False,
    volume_price_bearish: bool = False,
) -> dict[str, str]:
    advice = decide_ma_macd_vol(
        daily_trend=daily_trend,
        macd_state=macd_state,
        volume_price_bullish=volume_price_bullish,
        volume_price_bearish=volume_price_bearish,
    )
    return {
        "maMacdVol": advice,
        "maMacdVolDetail": f"MA{daily_trend}·MACD{macd_state}·{volume_price_label or '中性'}",
    }
