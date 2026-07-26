"""20-day momentum + MA28 rotation: always hold the strongest eligible ETF.

Rules
-----
- Buy / enter: 20-day return ranks #1 in the pool **and** close > MA28.
- Hold: keep the position while it stays in the front ranks (top 3)
  and remains above MA28.
- Switch: when the hold drops out of the front ranks **or** closes below MA28,
  rotate into the current strongest eligible asset (rank #1 and above MA28).
  If none qualifies, go to cash.

Labels on the as-of day (per row):
- 买入: opened from cash today
- 换仓: switched into this code today
- 持有: continued hold
- —: not the strategy target
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import fmean
from typing import Any, Mapping, Sequence

from .market_data import DailyBar

RET_WINDOW = 20
MA_WINDOW = 28
# "前列" = top 3；换仓后买入仍指向当前最强（rank #1 + MA28）
TOP_N = 3

SIGNAL_BUY = "买入"
SIGNAL_HOLD = "持有"
SIGNAL_SWITCH = "换仓"
SIGNAL_NONE = "—"


@dataclass(frozen=True)
class DayMetrics:
    code: str
    ret20: float
    close: float
    ma28: float
    above_ma28: bool
    rank: int


def _closes_through(
    bars: Sequence[DailyBar], as_of: date
) -> list[float] | None:
    closes: list[float] = []
    for bar in bars:
        if bar.date > as_of:
            break
        closes.append(bar.close)
    need = RET_WINDOW + 1
    if len(closes) < max(need, MA_WINDOW):
        return None
    return closes


def metrics_on_date(
    bars_by_code: Mapping[str, Sequence[DailyBar]],
    as_of: date,
    *,
    ret_window: int = RET_WINDOW,
    ma_window: int = MA_WINDOW,
) -> list[DayMetrics]:
    """Cross-sectional ret20 rank and MA28 status for one trading day."""

    raw: list[tuple[str, float, float, float, bool]] = []
    for code, bars in bars_by_code.items():
        closes = _closes_through(bars, as_of)
        if closes is None:
            continue
        close = closes[-1]
        ma28 = fmean(closes[-ma_window:])
        ret20 = (close / closes[-ret_window - 1] - 1) * 100
        raw.append((code, ret20, close, ma28, close > ma28))

    raw.sort(key=lambda item: (-item[1], item[0]))
    return [
        DayMetrics(
            code=code,
            ret20=ret20,
            close=close,
            ma28=ma28,
            above_ma28=above,
            rank=index + 1,
        )
        for index, (code, ret20, close, ma28, above) in enumerate(raw)
    ]


def strongest_eligible(metrics: Sequence[DayMetrics], *, top_n: int = TOP_N) -> str | None:
    """Return the code that is rank #1 and above MA28; else None.

    ``top_n`` is accepted for API symmetry with exit rules; entry always
    requires absolute rank #1 (持有最强).
    """

    _ = top_n
    for item in metrics:
        if item.rank == 1 and item.above_ma28:
            return item.code
        if item.rank == 1:
            return None
    return None


def should_exit_hold(
    hold: str,
    metrics_by_code: Mapping[str, DayMetrics],
    *,
    top_n: int = TOP_N,
) -> bool:
    """Exit when momentum leaves the front ranks or price loses MA28."""

    current = metrics_by_code.get(hold)
    if current is None:
        return True
    if not current.above_ma28:
        return True
    if current.rank > top_n:
        return True
    return False


@dataclass
class RotationState:
    hold: str | None
    signal_by_code: dict[str, str]
    metrics_by_code: dict[str, DayMetrics]


def step_rotation(
    prev_hold: str | None,
    metrics: Sequence[DayMetrics],
    *,
    top_n: int = TOP_N,
) -> RotationState:
    """Advance one day; labels describe today's action vs yesterday's hold."""

    by_code = {m.code: m for m in metrics}
    target = strongest_eligible(metrics, top_n=top_n)
    signals = {m.code: SIGNAL_NONE for m in metrics}
    hold = prev_hold

    if hold is None:
        if target is not None:
            hold = target
            signals[hold] = SIGNAL_BUY
    elif should_exit_hold(hold, by_code, top_n=top_n):
        if target is not None and target != hold:
            signals[target] = SIGNAL_SWITCH
            hold = target
        else:
            hold = None
    else:
        signals[hold] = SIGNAL_HOLD

    return RotationState(hold=hold, signal_by_code=signals, metrics_by_code=by_code)


def simulate_rotation(
    bars_by_code: Mapping[str, Sequence[DailyBar]],
    *,
    as_of: date | None = None,
    ret_window: int = RET_WINDOW,
    ma_window: int = MA_WINDOW,
    top_n: int = TOP_N,
) -> RotationState:
    """Walk trading days up to ``as_of`` and return the final rotation state."""

    all_dates: set[date] = set()
    for bars in bars_by_code.values():
        for bar in bars:
            if as_of is not None and bar.date > as_of:
                continue
            all_dates.add(bar.date)
    dates = sorted(all_dates)
    if not dates:
        return RotationState(hold=None, signal_by_code={}, metrics_by_code={})

    hold: str | None = None
    state = RotationState(hold=None, signal_by_code={}, metrics_by_code={})
    min_len = max(ret_window + 1, ma_window)
    # Skip early dates that cannot produce a full cross-section.
    start_idx = 0
    for index, day in enumerate(dates):
        ready = 0
        for bars in bars_by_code.values():
            closes = _closes_through(bars, day)
            if closes is not None and len(closes) >= min_len:
                ready += 1
        if ready >= 1:
            start_idx = index
            break

    for day in dates[start_idx:]:
        metrics = metrics_on_date(
            bars_by_code,
            day,
            ret_window=ret_window,
            ma_window=ma_window,
        )
        if not metrics:
            continue
        state = step_rotation(hold, metrics, top_n=top_n)
        hold = state.hold

    return state


def apply_mom20_ma28(
    rows: Sequence[Mapping[str, Any]],
    bars_by_code: Mapping[str, Sequence[DailyBar]],
    *,
    as_of: date | None = None,
    top_n: int = TOP_N,
) -> dict[str, Any]:
    """Annotate report rows with mom20/MA28 fields; return summary meta."""

    state = simulate_rotation(bars_by_code, as_of=as_of, top_n=top_n)
    for row in rows:
        code = str(row["code"])
        m = state.metrics_by_code.get(code)
        if m is None:
            row["ma28"] = None
            row["above_ma28"] = False
            row["ret20_rank"] = None
            row["mom20Ma28"] = SIGNAL_NONE
            continue
        row["ma28"] = m.ma28
        row["above_ma28"] = m.above_ma28
        row["ret20_rank"] = m.rank
        row["mom20Ma28"] = state.signal_by_code.get(code, SIGNAL_NONE)

    return {
        "primary": "mom20_rank1_plus_ma28",
        "retWindow": RET_WINDOW,
        "maWindow": MA_WINDOW,
        "topN": top_n,
        "hold": state.hold,
        "rule": "买入需20日涨幅第1且收盘站上MA28；排名掉出前3或跌破MA28则换仓，换入当前最强资产",
    }
