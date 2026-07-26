#!/usr/bin/env python3.12
"""Backtest daily KDJ / MACD state positions vs forward returns per ETF.

For each fund, measures historical forward-10d returns conditional on each
KDJ and MACD state, then emits:
  - best uptrend reference states
  - best downtrend reference states
  - current-state reading vs history
  - one canvas column string `kdjMacdRef`
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from src.market_data import DailyBar, MarketDataError, PublicMarketDataProvider, parse_eastmoney_bars, parse_tencent_bars, _secid, _tencent_symbol

# Reuse indicator state series from edge analyzer (same definitions as report).
from analyze_edge_conditions import ConditionStats, kdj_state_series, macd_state_series

MODULE_ROOT = Path(__file__).resolve().parent
REPORTS = MODULE_ROOT / "reports"
SHANGHAI = ZoneInfo("Asia/Shanghai")

FORWARD_DAYS = 10
MIN_SAMPLES = 8
BAR_LIMIT = 400
START_I = 30  # after MACD warm-up (~26) + buffer


def _opener(url: str, timeout: int = 15):
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    return urlopen(req, timeout=timeout)


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

    def get_daily_bars(self, code: str) -> Sequence[DailyBar]:
        fetched_at = self.clock()
        try:
            payload = self._json(self.TENCENT_BARS.format(symbol=_tencent_symbol(code)))
            return parse_tencent_bars(payload, code, fetched_at)
        except MarketDataError:
            payload = self._json(self.EASTMONEY_BARS.format(secid=_secid(code)))
            return parse_eastmoney_bars(payload, fetched_at)


def _fmt_stat(st: ConditionStats) -> str:
    return (
        f"样本{st.n}｜胜率{st.win_rate * 100:.0f}%"
        f"｜后{FORWARD_DAYS}日均{st.mean:+.2f}%｜确定性{st.deterministic_score:+.2f}%"
    )


def _rank_states(
    stats: dict[str, ConditionStats],
    *,
    prefer: str,
) -> list[tuple[str, ConditionStats]]:
    """prefer=up → highest deterministic score; prefer=down → lowest mean (most negative)."""
    eligible = [(k, st) for k, st in stats.items() if st.n >= MIN_SAMPLES]
    if prefer == "up":
        return sorted(eligible, key=lambda x: x[1].deterministic_score, reverse=True)
    # downtrend: prefer low mean; use -deterministic as tie-breaker toward more negative certainty
    return sorted(eligible, key=lambda x: (x[1].mean, x[1].deterministic_score))


def analyze_code(code: str, name: str, bars: Sequence[DailyBar], current_kdj: str | None, current_macd: str | None) -> dict[str, Any]:
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    n = len(closes)
    kdj_s = kdj_state_series(highs, lows, closes)
    macd_s = macd_state_series(closes)

    kdj_stats: dict[str, ConditionStats] = defaultdict(ConditionStats)
    macd_stats: dict[str, ConditionStats] = defaultdict(ConditionStats)
    combo_stats: dict[str, ConditionStats] = defaultdict(ConditionStats)

    for i in range(START_I, n - FORWARD_DAYS):
        kdj = kdj_s[i]
        macd = macd_s[i]
        if not kdj or not macd:
            continue
        fwd = (closes[i + FORWARD_DAYS] / closes[i] - 1) * 100
        kdj_stats[kdj].add(fwd)
        macd_stats[macd].add(fwd)
        combo_stats[f"KDJ{kdj}+MACD{macd}"].add(fwd)

    # current states: prefer review snapshot; else last bar
    cur_kdj = current_kdj or kdj_s[n - 1] or "—"
    cur_macd = current_macd or macd_s[n - 1] or "—"

    kdj_up = _rank_states(kdj_stats, prefer="up")
    kdj_dn = _rank_states(kdj_stats, prefer="down")
    macd_up = _rank_states(macd_stats, prefer="up")
    macd_dn = _rank_states(macd_stats, prefer="down")
    combo_up = _rank_states(combo_stats, prefer="up")
    combo_dn = _rank_states(combo_stats, prefer="down")

    def pack(label: str | None, st: ConditionStats | None) -> dict[str, Any] | None:
        if not label or st is None:
            return None
        return {
            "state": label,
            "samples": st.n,
            "win_rate_pct": round(st.win_rate * 100, 1),
            "avg_fwd_ret_pct": round(st.mean, 2),
            "deterministic_score_pct": round(st.deterministic_score, 2),
        }

    best_up_kdj = pack(kdj_up[0][0], kdj_up[0][1]) if kdj_up else None
    best_dn_kdj = pack(kdj_dn[0][0], kdj_dn[0][1]) if kdj_dn else None
    best_up_macd = pack(macd_up[0][0], macd_up[0][1]) if macd_up else None
    best_dn_macd = pack(macd_dn[0][0], macd_dn[0][1]) if macd_dn else None
    best_up_combo = pack(combo_up[0][0], combo_up[0][1]) if combo_up else None
    best_dn_combo = pack(combo_dn[0][0], combo_dn[0][1]) if combo_dn else None

    def cur_read(kind: str, state: str, stats: dict[str, ConditionStats]) -> dict[str, Any]:
        st = stats.get(state)
        if st is None or st.n < MIN_SAMPLES:
            return {
                "indicator": kind,
                "state": state,
                "bias": "样本不足",
                "samples": st.n if st else 0,
                "avg_fwd_ret_pct": None,
                "win_rate_pct": None,
                "text": f"现{kind}{state}(样本不足)",
            }
        # bias vs zero mean
        if st.mean >= 0.5 and st.win_rate >= 0.55:
            bias = "偏多"
        elif st.mean <= -0.5 and st.win_rate <= 0.45:
            bias = "偏空"
        elif st.mean >= 0:
            bias = "中性偏多"
        else:
            bias = "中性偏空"
        return {
            "indicator": kind,
            "state": state,
            "bias": bias,
            "samples": st.n,
            "avg_fwd_ret_pct": round(st.mean, 2),
            "win_rate_pct": round(st.win_rate * 100, 1),
            "deterministic_score_pct": round(st.deterministic_score, 2),
            "text": f"现{kind}{state}→史后{FORWARD_DAYS}日均{st.mean:+.2f}%/胜率{st.win_rate*100:.0f}%（{bias}）",
        }

    cur_kdj_read = cur_read("KDJ", cur_kdj, kdj_stats)
    cur_macd_read = cur_read("MACD", cur_macd, macd_stats)

    # Column text: up ref | down ref | current
    up_parts: list[str] = []
    if best_up_kdj and best_up_kdj["avg_fwd_ret_pct"] is not None and best_up_kdj["avg_fwd_ret_pct"] > 0:
        up_parts.append(f"KDJ{best_up_kdj['state']}({best_up_kdj['avg_fwd_ret_pct']:+.2f}%)")
    if best_up_macd and best_up_macd["avg_fwd_ret_pct"] is not None and best_up_macd["avg_fwd_ret_pct"] > 0:
        up_parts.append(f"MACD{best_up_macd['state']}({best_up_macd['avg_fwd_ret_pct']:+.2f}%)")
    dn_parts: list[str] = []
    weak_parts: list[str] = []
    if best_dn_kdj and best_dn_kdj["avg_fwd_ret_pct"] is not None:
        piece = f"KDJ{best_dn_kdj['state']}({best_dn_kdj['avg_fwd_ret_pct']:+.2f}%)"
        if best_dn_kdj["avg_fwd_ret_pct"] < 0:
            dn_parts.append(piece)
        else:
            weak_parts.append(piece)
    if best_dn_macd and best_dn_macd["avg_fwd_ret_pct"] is not None:
        piece = f"MACD{best_dn_macd['state']}({best_dn_macd['avg_fwd_ret_pct']:+.2f}%)"
        if best_dn_macd["avg_fwd_ret_pct"] < 0:
            dn_parts.append(piece)
        else:
            weak_parts.append(piece)

    if best_up_combo and best_up_combo["avg_fwd_ret_pct"] is not None and best_up_combo["avg_fwd_ret_pct"] > 0:
        up_combo_txt = f"{best_up_combo['state']}({best_up_combo['avg_fwd_ret_pct']:+.2f}%)"
    else:
        up_combo_txt = "—"
    if best_dn_combo and best_dn_combo["avg_fwd_ret_pct"] is not None and best_dn_combo["avg_fwd_ret_pct"] < 0:
        dn_combo_txt = f"{best_dn_combo['state']}({best_dn_combo['avg_fwd_ret_pct']:+.2f}%)"
    else:
        dn_combo_txt = "—"

    if not up_parts and not dn_parts and not weak_parts:
        ref = "日线KDJ/MACD分状态样本不足，暂无分位参考"
    else:
        down_txt = "/".join(dn_parts) if dn_parts else ("相对最弱:" + "/".join(weak_parts) if weak_parts else "—")
        ref = (
            f"上涨参考:{'/'.join(up_parts) if up_parts else '—'}｜"
            f"下跌参考:{down_txt}｜"
            f"组合多:{up_combo_txt}｜组合空:{dn_combo_txt}｜"
            f"{cur_kdj_read['text']}；{cur_macd_read['text']}"
        )

    def table(stats: dict[str, ConditionStats]) -> list[dict[str, Any]]:
        rows = []
        for state, st in sorted(stats.items(), key=lambda x: x[1].deterministic_score, reverse=True):
            if st.n < 1:
                continue
            rows.append(
                {
                    "state": state,
                    "samples": st.n,
                    "win_rate_pct": round(st.win_rate * 100, 1),
                    "avg_fwd_ret_pct": round(st.mean, 2),
                    "deterministic_score_pct": round(st.deterministic_score, 2) if st.n >= MIN_SAMPLES else None,
                    "eligible": st.n >= MIN_SAMPLES,
                }
            )
        return rows

    return {
        "code": code,
        "name": name,
        "bars": n,
        "forwardDays": FORWARD_DAYS,
        "minSamples": MIN_SAMPLES,
        "currentKdj": cur_kdj,
        "currentMacd": cur_macd,
        "currentKdjRead": cur_kdj_read,
        "currentMacdRead": cur_macd_read,
        "bestUpKdj": best_up_kdj,
        "bestDownKdj": best_dn_kdj,
        "bestUpMacd": best_up_macd,
        "bestDownMacd": best_dn_macd,
        "bestUpCombo": best_up_combo,
        "bestDownCombo": best_dn_combo,
        "kdjTable": table(kdj_stats),
        "macdTable": table(macd_stats),
        "kdjMacdRef": ref,
    }


def collect_bars(codes: list[str], provider: LongHistoryProvider, workers: int) -> tuple[dict[str, Sequence[DailyBar]], dict[str, str]]:
    out: dict[str, Sequence[DailyBar]] = {}
    errors: dict[str, str] = {}

    def one(code: str) -> tuple[str, Sequence[DailyBar]]:
        return code, provider.get_daily_bars(code)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(one, c): c for c in codes}
        for fut in as_completed(futs):
            code = futs[fut]
            try:
                c, bars = fut.result()
                out[c] = bars
            except Exception as exc:  # noqa: BLE001
                errors[code] = getattr(exc, "reason", None) or str(exc)
    return out, errors


def build(day: str, workers: int) -> dict[str, Any]:
    seed_path = REPORTS / f"representative-technical-review-{day}.json"
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    meta = {str(r["code"]): r for r in seed["rows"]}
    codes = list(meta.keys())

    provider = LongHistoryProvider(
        calendar_provider=object(),
        catalyst_provider=object(),
        opener=_opener,
        clock=lambda: datetime.now(timezone.utc),
    )
    bars_by, errors = collect_bars(codes, provider, workers=workers)
    if errors:
        for code, reason in list(errors.items()):
            try:
                time.sleep(0.3)
                bars_by[code] = provider.get_daily_bars(code)
                errors.pop(code, None)
            except Exception as exc:  # noqa: BLE001
                errors[code] = getattr(exc, "reason", None) or str(exc)
    if errors:
        raise RuntimeError(f"bar_fetch_failed:{errors}")

    rows = []
    for code in codes:
        r = meta[code]
        kdj = (r.get("kdj") or {}).get("state")
        macd = (r.get("macd") or {}).get("state")
        rows.append(analyze_code(code, str(r["name"]), bars_by[code], kdj, macd))

    return {
        "asOf": seed.get("data_date") or day,
        "generatedAt": datetime.now(SHANGHAI).isoformat(),
        "methodology": {
            "indicators": ["daily_KDJ(9)", "daily_MACD(12/26/9)"],
            "forwardDays": FORWARD_DAYS,
            "minSamples": MIN_SAMPLES,
            "barLimit": BAR_LIMIT,
            "score": "mean_fwd_ret - std/sqrt(n) for up-rank; lowest mean for down-rank",
            "note": "分状态历史前瞻收益参考，非实盘保证；与周线主框架独立，仅作日线辅助列。",
        },
        "rows": rows,
    }


def main() -> int:
    # Direct market access — local proxy often breaks Eastmoney/Tencent.
    os.environ["NO_PROXY"] = "*"
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(k, None)

    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-07-24")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    out = args.output or (REPORTS / f"etf68-daily-kdj-macd-backtest-{args.date}.json")
    data = build(args.date, workers=args.workers)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} rows={len(data['rows'])}")
    for r in data["rows"][:5]:
        print(r["code"], r["kdjMacdRef"][:100])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
