"""Daily ETF momentum rotation backtester."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from .config import validate_config
from .filters import RankCandidate, build_rankings, top_targets


@dataclass
class PositionState:
    code: str | None = None
    entry_date: date | None = None
    entry_price: float = 0.0
    peak_price: float = 0.0
    held_trading_days: int = 0
    is_fallback: bool = False


@dataclass
class BacktestResult:
    as_of: date | None
    hold_code: str | None
    hold_name: str | None
    signal: str
    total_return_pct: float
    max_drawdown_pct: float
    ytd_return_pct: float
    day_index: int
    rankings: list[dict[str, Any]]
    equity_dates: list[str]
    equity_nav: list[float]
    equity_hold_codes: list[str | None]
    equity_hold_names: list[str | None]
    trades: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)


def _closes_through(bars: Sequence[Any], as_of: date) -> list[float]:
    out: list[float] = []
    for bar in bars:
        if bar.date > as_of:
            break
        out.append(float(bar.close))
    return out


def _highs_through(bars: Sequence[Any], as_of: date) -> list[float]:
    out: list[float] = []
    for bar in bars:
        if bar.date > as_of:
            break
        out.append(float(bar.high))
    return out


def _lows_through(bars: Sequence[Any], as_of: date) -> list[float]:
    out: list[float] = []
    for bar in bars:
        if bar.date > as_of:
            break
        out.append(float(bar.low))
    return out


def _price_on(bars: Sequence[Any], as_of: date) -> float | None:
    price = None
    for bar in bars:
        if bar.date > as_of:
            break
        price = float(bar.close)
    return price


def _union_trade_dates(bars_by_code: Mapping[str, Sequence[Any]], start: date | None) -> list[date]:
    dates: set[date] = set()
    for bars in bars_by_code.values():
        for bar in bars:
            if start and bar.date < start:
                continue
            dates.add(bar.date)
    return sorted(dates)


def _max_drawdown(navs: Sequence[float]) -> float:
    peak = None
    mdd = 0.0
    for nav in navs:
        if peak is None or nav > peak:
            peak = nav
        if peak and peak > 0:
            dd = (peak - nav) / peak
            if dd > mdd:
                mdd = dd
    return mdd * 100.0


def _ytd_return(dates: Sequence[date], navs: Sequence[float], as_of: date) -> float:
    if not dates or not navs:
        return 0.0
    year_start = date(as_of.year, 1, 1)
    base = None
    for d, nav in zip(dates, navs):
        if d < year_start:
            base = nav
            continue
        if base is None:
            base = nav
        break
    if base is None or base <= 0:
        return 0.0
    return (navs[-1] / base - 1.0) * 100.0


def _rank_payload(rankings: Sequence[RankCandidate]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, c in enumerate(rankings, start=1):
        out.append(
            {
                "rank": i,
                "code": c.code,
                "name": c.name,
                "score": round(c.score, 6),
                "annualized_return": None
                if c.annualized_return is None
                else round(c.annualized_return, 4),
                "r_squared": None if c.r_squared is None else round(c.r_squared, 4),
            }
        )
    return out


def run_backtest(
    *,
    config: dict[str, Any],
    bars_by_code: Mapping[str, Sequence[Any]],
    names: Mapping[str, str] | None = None,
) -> BacktestResult:
    cfg = validate_config(config)
    pool = list(cfg["etf_pool"])
    name_map = {**dict(cfg["etf_names"]), **dict(names or {})}
    start_raw = cfg["backtest"].get("start_date")
    end_raw = cfg["backtest"].get("end_date")
    start = date.fromisoformat(start_raw) if start_raw else None
    end = date.fromisoformat(str(end_raw)[:10]) if end_raw else None

    codes_needed = set(pool)
    fb = cfg["holding"].get("fallback_code")
    if fb:
        codes_needed.add(fb)
    if cfg["market_timing"]["enabled"]:
        codes_needed.add(cfg["market_timing"]["benchmark_code"])

    trade_dates = _union_trade_dates(
        {c: bars_by_code[c] for c in codes_needed if c in bars_by_code}, start
    )
    if end is not None:
        trade_dates = [d for d in trade_dates if d <= end]
    if not trade_dates:
        return BacktestResult(
            as_of=None,
            hold_code=None,
            hold_name=None,
            signal="—",
            total_return_pct=0.0,
            max_drawdown_pct=0.0,
            ytd_return_pct=0.0,
            day_index=0,
            rankings=[],
            equity_dates=[],
            equity_nav=[],
            equity_hold_codes=[],
            equity_hold_names=[],
            trades=[],
            warnings=["no_bars"],
        )

    return _run_backtest_units(
        cfg=cfg,
        bars_by_code=bars_by_code,
        name_map=name_map,
        trade_dates=trade_dates,
        codes_needed=codes_needed,
        warnings=[],
    )


def _run_backtest_units(
    *,
    cfg: dict[str, Any],
    bars_by_code: Mapping[str, Sequence[Any]],
    name_map: dict[str, str],
    trade_dates: list[date],
    codes_needed: set[str],
    warnings: list[str],
) -> BacktestResult:
    initial = float(cfg["backtest"]["initial_nav"])
    commission = float(cfg["costs"]["commission_rate"])
    slippage = float(cfg["costs"]["slippage_rate"])
    cost_rate = commission + slippage
    pool = list(cfg["etf_pool"])
    min_hold = int(cfg["holding"]["min_hold_days"])
    day_type = cfg["holding"]["day_count_type"]
    top_n = int(cfg["selection"]["top_n"])
    fallback = cfg["holding"].get("fallback_code")

    cash = initial
    units = 0.0
    pos = PositionState()
    equity_dates: list[str] = []
    equity_nav: list[float] = []
    equity_hold_codes: list[str | None] = []
    equity_hold_names: list[str | None] = []
    equity_date_objs: list[date] = []
    trades: list[dict[str, Any]] = []
    cooldown_until: dict[str, date] = {}
    last_rankings: list[RankCandidate] = []
    signal = "—"

    def nav_value(d: date) -> float:
        if pos.code and units > 0:
            px = _price_on(bars_by_code.get(pos.code) or [], d)
            if px is not None:
                return cash + units * px
        return cash

    def cooldown_active(code: str, d: date) -> bool:
        until = cooldown_until.get(code)
        return until is not None and d <= until

    def add_cooldown(code: str, d: date, days: int) -> None:
        if days < 0:
            days = 0
        if day_type == "calendar":
            cooldown_until[code] = d + timedelta(days=days)
            return
        try:
            idx = trade_dates.index(d)
            cooldown_until[code] = trade_dates[min(len(trade_dates) - 1, idx + days)]
        except ValueError:
            cooldown_until[code] = d + timedelta(days=days)

    def sell_all(d: date, price: float, action: str) -> None:
        nonlocal cash, units, pos, signal
        if not pos.code or units <= 0:
            return
        proceeds = units * price * (1.0 - cost_rate)
        cash += proceeds
        trades.append(
            {
                "date": d.isoformat(),
                "action": action,
                "code": pos.code,
                "name": name_map.get(pos.code, pos.code),
                "price": round(price * (1.0 - cost_rate), 6),
                "nav": round(cash, 4),
            }
        )
        units = 0.0
        signal = action
        pos = PositionState()

    def buy_code(code: str, d: date, price: float, action: str, *, is_fallback: bool = False) -> None:
        nonlocal cash, units, pos, signal
        if cash <= 0 or price <= 0:
            return
        exec_price = price * (1.0 + cost_rate)
        units = cash / exec_price
        cash = 0.0
        pos = PositionState(
            code=code,
            entry_date=d,
            entry_price=exec_price,
            peak_price=price,
            held_trading_days=0,
            is_fallback=is_fallback,
        )
        signal = action
        trades.append(
            {
                "date": d.isoformat(),
                "action": action,
                "code": code,
                "name": name_map.get(code, code),
                "price": round(exec_price, 6),
                "nav": round(units * price, 4),
            }
        )

    for d in trade_dates:
        closes_by = {c: _closes_through(bars_by_code.get(c) or [], d) for c in codes_needed}
        highs_by = {c: _highs_through(bars_by_code.get(c) or [], d) for c in codes_needed}
        lows_by = {c: _lows_through(bars_by_code.get(c) or [], d) for c in codes_needed}

        cool = {c for c in pool if cooldown_active(c, d)}
        rankings = build_rankings(
            pool=pool,
            names=name_map,
            closes_by_code=closes_by,
            highs_by_code=highs_by,
            lows_by_code=lows_by,
            method=cfg["momentum"]["method"],
            window=int(cfg["momentum"]["window"]),
            secondary_enabled=bool(cfg["momentum"]["secondary_enabled"]),
            secondary_method=cfg["momentum"]["secondary_method"],
            secondary_window=int(cfg["momentum"]["secondary_window"]),
            secondary_min=float(cfg["momentum"]["secondary_min"]),
            score_min=cfg["selection"]["score_min"],
            score_max=cfg["selection"]["score_max"],
            skip_limit_up=bool(cfg["extreme_filter"]["skip_limit_up"]),
            skip_limit_down=bool(cfg["extreme_filter"]["skip_limit_down"]),
            price_above_ma=bool(cfg["condition_filter"]["price_above_ma"]),
            ma_period=int(cfg["condition_filter"]["ma_period"]),
            ma_bull=bool(cfg["condition_filter"]["ma_bull"]),
            ma_fast=int(cfg["condition_filter"]["ma_fast"]),
            ma_slow=int(cfg["condition_filter"]["ma_slow"]),
            market_timing_enabled=bool(cfg["market_timing"]["enabled"]),
            benchmark_code=cfg["market_timing"]["benchmark_code"],
            cooldown_codes=cool,
        )
        last_rankings = rankings
        targets = top_targets(rankings, top_n)
        primary = targets[0] if targets else None

        # update peak / hold days
        if pos.code:
            px = _price_on(bars_by_code.get(pos.code) or [], d)
            if px is not None:
                pos.peak_price = max(pos.peak_price, px)
            pos.held_trading_days += 1

            # stop loss first
            if cfg["stop_loss"]["enabled"] and px is not None and pos.entry_price > 0:
                pct_loss = 1.0 - (px / pos.entry_price)
                dd = 1.0 - (px / pos.peak_price) if pos.peak_price > 0 else 0.0
                hit = False
                if cfg["stop_loss"]["pct_enabled"] and pct_loss >= float(cfg["stop_loss"]["pct_threshold"]):
                    hit = True
                if cfg["stop_loss"]["drawdown_enabled"] and dd >= float(
                    cfg["stop_loss"]["drawdown_threshold"]
                ):
                    hit = True
                if hit:
                    sold = pos.code
                    sell_all(d, px, "止损")
                    add_cooldown(sold, d, int(cfg["stop_loss"]["cooldown_days"]))

        held_ok = True
        if pos.code and pos.entry_date:
            if day_type == "calendar":
                held_ok = (d - pos.entry_date).days >= min_hold
            else:
                held_ok = pos.held_trading_days >= min_hold

        if pos.code and not pos.is_fallback:
            px = _price_on(bars_by_code.get(pos.code) or [], d)
            if px is not None and held_ok and cfg["take_profit"]["enabled"] and pos.entry_price > 0:
                gain = px / pos.entry_price - 1.0
                if gain >= float(cfg["take_profit"]["threshold"]):
                    sold = pos.code
                    sell_all(d, px, "止盈")
                    add_cooldown(sold, d, int(cfg["take_profit"]["cooldown_days"]))

        # rotation decisions
        if pos.code and not pos.is_fallback:
            px = _price_on(bars_by_code.get(pos.code) or [], d)
            if px is not None:
                if not rankings:
                    if held_ok:
                        sell_all(d, px, "空仓")
                        if fallback:
                            fpx = _price_on(bars_by_code.get(fallback) or [], d)
                            if fpx is not None:
                                buy_code(fallback, d, fpx, "买入", is_fallback=True)
                        else:
                            signal = "空仓"
                    else:
                        signal = "持有"
                elif held_ok:
                    if pos.code not in targets[:top_n]:
                        sell_all(d, px, "换仓")
                        if primary:
                            tpx = _price_on(bars_by_code.get(primary) or [], d)
                            if tpx is not None:
                                buy_code(primary, d, tpx, "换仓")
                        elif fallback:
                            fpx = _price_on(bars_by_code.get(fallback) or [], d)
                            if fpx is not None:
                                buy_code(fallback, d, fpx, "买入", is_fallback=True)
                    else:
                        signal = "持有"
                else:
                    signal = "持有"
        elif pos.code and pos.is_fallback:
            if primary:
                px = _price_on(bars_by_code.get(pos.code) or [], d)
                tpx = _price_on(bars_by_code.get(primary) or [], d)
                if px is not None and tpx is not None:
                    sell_all(d, px, "换仓")
                    buy_code(primary, d, tpx, "换仓")
            else:
                signal = "持有"
        else:
            # flat
            if primary:
                tpx = _price_on(bars_by_code.get(primary) or [], d)
                if tpx is not None:
                    buy_code(primary, d, tpx, "买入")
            elif fallback:
                fpx = _price_on(bars_by_code.get(fallback) or [], d)
                if fpx is not None:
                    buy_code(fallback, d, fpx, "买入", is_fallback=True)
            else:
                signal = "空仓"

        nav = nav_value(d)
        equity_dates.append(d.isoformat())
        equity_date_objs.append(d)
        equity_nav.append(round(nav, 4))
        equity_hold_codes.append(pos.code)
        equity_hold_names.append(
            None if not pos.code else name_map.get(pos.code, pos.code)
        )

    as_of = trade_dates[-1]
    total_ret = (equity_nav[-1] / initial - 1.0) * 100.0 if equity_nav else 0.0
    return BacktestResult(
        as_of=as_of,
        hold_code=pos.code,
        hold_name=None if not pos.code else name_map.get(pos.code, pos.code),
        signal=signal,
        total_return_pct=round(total_ret, 4),
        max_drawdown_pct=round(_max_drawdown(equity_nav), 4),
        ytd_return_pct=round(_ytd_return(equity_date_objs, equity_nav, as_of), 4),
        day_index=len(equity_nav),
        rankings=_rank_payload(last_rankings),
        equity_dates=equity_dates,
        equity_nav=equity_nav,
        equity_hold_codes=equity_hold_codes,
        equity_hold_names=equity_hold_names,
        trades=trades,
        warnings=warnings,
    )
