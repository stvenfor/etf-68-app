"""Weekly MACD + MA primary framework helpers (shared by report + backtest)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import fmean, pstdev
from typing import Any, Literal, Mapping, Optional, Sequence

from .market_data import DailyBar
from .reporting import MacdValue, ReportDataError, calculate_macd

MacdMode = Literal["strict", "loose"]
DEFAULT_MA_PAIR = (10, 20)
DEFAULT_MACD_MODE: MacdMode = "strict"
MA_GRID: tuple[tuple[int, int], ...] = ((5, 10), (10, 20), (10, 30), (20, 40))
MACD_MODES: tuple[MacdMode, ...] = ("strict", "loose")
FORWARD_WEEKS = 4
MIN_SAMPLES = 12
MIN_SAMPLES_LOW_VOL = 8
MAX_DD_GATE = -15.0
DEFAULT_MARGIN = 0.1  # if best barely beats default, keep default
LOW_VOL_WEEKLY_RET_STD = 0.5  # percent
BOND_SECTORS = frozenset({"credit_bond", "government_bond", "convertible_bond"})
BULLISH_STRICT = frozenset({"零轴上多头", "金叉"})
BULLISH_LOOSE = frozenset({"零轴上多头", "金叉", "收敛"})
BEARISH = frozenset({"死叉", "零轴下空头"})


@dataclass(frozen=True)
class WeeklyMaState:
    fast: int
    slow: int
    ma_fast: float
    ma_slow: float
    above_fast: bool
    above_slow: bool
    fast_above_slow: bool
    aligned: bool  # price > fast > slow


@dataclass(frozen=True)
class WeeklyRegime:
    week_date: str
    weekly_bars: int
    macd: MacdValue
    ma: WeeklyMaState
    macd_mode: MacdMode
    macd_bullish: bool
    macd_bearish: bool
    ma_ok: bool
    weekly_trend: str  # 多头 / 空头 / 震荡
    long_eligible: bool


def aggregate_weekly_bars(bars: Sequence[DailyBar]) -> list[DailyBar]:
    """Aggregate daily bars into ISO-week bars (OHLCV; date = last session in week)."""
    if not bars:
        return []
    ordered = sorted(bars, key=lambda b: b.date)
    groups: dict[tuple[int, int], list[DailyBar]] = {}
    order: list[tuple[int, int]] = []
    for bar in ordered:
        key = (bar.date.isocalendar().year, bar.date.isocalendar().week)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(bar)
    weekly: list[DailyBar] = []
    for key in order:
        chunk = groups[key]
        first, last = chunk[0], chunk[-1]
        weekly.append(
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
    return weekly


def macd_is_bullish(state: str, mode: MacdMode) -> bool:
    return state in (BULLISH_LOOSE if mode == "loose" else BULLISH_STRICT)


def macd_is_bearish(state: str) -> bool:
    return state in BEARISH


def weekly_ma_state(weekly: Sequence[DailyBar], fast: int, slow: int) -> WeeklyMaState:
    if fast <= 0 or slow <= 0 or fast >= slow:
        raise ReportDataError("invalid_weekly_ma_pair")
    if len(weekly) < slow:
        raise ReportDataError("insufficient_weekly_bars_for_ma")
    ma_fast = fmean(b.close for b in weekly[-fast:])
    ma_slow = fmean(b.close for b in weekly[-slow:])
    close = weekly[-1].close
    above_fast = close > ma_fast
    above_slow = close > ma_slow
    fast_above_slow = ma_fast > ma_slow
    return WeeklyMaState(
        fast=fast,
        slow=slow,
        ma_fast=ma_fast,
        ma_slow=ma_slow,
        above_fast=above_fast,
        above_slow=above_slow,
        fast_above_slow=fast_above_slow,
        aligned=above_fast and fast_above_slow,
    )


def weekly_trend_label(*, macd_bullish: bool, macd_bearish: bool, ma_ok: bool) -> str:
    if macd_bearish:
        return "空头"
    if macd_bullish and ma_ok:
        return "多头"
    if macd_bullish:
        return "震荡"
    return "震荡"


def compute_weekly_regime(
    daily_bars: Sequence[DailyBar],
    *,
    fast: int = DEFAULT_MA_PAIR[0],
    slow: int = DEFAULT_MA_PAIR[1],
    macd_mode: MacdMode = DEFAULT_MACD_MODE,
) -> WeeklyRegime:
    weekly = aggregate_weekly_bars(daily_bars)
    if len(weekly) < 26:
        raise ReportDataError("insufficient_weekly_bars_for_macd")
    macd = calculate_macd(weekly)
    ma = weekly_ma_state(weekly, fast, slow)
    bull = macd_is_bullish(macd.state, macd_mode)
    bear = macd_is_bearish(macd.state)
    ma_ok = ma.aligned
    trend = weekly_trend_label(macd_bullish=bull, macd_bearish=bear, ma_ok=ma_ok)
    return WeeklyRegime(
        week_date=weekly[-1].date.isoformat(),
        weekly_bars=len(weekly),
        macd=macd,
        ma=ma,
        macd_mode=macd_mode,
        macd_bullish=bull,
        macd_bearish=bear,
        ma_ok=ma_ok,
        weekly_trend=trend,
        long_eligible=bull and ma_ok and not bear,
    )


def macd_state_series(weekly: Sequence[DailyBar]) -> list[Optional[str]]:
    """MACD state at each weekly index (None until 26 bars available)."""
    out: list[Optional[str]] = [None] * len(weekly)
    if len(weekly) < 26:
        return out
    ema12 = weekly[0].close
    ema26 = weekly[0].close
    dea = 0.0
    dif = 0.0
    for i, bar in enumerate(weekly):
        prev_dif, prev_dea = dif, dea
        ema12 = (2 * bar.close + 11 * ema12) / 13
        ema26 = (2 * bar.close + 25 * ema26) / 27
        dif = ema12 - ema26
        dea = (2 * dif + 8 * dea) / 10
        if i < 25:
            continue
        if dif > dea and prev_dif <= prev_dea:
            state = "金叉"
        elif dif < dea and prev_dif >= prev_dea:
            state = "死叉"
        elif dif > dea and dif > 0 and dea > 0:
            state = "零轴上多头"
        elif dif < dea and dif < 0 and dea < 0:
            state = "零轴下空头"
        else:
            state = "收敛"
        out[i] = state
    return out


def long_signal_series(
    weekly: Sequence[DailyBar],
    *,
    fast: int,
    slow: int,
    macd_mode: MacdMode,
) -> list[bool]:
    states = macd_state_series(weekly)
    out = [False] * len(weekly)
    for i in range(len(weekly)):
        if i + 1 < slow or states[i] is None:
            continue
        ma_fast = fmean(b.close for b in weekly[i - fast + 1 : i + 1])
        ma_slow = fmean(b.close for b in weekly[i - slow + 1 : i + 1])
        close = weekly[i].close
        ma_ok = close > ma_fast > ma_slow
        bull = macd_is_bullish(states[i], macd_mode)
        bear = macd_is_bearish(states[i])
        out[i] = bool(bull and ma_ok and not bear)
    return out


def is_low_vol_weekly(weekly: Sequence[DailyBar], lookback: int = 52) -> bool:
    if len(weekly) < 3:
        return True
    chunk = weekly[-lookback:] if len(weekly) > lookback else weekly
    rets = [
        (chunk[i].close / chunk[i - 1].close - 1) * 100
        for i in range(1, len(chunk))
        if chunk[i - 1].close > 0
    ]
    if len(rets) < 8:
        return True
    return pstdev(rets) < LOW_VOL_WEEKLY_RET_STD


def evaluate_params(
    weekly: Sequence[DailyBar],
    *,
    fast: int,
    slow: int,
    macd_mode: MacdMode,
    forward_weeks: int = FORWARD_WEEKS,
) -> dict[str, Any]:
    signals = long_signal_series(weekly, fast=fast, slow=slow, macd_mode=macd_mode)
    fwds: list[float] = []
    for i in range(len(weekly) - forward_weeks):
        if not signals[i]:
            continue
        entry = weekly[i].close
        exit_px = weekly[i + forward_weeks].close
        if entry <= 0:
            continue
        fwds.append((exit_px / entry - 1) * 100)

    # strategy equity for max drawdown (long/flat, signal week close)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    in_pos = False
    entry_px = 0.0
    for i in range(1, len(weekly)):
        if signals[i - 1] and not in_pos:
            in_pos = True
            entry_px = weekly[i - 1].close
        if in_pos and not signals[i]:
            if entry_px > 0:
                equity *= weekly[i].close / entry_px
            in_pos = False
            peak = max(peak, equity)
            dd = (equity / peak - 1) * 100 if peak > 0 else 0.0
            max_dd = min(max_dd, dd)
        elif in_pos:
            mark = equity * (weekly[i].close / entry_px) if entry_px > 0 else equity
            peak = max(peak, mark)
            dd = (mark / peak - 1) * 100 if peak > 0 else 0.0
            max_dd = min(max_dd, dd)
    if in_pos and entry_px > 0:
        equity *= weekly[-1].close / entry_px
        peak = max(peak, equity)
        max_dd = min(max_dd, (equity / peak - 1) * 100 if peak > 0 else 0.0)

    n = len(fwds)
    if n == 0:
        mean = 0.0
        std = 0.0
        win_rate = 0.0
        score = float("-inf")
    else:
        mean = fmean(fwds)
        std = pstdev(fwds) if n > 1 else 0.0
        win_rate = sum(1 for x in fwds if x > 0) / n
        score = mean - (std / math.sqrt(n) if n else 0.0)

    return {
        "fast": fast,
        "slow": slow,
        "macdMode": macd_mode,
        "n": n,
        "meanFwd4w": round(mean, 4) if n else None,
        "stdFwd4w": round(std, 4) if n else None,
        "winRate": round(win_rate, 4) if n else None,
        "score": round(score, 4) if math.isfinite(score) else None,
        "maxDdPct": round(max_dd, 4),
        "totalReturnPct": round((equity - 1) * 100, 4),
    }


def passes_gate(
    metrics: Mapping[str, Any],
    *,
    low_vol: bool = False,
    sector: str | None = None,
) -> bool:
    n = int(metrics.get("n") or 0)
    score = metrics.get("score")
    max_dd = metrics.get("maxDdPct")
    min_n = MIN_SAMPLES_LOW_VOL if (low_vol or (sector or "") in BOND_SECTORS) else MIN_SAMPLES
    if n < min_n or score is None or not math.isfinite(float(score)):
        return False
    if float(score) <= 0:
        return False
    if max_dd is None or float(max_dd) < MAX_DD_GATE:
        return False
    return True


def select_best_params(
    weekly: Sequence[DailyBar],
    *,
    sector: str | None = None,
) -> dict[str, Any]:
    low_vol = is_low_vol_weekly(weekly) or (sector or "") in BOND_SECTORS
    evaluated: list[dict[str, Any]] = []
    for fast, slow in MA_GRID:
        for mode in MACD_MODES:
            evaluated.append(
                evaluate_params(weekly, fast=fast, slow=slow, macd_mode=mode)
            )
    default = next(
        m
        for m in evaluated
        if m["fast"] == DEFAULT_MA_PAIR[0]
        and m["slow"] == DEFAULT_MA_PAIR[1]
        and m["macdMode"] == DEFAULT_MACD_MODE
    )
    best = max(
        evaluated,
        key=lambda m: (
            float(m["score"]) if m["score"] is not None else float("-inf"),
            float(m["meanFwd4w"]) if m["meanFwd4w"] is not None else float("-inf"),
        ),
    )
    chosen = best
    if (
        best["score"] is not None
        and default["score"] is not None
        and float(best["score"]) - float(default["score"]) < DEFAULT_MARGIN
    ):
        chosen = default
    elif best["score"] is None or not math.isfinite(float(best["score"])):
        chosen = default

    gate = passes_gate(chosen, low_vol=low_vol, sector=sector)
    # Prefer default if it also passes and best was only marginal — already handled
    if not gate and passes_gate(default, low_vol=low_vol, sector=sector):
        chosen = default
        gate = True

    regime = None
    regime_error = None
    try:
        # rebuild daily-like from weekly for regime using chosen params
        # compute_weekly_regime needs daily; caller should pass daily. Here from weekly only:
        macd = calculate_macd(weekly)
        ma = weekly_ma_state(weekly, int(chosen["fast"]), int(chosen["slow"]))
        mode: MacdMode = chosen["macdMode"]  # type: ignore[assignment]
        bull = macd_is_bullish(macd.state, mode)
        bear = macd_is_bearish(macd.state)
        ma_ok = ma.aligned
        regime = {
            "weekDate": weekly[-1].date.isoformat(),
            "weeklyBars": len(weekly),
            "macd": asdict(macd),
            "ma": asdict(ma),
            "macdMode": mode,
            "macdBullish": bull,
            "macdBearish": bear,
            "maOk": ma_ok,
            "weeklyTrend": weekly_trend_label(
                macd_bullish=bull, macd_bearish=bear, ma_ok=ma_ok
            ),
            "longEligible": bull and ma_ok and not bear,
        }
    except ReportDataError as exc:
        regime_error = exc.reason

    return {
        "bestParams": {
            "fast": chosen["fast"],
            "slow": chosen["slow"],
            "macdMode": chosen["macdMode"],
        },
        "metrics": chosen,
        "defaultMetrics": default,
        "passGate": gate,
        "lowVol": low_vol,
        "regimeNow": regime,
        "regimeError": regime_error,
        "gridSize": len(evaluated),
    }


VOL_UP_RATIO = 1.1  # current window vs prior baseline
PRICE_UP_EPS = 0.0  # ret > 0 counts as 价增; <=0 is 价不涨


@dataclass(frozen=True)
class VolumePriceSignal:
    label: str  # 量升价增 | 量升价不涨 | 中性
    bullish: bool
    bearish: bool
    volUp: bool
    priceUp: bool
    volRatio: float | None
    priceRetPct: float | None
    basis: str  # daily5 | weekly


def volume_price_signal_daily(bars: Sequence[DailyBar]) -> VolumePriceSignal:
    """5日量相对前20日量 + 5日涨跌：量升价增看多，量升价不涨看空。"""
    if len(bars) < 25:
        return VolumePriceSignal("中性", False, False, False, False, None, None, "daily5")
    recent_vol = fmean(b.volume for b in bars[-5:])
    base_vol = fmean(b.volume for b in bars[-25:-5])
    if base_vol <= 0 or not math.isfinite(base_vol):
        return VolumePriceSignal("中性", False, False, False, False, None, None, "daily5")
    vol_ratio = recent_vol / base_vol
    prev = bars[-6].close
    price_ret = (bars[-1].close / prev - 1) * 100 if prev > 0 else 0.0
    return _classify_volume_price(vol_ratio, price_ret, "daily5")


def volume_price_signal_weekly(weekly: Sequence[DailyBar]) -> VolumePriceSignal:
    """本周量相对近4周均量 + 周涨跌。"""
    if len(weekly) < 5:
        return VolumePriceSignal("中性", False, False, False, False, None, None, "weekly")
    cur = weekly[-1].volume
    base = fmean(b.volume for b in weekly[-5:-1])
    if base <= 0 or not math.isfinite(base):
        return VolumePriceSignal("中性", False, False, False, False, None, None, "weekly")
    vol_ratio = cur / base
    prev = weekly[-2].close
    price_ret = (weekly[-1].close / prev - 1) * 100 if prev > 0 else 0.0
    return _classify_volume_price(vol_ratio, price_ret, "weekly")


def _classify_volume_price(
    vol_ratio: float, price_ret_pct: float, basis: str
) -> VolumePriceSignal:
    vol_up = vol_ratio >= VOL_UP_RATIO
    price_up = price_ret_pct > PRICE_UP_EPS
    if vol_up and price_up:
        label = "量升价增"
        return VolumePriceSignal(
            label, True, False, True, True, round(vol_ratio, 4), round(price_ret_pct, 4), basis
        )
    if vol_up and not price_up:
        label = "量升价不涨"
        return VolumePriceSignal(
            label, False, True, True, False, round(vol_ratio, 4), round(price_ret_pct, 4), basis
        )
    return VolumePriceSignal(
        "中性",
        False,
        False,
        vol_up,
        price_up,
        round(vol_ratio, 4),
        round(price_ret_pct, 4),
        basis,
    )


def decide_action(
    *,
    weekly_trend: str,
    long_eligible: bool,
    backtest_pass: bool,
    ret1: float,
    distance_ma20: float,
    sentiment: float,
    volume_price_bearish: bool = False,
    volume_price_bullish: bool = False,
) -> str:
    """Weekly primary + gate; 量升价不涨看空拦截候选；辅指标做不追涨。"""
    if weekly_trend == "空头":
        return "暂缓"
    # 量升价不涨：即使周线多头也不给技术候选（看空确认）
    if volume_price_bearish:
        if ret1 > 3 or distance_ma20 > 5 or sentiment >= 80:
            return "不追涨"
        return "观察"
    if ret1 > 3 or distance_ma20 > 5 or sentiment >= 80:
        return "不追涨"
    if weekly_trend == "多头" and long_eligible and backtest_pass:
        return "技术候选"
    # 量升价增 alone does not upgrade to candidate without weekly+gate
    _ = volume_price_bullish
    return "观察"


def volume_price_from_ratio_ret(
    vol_ratio: float | None,
    price_ret_pct: float | None,
    *,
    basis: str = "daily5",
) -> VolumePriceSignal:
    """Build signal from precomputed volume_ratio + return (for apply-review)."""
    if vol_ratio is None or price_ret_pct is None:
        return VolumePriceSignal("中性", False, False, False, False, None, None, basis)
    if not math.isfinite(float(vol_ratio)) or not math.isfinite(float(price_ret_pct)):
        return VolumePriceSignal("中性", False, False, False, False, None, None, basis)
    return _classify_volume_price(float(vol_ratio), float(price_ret_pct), basis)


def volume_price_to_dict(sig: VolumePriceSignal) -> dict[str, Any]:
    return {
        "label": sig.label,
        "bullish": sig.bullish,
        "bearish": sig.bearish,
        "volUp": sig.volUp,
        "priceUp": sig.priceUp,
        "volRatio": sig.volRatio,
        "priceRetPct": sig.priceRetPct,
        "basis": sig.basis,
    }


def daily_ma_trend(close: float, ma20: float, ma60: float, ma20_rising: bool) -> str:
    if close > ma20 > ma60 and ma20_rising:
        return "多头"
    if close < ma20 and close < ma60:
        return "空头"
    return "震荡"


def regime_to_row_fields(result: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten backtest/select result into report row fields."""
    regime = result.get("regimeNow") or {}
    params = result.get("bestParams") or {}
    metrics = result.get("metrics") or {}
    macd = regime.get("macd") or {}
    ma = regime.get("ma") or {}
    weekly_trend = str(regime.get("weeklyTrend") or "震荡")
    long_eligible = bool(regime.get("longEligible"))
    pass_gate = bool(result.get("passGate"))
    return {
        "weeklyMacd": macd,
        "weeklyMa": ma,
        "weeklyTrend": weekly_trend,
        "maRegime": {
            "aligned": bool(ma.get("aligned")),
            "fast": params.get("fast", ma.get("fast")),
            "slow": params.get("slow", ma.get("slow")),
            "macdMode": params.get("macdMode") or regime.get("macdMode"),
        },
        "backtestPass": pass_gate,
        "bestWeeklyParams": params,
        "weeklyBacktestMetrics": {
            "n": metrics.get("n"),
            "score": metrics.get("score"),
            "winRate": metrics.get("winRate"),
            "meanFwd4w": metrics.get("meanFwd4w"),
            "maxDdPct": metrics.get("maxDdPct"),
        },
        "weeklyLongEligible": long_eligible,
        "trend": weekly_trend,
    }
