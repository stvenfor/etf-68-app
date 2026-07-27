"""Week+month direction, daily entry signal (周月定方向、日线出信号).

Direction
---------
- Monthly: price > MA_fast > MA_slow on monthly bars → 多头;
  close below both MAs → 空头; else 震荡.
- Weekly: reuse the report's weekly trend (MACD + MA framework).
- Direction is long only when **both** month and week are 多头.
  If either is 空头 → 不做多.

Daily selection (only after direction is long)
---------------------------------------------
- Daily 多头: close > MA20 > MA60 and MA20 rising (same as daily_ma_trend).
- Overheat veto: ret1 > 3% or distance_ma20 > 5% → 日线过热.
- Labels:
  - 做多信号: 月多 + 周多 + 日多 + 未过热
  - 等日线: 月多 + 周多 + 日线未确认多头
  - 日线过热: 月多 + 周多 + 日多但过热
  - 方向未齐: 未同时月多周多，且非空头否决
  - 不做多: 月空或周空
"""

from __future__ import annotations

from statistics import fmean
from typing import Sequence

from .market_data import DailyBar

# Monthly MA pair — needs ≥ slow months of history
MONTHLY_MA_FAST = 2
MONTHLY_MA_SLOW = 5

SIGNAL_LONG = "做多信号"
SIGNAL_WAIT_DAILY = "等日线"
SIGNAL_OVERHEAT = "日线过热"
SIGNAL_DIR_MIXED = "方向未齐"
SIGNAL_NO_LONG = "不做多"

RET1_OVERHEAT = 3.0
DIST_MA20_OVERHEAT = 5.0


def aggregate_monthly_bars(bars: Sequence[DailyBar]) -> list[DailyBar]:
    """Aggregate daily bars into calendar-month bars (date = last session)."""

    if not bars:
        return []
    ordered = sorted(bars, key=lambda b: b.date)
    groups: dict[tuple[int, int], list[DailyBar]] = {}
    order: list[tuple[int, int]] = []
    for bar in ordered:
        key = (bar.date.year, bar.date.month)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(bar)
    monthly: list[DailyBar] = []
    for key in order:
        chunk = groups[key]
        first, last = chunk[0], chunk[-1]
        monthly.append(
            DailyBar(
                date=last.date,
                open=first.open,
                close=last.close,
                high=max(b.high for b in chunk),
                low=min(b.low for b in chunk),
                volume=sum(b.volume for b in chunk),
                turnover_cny=sum(b.turnover_cny for b in chunk),
                source=last.source,
                timestamp=last.timestamp,
            )
        )
    return monthly


def monthly_trend_label(
    daily_bars: Sequence[DailyBar],
    *,
    fast: int = MONTHLY_MA_FAST,
    slow: int = MONTHLY_MA_SLOW,
) -> str:
    """Return 多头 / 空头 / 震荡 from monthly MA alignment."""

    monthly = aggregate_monthly_bars(daily_bars)
    if len(monthly) < slow:
        return "震荡"
    close = monthly[-1].close
    ma_fast = fmean(b.close for b in monthly[-fast:])
    ma_slow = fmean(b.close for b in monthly[-slow:])
    if close > ma_fast > ma_slow:
        return "多头"
    if close < ma_fast and close < ma_slow:
        return "空头"
    return "震荡"


def decide_wm_daily_signal(
    *,
    monthly_trend: str,
    weekly_trend: str,
    daily_trend: str,
    ret1: float,
    distance_ma20: float,
) -> str:
    """Compose week/month direction with daily selection label."""

    month_bear = monthly_trend == "空头"
    week_bear = weekly_trend == "空头"
    if month_bear or week_bear:
        return SIGNAL_NO_LONG

    direction_long = monthly_trend == "多头" and weekly_trend == "多头"
    if not direction_long:
        return SIGNAL_DIR_MIXED

    overheat = ret1 > RET1_OVERHEAT or distance_ma20 > DIST_MA20_OVERHEAT
    if daily_trend == "多头":
        return SIGNAL_OVERHEAT if overheat else SIGNAL_LONG
    return SIGNAL_WAIT_DAILY


def compute_wm_daily_fields(
    daily_bars: Sequence[DailyBar],
    *,
    weekly_trend: str,
    daily_trend: str,
    ret1: float,
    distance_ma20: float,
) -> dict[str, str]:
    monthly = monthly_trend_label(daily_bars)
    signal = decide_wm_daily_signal(
        monthly_trend=monthly,
        weekly_trend=weekly_trend,
        daily_trend=daily_trend,
        ret1=ret1,
        distance_ma20=distance_ma20,
    )
    return {
        "monthlyTrend": monthly,
        "wmDailySignal": signal,
        "wmDailyDetail": f"月{monthly}·周{weekly_trend}·日{daily_trend}",
    }
