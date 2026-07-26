#!/usr/bin/env python3.12
"""Per-ETF weekly MACD + MA backtest with small param grid and passGate."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.market_data import DailyBar, MarketDataError, PublicMarketDataProvider, parse_eastmoney_bars, parse_tencent_bars, _secid, _tencent_symbol
from src.reporting import ReportDataError
from src.weekly_signals import (
    MAX_DD_GATE,
    MIN_SAMPLES,
    aggregate_weekly_bars,
    decide_action,
    regime_to_row_fields,
    select_best_params,
    volume_price_from_ratio_ret,
    volume_price_to_dict,
)

MODULE_ROOT = Path(__file__).resolve().parent
SHANGHAI = ZoneInfo("Asia/Shanghai")
BAR_LIMIT = 800


class LongHistoryProvider(PublicMarketDataProvider):
    EASTMONEY_BARS = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get?"
        "secid={secid}&ut=7eea3edcaed734bea9cbfc24409ed989&klt=101&fqt=1&end=20500101"
        f"&lmt={BAR_LIMIT}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    )
    TENCENT_BARS = (
        "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get?"
        f"param={{symbol}},day,,,{BAR_LIMIT},qfq"
    )

    def get_daily_bars(self, code: str) -> list[DailyBar]:
        fetched_at = self.clock()
        try:
            payload = self._json(self.TENCENT_BARS.format(symbol=_tencent_symbol(code)))
            return list(parse_tencent_bars(payload, code, fetched_at))
        except MarketDataError:
            payload = self._json(self.EASTMONEY_BARS.format(secid=_secid(code)))
            return list(parse_eastmoney_bars(payload, fetched_at))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--seed",
        type=Path,
        default=MODULE_ROOT / "reports" / "representative-technical-review-2026-07-24.json",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Default: reports/etf68-weekly-macd-ma-backtest-<data_date>.json",
    )
    p.add_argument(
        "--apply-review",
        type=Path,
        default=None,
        help="If set, rewrite action/trend/weekly fields on this review JSON in place",
    )
    p.add_argument("--workers", type=int, default=6)
    return p.parse_args()


def analyze_one(code: str, name: str, sector: str, bars: list[DailyBar]) -> dict[str, Any]:
    weekly = aggregate_weekly_bars(bars)
    base = {
        "code": code,
        "name": name,
        "sector": sector,
        "dailyBars": len(bars),
        "weeklyBars": len(weekly),
    }
    if len(weekly) < 30:
        return {
            **base,
            "passGate": False,
            "insufficient": True,
            "reason": "insufficient_weekly_bars",
            "bestParams": {"fast": 10, "slow": 20, "macdMode": "strict"},
            "metrics": None,
            "regimeNow": None,
        }
    try:
        selected = select_best_params(weekly, sector=sector)
    except ReportDataError as exc:
        return {
            **base,
            "passGate": False,
            "insufficient": True,
            "reason": exc.reason,
            "bestParams": {"fast": 10, "slow": 20, "macdMode": "strict"},
            "metrics": None,
            "regimeNow": None,
        }
    return {**base, "insufficient": False, **selected}


def apply_to_review(review_path: Path, by_code: dict[str, dict[str, Any]]) -> None:
    report = json.loads(review_path.read_text(encoding="utf-8"))
    for row in report["rows"]:
        code = str(row["code"])
        bt = by_code.get(code)
        if not bt:
            row["backtestPass"] = False
            row["weeklyTrend"] = row.get("trend", "震荡")
            continue
        fields = regime_to_row_fields(bt) if bt.get("regimeNow") else {
            "weeklyMacd": None,
            "weeklyMa": None,
            "weeklyTrend": "震荡",
            "maRegime": bt.get("bestParams"),
            "backtestPass": False,
            "bestWeeklyParams": bt.get("bestParams") or {},
            "weeklyBacktestMetrics": bt.get("metrics"),
            "weeklyLongEligible": False,
            "trend": "震荡",
        }
        if bt.get("insufficient") or not bt.get("regimeNow"):
            fields["trend"] = "震荡"
            fields["weeklyTrend"] = "震荡"
            fields["backtestPass"] = False
            fields["weeklyLongEligible"] = False
        row.update(fields)
        daily_ma = "多头" if row.get("ma20_rising") and row.get("close", 0) > row.get("ma20", 0) > row.get("ma60", 0) else (
            "空头" if row.get("close", 0) < row.get("ma20", 0) and row.get("close", 0) < row.get("ma60", 0) else "震荡"
        )
        row["dailyMaTrend"] = daily_ma
        sentiment = float(row.get("sentiment", {}).get("score") or 50)
        vp = volume_price_from_ratio_ret(
            row.get("volume_ratio") if isinstance(row.get("volume_ratio"), (int, float)) else None,
            float(row["ret5_pct"]) if row.get("ret5_pct") is not None else None,
            basis="daily5",
        )
        row["volumePrice"] = volume_price_to_dict(vp)
        row["action"] = decide_action(
            weekly_trend=str(row.get("weeklyTrend") or "震荡"),
            long_eligible=bool(row.get("weeklyLongEligible")),
            backtest_pass=bool(row.get("backtestPass")),
            ret1=float(row.get("ret1_pct") or 0),
            distance_ma20=float(row.get("distance_ma20_pct") or 0),
            sentiment=sentiment,
            volume_price_bearish=vp.bearish,
            volume_price_bullish=vp.bullish,
        )
    # re-sort like build_report
    rank = {"技术候选": 0, "观察": 1, "不追涨": 2, "暂缓": 3}
    report["rows"].sort(
        key=lambda r: (
            rank.get(str(r.get("action")), 9),
            -float((r.get("sentiment") or {}).get("score") or 0),
            -float(r.get("ret20_pct") or 0),
        )
    )
    report["weekly_framework"] = {
        "primary": "weekly_macd_plus_ma",
        "gate": {"minSamples": MIN_SAMPLES, "maxDdPct": MAX_DD_GATE},
        "volumePrice": "量升价增看多；量升价不涨看空并拦截技术候选",
    }
    review_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    seed = json.loads(args.seed.read_text(encoding="utf-8"))
    data_date = str(seed.get("data_date") or "")
    out = args.output or (MODULE_ROOT / "reports" / f"etf68-weekly-macd-ma-backtest-{data_date}.json")
    rows_meta = list(seed.get("rows") or [])
    provider = LongHistoryProvider(calendar_provider=object(), catalyst_provider=object())

    results: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}

    def work(meta: dict[str, Any]) -> tuple[str, dict[str, Any] | None, str | None]:
        code = str(meta["code"])
        try:
            bars = list(provider.get_daily_bars(code))
            # trim to as-of data_date if present
            if data_date:
                from datetime import date as date_cls
                as_of = date_cls.fromisoformat(data_date)
                bars = [b for b in bars if b.date <= as_of]
            row = analyze_one(code, str(meta.get("name") or ""), str(meta.get("sector") or ""), bars)
            return code, row, None
        except Exception as exc:
            return code, None, getattr(exc, "reason", str(exc) or type(exc).__name__)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = [ex.submit(work, m) for m in rows_meta]
        for fut in as_completed(futs):
            code, row, err = fut.result()
            if err:
                errors[code] = err
            elif row:
                results[code] = row

    ordered = []
    for meta in rows_meta:
        code = str(meta["code"])
        if code in results:
            ordered.append(results[code])
        else:
            ordered.append(
                {
                    "code": code,
                    "name": meta.get("name"),
                    "sector": meta.get("sector"),
                    "passGate": False,
                    "insufficient": True,
                    "reason": errors.get(code, "missing"),
                    "bestParams": {"fast": 10, "slow": 20, "macdMode": "strict"},
                    "metrics": None,
                    "regimeNow": None,
                }
            )

    payload = {
        "asOf": data_date,
        "generatedAt": datetime.now(SHANGHAI).isoformat(),
        "method": "weekly_macd_plus_ma_per_etf_grid",
        "rules": {
            "maGrid": [[5, 10], [10, 20], [10, 30], [20, 40]],
            "macdModes": ["strict", "loose"],
            "forwardWeeks": 4,
            "minSamples": MIN_SAMPLES,
            "maxDdGate": MAX_DD_GATE,
            "defaultParams": {"fast": 10, "slow": 20, "macdMode": "strict"},
        },
        "summary": {
            "etfs": len(ordered),
            "passGate": sum(1 for r in ordered if r.get("passGate")),
            "insufficient": sum(1 for r in ordered if r.get("insufficient")),
            "errors": errors,
        },
        "rows": ordered,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.apply_review:
        by_code = {str(r["code"]): r for r in ordered}
        apply_to_review(args.apply_review, by_code)

    print(
        json.dumps(
            {
                "output": str(out),
                "asOf": data_date,
                "etfs": len(ordered),
                "passGate": payload["summary"]["passGate"],
                "insufficient": payload["summary"]["insufficient"],
                "appliedReview": str(args.apply_review) if args.apply_review else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
