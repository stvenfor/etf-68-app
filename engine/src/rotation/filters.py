"""Ranking filters for ETF rotation."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Mapping, Sequence

from .momentum import MomentumScore, compute_momentum


@dataclass(frozen=True)
class RankCandidate:
    code: str
    name: str
    score: float
    annualized_return: float | None
    r_squared: float | None
    close: float
    prev_close: float


def sma(values: Sequence[float], period: int) -> float | None:
    if period < 1 or len(values) < period:
        return None
    return fmean(values[-period:])


def is_limit_up(close: float, prev_close: float, *, threshold: float = 0.095) -> bool:
    if prev_close <= 0:
        return False
    return (close / prev_close - 1.0) >= threshold


def is_limit_down(close: float, prev_close: float, *, threshold: float = 0.095) -> bool:
    if prev_close <= 0:
        return False
    return (close / prev_close - 1.0) <= -threshold


def passes_condition_filters(
    closes: Sequence[float],
    *,
    price_above_ma: bool,
    ma_period: int,
    ma_bull: bool,
    ma_fast: int,
    ma_slow: int,
) -> bool:
    if price_above_ma:
        ma = sma(closes, ma_period)
        if ma is None or closes[-1] <= ma:
            return False
    if ma_bull:
        fast = sma(closes, ma_fast)
        slow = sma(closes, ma_slow)
        if fast is None or slow is None or fast <= slow:
            return False
    return True


def passes_score_bounds(
    score: float, *, score_min: float | None, score_max: float | None
) -> bool:
    if score_min is not None and score <= float(score_min):
        return False
    if score_max is not None and float(score_max) > 0 and score >= float(score_max):
        return False
    return True


def build_rankings(
    *,
    pool: Sequence[str],
    names: Mapping[str, str],
    closes_by_code: Mapping[str, Sequence[float]],
    highs_by_code: Mapping[str, Sequence[float]],
    lows_by_code: Mapping[str, Sequence[float]],
    method: str,
    window: int,
    secondary_enabled: bool,
    secondary_method: str,
    secondary_window: int,
    secondary_min: float,
    score_min: float | None,
    score_max: float | None,
    skip_limit_up: bool,
    skip_limit_down: bool,
    price_above_ma: bool,
    ma_period: int,
    ma_bull: bool,
    ma_fast: int,
    ma_slow: int,
    market_timing_enabled: bool,
    benchmark_code: str | None,
    cooldown_codes: set[str] | None = None,
) -> list[RankCandidate]:
    cooldown = cooldown_codes or set()
    scored: list[RankCandidate] = []
    bench_score: float | None = None
    if market_timing_enabled and benchmark_code:
        b_closes = closes_by_code.get(benchmark_code) or []
        b_highs = highs_by_code.get(benchmark_code) or []
        b_lows = lows_by_code.get(benchmark_code) or []
        b_m = compute_momentum(
            method=method,
            window=window,
            closes=b_closes,
            highs=b_highs,
            lows=b_lows,
        )
        if b_m is not None:
            bench_score = b_m.score

    for code in pool:
        if code in cooldown:
            continue
        closes = closes_by_code.get(code) or []
        if len(closes) < 2:
            continue
        highs = highs_by_code.get(code) or closes
        lows = lows_by_code.get(code) or closes
        close = closes[-1]
        prev_close = closes[-2]
        if skip_limit_up and is_limit_up(close, prev_close):
            continue
        if skip_limit_down and is_limit_down(close, prev_close):
            continue
        if not passes_condition_filters(
            closes,
            price_above_ma=price_above_ma,
            ma_period=ma_period,
            ma_bull=ma_bull,
            ma_fast=ma_fast,
            ma_slow=ma_slow,
        ):
            continue
        primary = compute_momentum(
            method=method, window=window, closes=closes, highs=highs, lows=lows
        )
        if primary is None:
            continue
        if secondary_enabled:
            secondary = compute_momentum(
                method=secondary_method,
                window=secondary_window,
                closes=closes,
                highs=highs,
                lows=lows,
            )
            if secondary is None or secondary.score < float(secondary_min):
                continue
        if not passes_score_bounds(primary.score, score_min=score_min, score_max=score_max):
            continue
        if bench_score is not None and primary.score <= bench_score:
            continue
        scored.append(
            RankCandidate(
                code=code,
                name=str(names.get(code) or code),
                score=primary.score,
                annualized_return=primary.annualized_return,
                r_squared=primary.r_squared,
                close=close,
                prev_close=prev_close,
            )
        )

    scored.sort(key=lambda c: (-c.score, c.code))
    return scored


def top_targets(rankings: Sequence[RankCandidate], top_n: int) -> list[str]:
    n = max(1, int(top_n))
    return [c.code for c in rankings[:n]]
