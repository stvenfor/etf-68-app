"""Momentum score calculators for ETF rotation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class MomentumScore:
    score: float
    annualized_return: float | None = None
    r_squared: float | None = None


def _ols_slope_r2(
    ys: Sequence[float], *, weights: Sequence[float] | None = None
) -> tuple[float, float]:
    n = len(ys)
    if n < 2:
        return 0.0, 0.0
    xs = list(range(n))
    if weights is None:
        w = [1.0] * n
    else:
        w = list(weights)
        if len(w) != n:
            raise ValueError("weights_length_mismatch")
    sw = sum(w)
    if sw <= 0:
        return 0.0, 0.0
    x_bar = sum(wi * xi for wi, xi in zip(w, xs)) / sw
    y_bar = sum(wi * yi for wi, yi in zip(w, ys)) / sw
    sxx = sum(wi * (xi - x_bar) ** 2 for wi, xi in zip(w, xs))
    sxy = sum(wi * (xi - x_bar) * (yi - y_bar) for wi, xi, yi in zip(w, xs, ys))
    syy = sum(wi * (yi - y_bar) ** 2 for wi, yi in zip(w, ys))
    if sxx <= 1e-18:
        return 0.0, 0.0
    slope = sxy / sxx
    r2 = 0.0 if syy <= 1e-18 else max(0.0, min(1.0, (sxy * sxy) / (sxx * syy)))
    return slope, r2


def simple_momentum(closes: Sequence[float], window: int) -> MomentumScore | None:
    if window < 1 or len(closes) < window + 1:
        return None
    base = closes[-(window + 1)]
    if base <= 0:
        return None
    ret = closes[-1] / base - 1.0
    return MomentumScore(score=ret, annualized_return=ret * (252.0 / window) * 100.0, r_squared=None)


def slope_momentum(
    closes: Sequence[float], window: int, *, weighted: bool = False
) -> MomentumScore | None:
    need = window
    if need < 5 or len(closes) < need:
        return None
    series = closes[-need:]
    if any(v <= 0 for v in series):
        return None
    logs = [math.log(v) for v in series]
    weights = None
    if weighted:
        weights = [float(i + 1) for i in range(len(logs))]
    daily_slope, r2 = _ols_slope_r2(logs, weights=weights)
    annualized = (math.exp(daily_slope * 252.0) - 1.0) * 100.0
    score = (annualized / 100.0) * r2
    return MomentumScore(score=score, annualized_return=annualized, r_squared=r2)


def rsrs_momentum(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], window: int
) -> MomentumScore | None:
    """RSRS: OLS beta of high~low over window, z-scored vs prior 2*window betas."""

    hist = max(window * 3, window + 5)
    if window < 5 or len(closes) < hist or len(highs) < hist or len(lows) < hist:
        return None
    betas: list[float] = []
    start = len(closes) - hist
    for end in range(start + window, len(closes) + 1):
        hs = highs[end - window : end]
        ls = lows[end - window : end]
        n = window
        x_bar = sum(ls) / n
        y_bar = sum(hs) / n
        sxx = sum((x - x_bar) ** 2 for x in ls)
        sxy = sum((x - x_bar) * (y - y_bar) for x, y in zip(ls, hs))
        beta = 0.0 if sxx <= 1e-18 else sxy / sxx
        betas.append(beta)
    if len(betas) < window + 1:
        return None
    cur = betas[-1]
    ref = betas[-(window + 1) : -1]
    mean = sum(ref) / len(ref)
    var = sum((b - mean) ** 2 for b in ref) / max(1, len(ref) - 1)
    std = math.sqrt(var) if var > 1e-18 else 0.0
    z = 0.0 if std <= 0 else (cur - mean) / std
    return MomentumScore(score=z, annualized_return=None, r_squared=None)


def compute_momentum(
    *,
    method: str,
    window: int,
    closes: Sequence[float],
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
) -> MomentumScore | None:
    method = method.lower()
    if method == "simple":
        return simple_momentum(closes, window)
    if method == "slope":
        return slope_momentum(closes, window, weighted=False)
    if method == "weighted_slope":
        return slope_momentum(closes, window, weighted=True)
    if method == "rsrs":
        if highs is None or lows is None:
            return None
        return rsrs_momentum(highs, lows, closes, window)
    raise ValueError(f"unsupported_momentum_method:{method}")
