"""Build the date-stamped representative ETF review from validated inputs."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime
from statistics import fmean
from typing import Any, Mapping, Sequence

from .market_data import DailyBar
from .reporting import (
    FlowWindow,
    SharePoint,
    calculate_kdj,
    calculate_macd,
    calculate_share_flows,
    score_sentiment,
    validate_sector_context,
)
from .ma_macd_vol import ADVICE_FRAMEWORK as MA_MACD_VOL_FRAMEWORK, compute_ma_macd_vol_fields
from .mom20_ma28 import apply_mom20_ma28
from .trend_score import build_trend_score_card
from .wm_daily_signal import MONTHLY_MA_FAST, MONTHLY_MA_SLOW, compute_wm_daily_fields
from .weekly_signals import (
    DEFAULT_MA_PAIR,
    DEFAULT_MACD_MODE,
    aggregate_weekly_bars,
    compute_weekly_regime,
    daily_ma_trend,
    decide_action,
    regime_to_row_fields,
    select_best_params,
    volume_price_signal_daily,
    volume_price_signal_weekly,
    volume_price_to_dict,
)


def build_report(
    *,
    seed: Mapping[str, Any],
    bars_by_code: Mapping[str, Sequence[DailyBar]],
    shares_by_code: Mapping[str, Sequence[SharePoint]],
    share_errors: Mapping[str, str],
    context: Mapping[str, Any],
    generated_at: datetime,
    weekly_backtest_by_code: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create one report without performing I/O.

    If ``weekly_backtest_by_code`` is provided (from backtest JSON rows keyed by
    code), use its passGate / bestParams / regime. Otherwise compute weekly
    regime from available bars with default params and ``backtestPass=False``
    unless bars are long enough to run ``select_best_params`` inline.
    """

    source_rows = list(seed.get("rows", []))
    sectors = sorted({str(row["sector"]) for row in source_rows})
    validate_sector_context(context, sectors)
    breadth = _market_breadth(
        source_rows, bars_by_code, shares_by_code, share_errors
    )
    weekly_map = {str(k): dict(v) for k, v in (weekly_backtest_by_code or {}).items()}
    output_rows = []
    for metadata in source_rows:
        code = str(metadata["code"])
        bars = list(bars_by_code[code])
        if len(bars) < 60:
            raise ValueError(f"insufficient_report_bars:{code}")
        close = bars[-1].close
        ma5 = fmean(bar.close for bar in bars[-5:]) if len(bars) >= 5 else None
        ma20 = fmean(bar.close for bar in bars[-20:])
        ma23 = fmean(bar.close for bar in bars[-23:]) if len(bars) >= 23 else None
        ma28 = fmean(bar.close for bar in bars[-28:]) if len(bars) >= 28 else None
        ma60 = fmean(bar.close for bar in bars[-60:])
        prior_ma20 = fmean(bar.close for bar in bars[-25:-5])
        ma20_rising = ma20 > prior_ma20
        prior_ma60 = fmean(bar.close for bar in bars[-65:-5]) if len(bars) >= 65 else None
        ma60_rising = ma60 > prior_ma60 if prior_ma60 is not None else None
        above_ma5 = bool(ma5 is not None and close > ma5)
        above_ma23 = bool(ma23 is not None and close > ma23)
        # 5日线上穿23日线：昨 MA5≤MA23，今 MA5>MA23
        ma5_cross_ma23 = False
        if len(bars) >= 24 and ma5 is not None and ma23 is not None:
            ma5_prev = fmean(bar.close for bar in bars[-6:-1])
            ma23_prev = fmean(bar.close for bar in bars[-24:-1])
            ma5_cross_ma23 = ma5_prev <= ma23_prev and ma5 > ma23
        ret1 = _return_pct(bars, 1)
        ret5 = _return_pct(bars, 5)
        ret10 = _return_pct(bars, 10)
        ret20 = _return_pct(bars, 20)
        ret30 = _return_pct(bars, 30) if len(bars) >= 31 else None
        ret60 = _return_pct(bars, 60) if len(bars) >= 61 else None
        ret120 = _return_pct(bars, 120) if len(bars) >= 121 else None
        ret30_entry = bars[-31].date.isoformat() if len(bars) >= 31 else None
        rsi14 = _rsi14(bars)
        kdj = calculate_kdj(bars)
        macd = calculate_macd(bars)
        volume_ratio = _volume_ratio(bars)
        code_points = shares_by_code.get(code, ())
        flows, flow_as_of = _flows_for_code(
            code=code,
            bars=bars,
            points=code_points,
            error=share_errors.get(code),
        )
        latest_share = _latest_share(code_points, flow_as_of)
        aum_cny = latest_share.shares * close if latest_share is not None else None
        sentiment = score_sentiment(
            flow_5d_cny=flows[5].value_cny,
            aum_cny=aum_cny,
            volume_ratio=volume_ratio,
            market_breadth_pct=breadth,
            rsi14=rsi14,
            kdj_state=kdj.state,
            macd_state=macd.state,
        )
        distance_ma20 = (close / ma20 - 1) * 100
        daily_trend = daily_ma_trend(close, ma20, ma60, ma20_rising)
        weekly_fields = _resolve_weekly_fields(
            code=code,
            bars=bars,
            sector=str(metadata.get("sector") or ""),
            weekly_map=weekly_map,
        )
        trend = str(weekly_fields.get("trend") or "震荡")
        weekly = aggregate_weekly_bars(bars)
        vp_weekly = volume_price_signal_weekly(weekly)
        vp_daily = volume_price_signal_daily(bars)
        # 周线量价优先；周线中性时用日线量价
        vp = vp_weekly if vp_weekly.label != "中性" else vp_daily
        action = decide_action(
            weekly_trend=trend,
            long_eligible=bool(weekly_fields.get("weeklyLongEligible")),
            backtest_pass=bool(weekly_fields.get("backtestPass")),
            ret1=ret1,
            distance_ma20=distance_ma20,
            sentiment=sentiment.score,
            volume_price_bearish=vp.bearish,
            volume_price_bullish=vp.bullish,
        )
        wm_fields = compute_wm_daily_fields(
            bars,
            weekly_trend=trend,
            daily_trend=daily_trend,
            ret1=ret1,
            distance_ma20=distance_ma20,
        )
        mmv_fields = compute_ma_macd_vol_fields(
            daily_trend=daily_trend,
            macd_state=macd.state,
            volume_price_label=vp.label,
            volume_price_bullish=vp.bullish,
            volume_price_bearish=vp.bearish,
        )
        theme = _theme_for(
            context, str(metadata["sector"]), str(metadata.get("market", "CN"))
        )
        row = dict(metadata)
        row.update(
            {
                "date": bars[-1].date.isoformat(),
                "close": close,
                "ma5": ma5,
                "ma20": ma20,
                "ma23": ma23,
                "ma28": ma28,
                "ma60": ma60,
                "ma20_rising": ma20_rising,
                "ma60_rising": ma60_rising,
                "above_ma5": above_ma5,
                "above_ma23": above_ma23,
                "ma5_cross_ma23": ma5_cross_ma23,
                "ret1_pct": ret1,
                "ret5_pct": ret5,
                "ret10_pct": ret10,
                "ret20_pct": ret20,
                "ret30_hold_pct": None if ret30 is None else round(ret30, 4),
                "ret30_entry": ret30_entry,
                "ret60_pct": None if ret60 is None else round(ret60, 4),
                "ret120_pct": None if ret120 is None else round(ret120, 4),
                "rsi14": rsi14,
                "distance_ma20_pct": distance_ma20,
                "volume_ratio": volume_ratio,
                "volumePrice": volume_price_to_dict(vp),
                "volumePriceWeekly": volume_price_to_dict(vp_weekly),
                "volumePriceDaily": volume_price_to_dict(vp_daily),
                "dailyMaTrend": daily_trend,
                "trend": trend,
                "action": action,
                **wm_fields,
                **mmv_fields,
                "kdj": asdict(kdj),
                "macd": asdict(macd),
                "flows": {str(window): asdict(flow) for window, flow in flows.items()},
                "flow_as_of": flow_as_of.isoformat() if flow_as_of is not None else None,
                "aum_estimate_cny": aum_cny,
                "sentiment": asdict(sentiment),
                "policy_reason": _evidence_reason(theme["policy"]),
                "fundamental_reason": _evidence_reason(theme["fundamental"]),
                "technical_reason": _technical_reason(
                    close=close,
                    ma20=ma20,
                    ma60=ma60,
                    ma20_rising=ma20_rising,
                    ret5=ret5,
                    ret10=ret10,
                    ret20=ret20,
                    rsi14=rsi14,
                    kdj_state=kdj.state,
                    macd_state=macd.state,
                    weekly_trend=trend,
                    weekly_macd_state=(weekly_fields.get("weeklyMacd") or {}).get("state"),
                    backtest_pass=bool(weekly_fields.get("backtestPass")),
                    volume_price_label=vp.label,
                ),
                "sentiment_reason": _sentiment_reason(
                    sentiment.score,
                    sentiment.label,
                    flows,
                    volume_ratio,
                    breadth,
                    sentiment.missing_inputs,
                ),
            }
        )
        panorama = build_panorama(bars=bars, points=code_points)
        row["panoramaSeries"] = panorama["series"]
        row["panoramaSummary"] = panorama["summary"]
        row.update({k: v for k, v in weekly_fields.items() if k != "trend"})
        row["trend"] = trend
        row.pop("flow_status", None)
        row.pop("reason", None)
        output_rows.append(row)
    as_of = max(date.fromisoformat(str(row["date"])) for row in output_rows)
    mom_meta = apply_mom20_ma28(output_rows, bars_by_code, as_of=as_of)
    output_rows.sort(
        key=lambda row: (
            _action_rank(str(row["action"])),
            -float(row["sentiment"]["score"]),
            -float(row["ret20_pct"]),
        )
    )
    data_dates = {row["date"] for row in output_rows}
    entry_counts = Counter(
        str(row.get("ret30_entry")) for row in output_rows if row.get("ret30_entry")
    )
    ret30_entry = entry_counts.most_common(1)[0][0] if entry_counts else None
    return {
        "title": f"{max(data_dates)} ETF精简代表池技术面审阅",
        "generated_at": generated_at.isoformat(),
        "data_date": max(data_dates),
        "ret30_entry": ret30_entry,
        "ret30_as_of": max(data_dates),
        "lookback_trading_days": 30,
        "flow_definition": "交易所基金份额变化 × 当日收盘价",
        "flow_price_basis": "close",
        "flow_sources": {
            "SSE": "上交所ETF规模（TOT_VOL，万份）",
            "SZSE": "深交所基金规模（份）",
        },
        "breadth_pct": breadth,
        "weekly_framework": {
            "primary": "weekly_macd_plus_ma",
            "aux": ["daily_macd", "rsi", "kdj", "sentiment", "daily_ma", "volume_price"],
            "gateRequiredForCandidate": True,
            "volumePrice": "量升价增看多；量升价不涨看空并拦截技术候选",
        },
        "wm_daily_framework": {
            "rule": "月线+周线同时多头定方向；日线MA20/MA60多头且未过热给出做多信号",
            "monthlyMa": f"M{MONTHLY_MA_FAST}/{MONTHLY_MA_SLOW}",
            "signals": ["做多信号", "等日线", "日线过热", "方向未齐", "不做多"],
        },
        "ma_macd_vol_framework": MA_MACD_VOL_FRAMEWORK,
        "mom20_ma28_framework": mom_meta,
        "trend_score_card": build_trend_score_card(output_rows),
        "rows": output_rows,
    }


def _flows_for_code(
    *,
    code: str,
    bars: Sequence[DailyBar],
    points: Sequence[SharePoint],
    error: str | None,
) -> tuple[dict[int, FlowWindow], Any]:
    if error:
        return (
            {
                window: FlowWindow(window, None, "close", error)
                for window in (1, 5, 10, 20)
            },
            None,
        )
    code_points = [point for point in points if point.code == code]
    bar_dates = {bar.date for bar in bars}
    available_dates = sorted(
        point.date for point in code_points if point.date in bar_dates
    )
    if not available_dates:
        return calculate_share_flows(code_points, bars), None
    as_of = available_dates[-1]
    eligible_bars = [bar for bar in bars if bar.date <= as_of]
    return calculate_share_flows(code_points, eligible_bars), as_of


def _market_breadth(
    rows: Sequence[Mapping[str, Any]],
    bars_by_code: Mapping[str, Sequence[DailyBar]],
    shares_by_code: Mapping[str, Sequence[SharePoint]],
    share_errors: Mapping[str, str],
) -> float:
    above_ma20: list[bool] = []
    above_ma60: list[bool] = []
    rising_ma20: list[bool] = []
    positive_5d: list[bool] = []
    positive_flow_5d: list[bool] = []
    for row in rows:
        code = str(row["code"])
        bars = bars_by_code.get(str(row["code"]), ())
        if len(bars) < 60:
            continue
        ma20 = fmean(bar.close for bar in bars[-20:])
        ma60 = fmean(bar.close for bar in bars[-60:])
        prior_ma20 = fmean(bar.close for bar in bars[-25:-5])
        above_ma20.append(bars[-1].close > ma20)
        above_ma60.append(bars[-1].close > ma60)
        rising_ma20.append(ma20 > prior_ma20)
        positive_5d.append(_return_pct(bars, 5) > 0)
        flows, _ = _flows_for_code(
            code=code,
            bars=bars,
            points=shares_by_code.get(code, ()),
            error=share_errors.get(code),
        )
        if flows[5].value_cny is not None:
            positive_flow_5d.append(flows[5].value_cny > 0)
    components = [
        sum(values) / len(values) * 100
        for values in (
            above_ma20,
            above_ma60,
            rising_ma20,
            positive_5d,
            positive_flow_5d,
        )
        if values
    ]
    return 50.0 if not components else fmean(components)


def _return_pct(bars: Sequence[DailyBar], window: int) -> float:
    return (bars[-1].close / bars[-window - 1].close - 1) * 100


def _rsi14(bars: Sequence[DailyBar]) -> float:
    changes = [right.close - left.close for left, right in zip(bars[-15:-1], bars[-14:])]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = fmean(gains)
    average_loss = fmean(losses)
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100 - 100 / (1 + relative_strength)


def _volume_ratio(bars: Sequence[DailyBar]) -> float | None:
    if len(bars) < 25:
        return None
    baseline = fmean(bar.volume for bar in bars[-25:-5])
    if not math.isfinite(baseline) or baseline <= 0:
        return None
    return fmean(bar.volume for bar in bars[-5:]) / baseline


def _latest_share(
    points: Sequence[SharePoint], latest_date: Any
) -> SharePoint | None:
    matching = [point for point in points if point.date == latest_date]
    return matching[0] if len(matching) == 1 else None


def build_panorama(
    *,
    bars: Sequence[DailyBar],
    points: Sequence[SharePoint],
    lookback: int = 720,
) -> dict[str, Any]:
    """Align bars + shares into UI panorama series (亿元 / 亿份) and summary cards."""
    if not bars:
        return {"series": [], "summary": _empty_panorama_summary()}

    window = list(bars[-lookback:]) if lookback > 0 else list(bars)
    by_date: dict[date, SharePoint] = {}
    for point in points:
        if math.isfinite(point.shares) and point.shares >= 0:
            by_date[point.date] = point

    series: list[dict[str, Any]] = []
    prev_shares: float | None = None
    for bar in window:
        point = by_date.get(bar.date)
        shares = float(point.shares) if point is not None else None
        net_flow_yi: float | None = None
        if shares is not None and prev_shares is not None:
            net_flow_yi = round((shares - prev_shares) * bar.close / 1e8, 4)
        if shares is not None:
            prev_shares = shares
        amount_yi = (
            round(float(bar.turnover_cny) / 1e8, 4)
            if math.isfinite(bar.turnover_cny)
            else None
        )
        series.append(
            {
                "date": bar.date.isoformat(),
                "netFlowYi": net_flow_yi,
                "amountYi": amount_yi,
                "sharesYi": round(shares / 1e8, 4) if shares is not None else None,
                "close": round(float(bar.close), 4) if math.isfinite(bar.close) else None,
            }
        )

    return {"series": series, "summary": _panorama_summary(series)}


def _empty_panorama_summary() -> dict[str, Any]:
    return {
        "avgNetFlowYi": None,
        "avgAmountYi": None,
        "sumNetFlowYi": None,
        "flow3Yi": None,
        "flow5Yi": None,
        "flow10Yi": None,
    }


def _sum_last_n_flows(flows: Sequence[float], n: int) -> float | None:
    """Sum the last N daily net-flow points (亿元); None if sample shorter than N."""
    if n <= 0 or len(flows) < n:
        return None
    return round(sum(flows[-n:]), 4)


def _panorama_summary(series: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    flows = [
        float(item["netFlowYi"])
        for item in series
        if item.get("netFlowYi") is not None and math.isfinite(float(item["netFlowYi"]))
    ]
    amounts = [
        float(item["amountYi"])
        for item in series
        if item.get("amountYi") is not None and math.isfinite(float(item["amountYi"]))
    ]
    avg_flow = round(fmean(flows), 4) if flows else None
    avg_amount = round(fmean(amounts), 4) if amounts else None
    sum_flow = round(sum(flows), 4) if flows else None
    return {
        "avgNetFlowYi": avg_flow,
        "avgAmountYi": avg_amount,
        "sumNetFlowYi": sum_flow,
        "flow3Yi": _sum_last_n_flows(flows, 3),
        "flow5Yi": _sum_last_n_flows(flows, 5),
        "flow10Yi": _sum_last_n_flows(flows, 10),
    }


def _resolve_weekly_fields(
    *,
    code: str,
    bars: Sequence[DailyBar],
    sector: str,
    weekly_map: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    cached = weekly_map.get(code)
    if cached and cached.get("regimeNow"):
        return regime_to_row_fields(cached)
    weekly = aggregate_weekly_bars(bars)
    if len(weekly) >= 40:
        selected = select_best_params(weekly, sector=sector)
        if selected.get("regimeNow"):
            return regime_to_row_fields(selected)
    try:
        regime = compute_weekly_regime(
            bars,
            fast=DEFAULT_MA_PAIR[0],
            slow=DEFAULT_MA_PAIR[1],
            macd_mode=DEFAULT_MACD_MODE,
        )
        return {
            "weeklyMacd": asdict(regime.macd),
            "weeklyMa": asdict(regime.ma),
            "weeklyTrend": regime.weekly_trend,
            "maRegime": {
                "aligned": regime.ma.aligned,
                "fast": regime.ma.fast,
                "slow": regime.ma.slow,
                "macdMode": regime.macd_mode,
            },
            "backtestPass": False,
            "bestWeeklyParams": {
                "fast": DEFAULT_MA_PAIR[0],
                "slow": DEFAULT_MA_PAIR[1],
                "macdMode": DEFAULT_MACD_MODE,
            },
            "weeklyBacktestMetrics": None,
            "weeklyLongEligible": regime.long_eligible,
            "trend": regime.weekly_trend,
        }
    except Exception:
        return {
            "weeklyMacd": None,
            "weeklyMa": None,
            "weeklyTrend": "震荡",
            "maRegime": None,
            "backtestPass": False,
            "bestWeeklyParams": {
                "fast": DEFAULT_MA_PAIR[0],
                "slow": DEFAULT_MA_PAIR[1],
                "macdMode": DEFAULT_MACD_MODE,
            },
            "weeklyBacktestMetrics": None,
            "weeklyLongEligible": False,
            "trend": "震荡",
        }


def _theme_for(
    context: Mapping[str, Any], sector: str, market: str
) -> Mapping[str, Any]:
    global_markets = {"US", "BR", "SEA", "JP", "DE"}
    theme_name = (
        "global_equity"
        if market.upper() in global_markets and "global_equity" in context["themes"]
        else context["sector_theme"][sector]
    )
    return context["themes"][theme_name]


def _evidence_reason(evidence: Mapping[str, Any]) -> str:
    label = f"{evidence['publisher']}｜{evidence['date']}｜{evidence['title']}"
    return f"{evidence['text']} [{label}]({evidence['url']})"


def _technical_reason(
    *,
    close: float,
    ma20: float,
    ma60: float,
    ma20_rising: bool,
    ret5: float,
    ret10: float,
    ret20: float,
    rsi14: float,
    kdj_state: str,
    macd_state: str,
    weekly_trend: str | None = None,
    weekly_macd_state: str | None = None,
    backtest_pass: bool | None = None,
    volume_price_label: str | None = None,
) -> str:
    relative = "上方" if close > ma20 else "下方"
    long_relative = "上方" if close > ma60 else "下方"
    slope = "上行" if ma20_rising else "未上行"
    if backtest_pass is True:
        gate = "回测门控通过"
    elif backtest_pass is False:
        gate = "回测门控未过"
    else:
        gate = "回测门控未知"
    weekly_bit = (
        f"周线趋势{weekly_trend or '—'}，周MACD={weekly_macd_state or '—'}，{gate}；"
    )
    vp_bit = f"量价={volume_price_label or '—'}；"
    return (
        f"{weekly_bit}{vp_bit}"
        f"收盘价位于MA20{relative}、MA60{long_relative}，MA20{slope}；"
        f"5/10/20日涨跌幅分别为{ret5:+.2f}%/{ret10:+.2f}%/{ret20:+.2f}%，"
        f"RSI14={rsi14:.1f}，KDJ={kdj_state}，日MACD={macd_state}。"
    )


def _sentiment_reason(
    score: float,
    label: str,
    flows: Mapping[int, FlowWindow],
    volume_ratio: float | None,
    breadth: float,
    missing_inputs: Sequence[str],
) -> str:
    flow_text = "/".join(_flow_reason_value(flows[window]) for window in (5, 10, 20))
    volume_text = "N/A" if volume_ratio is None else f"{volume_ratio:.2f}倍"
    missing = "无" if not missing_inputs else "、".join(missing_inputs)
    return (
        f"情绪分数{score:.1f}（{label}）；5/10/20日份额净流入为{flow_text}，"
        f"5日成交量相对前20日为{volume_text}，代表池综合宽度{breadth:.1f}%，"
        f"缺失分项：{missing}。"
    )


def _flow_reason_value(flow: FlowWindow) -> str:
    if flow.value_cny is None:
        return f"N/A({flow.reason})"
    return f"{flow.value_cny / 100_000_000:+.2f}亿"


def _action_rank(action: str) -> int:
    return {"技术候选": 0, "观察": 1, "不追涨": 2, "暂缓": 3}.get(action, 4)
