"""Rotation strategy config defaults, validation, and builtin presets."""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

MOMENTUM_METHODS = frozenset({"simple", "slope", "weighted_slope", "rsrs", "log_trend"})
DAY_COUNT_TYPES = frozenset({"trading", "calendar"})

DEFAULT_POOL = ["513100", "159915", "510300", "518880"]
DEFAULT_NAMES = {
    "513100": "纳指ETF",
    "159915": "创业板ETF",
    "510300": "沪深300ETF",
    "518880": "黄金ETF",
    "512890": "红利低波ETF",
}

XIAOXIN_PRESET_ID = "xiaoxin-public-approx"
ZHIBEI_CLONE_ID = "zhibei-official-clone"

# Website alias: log_trend ≡ slope (ann×R² on log prices)
MOMENTUM_ALIASES = {"log_trend": "slope"}


def _now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def default_config() -> dict[str, Any]:
    return {
        "etf_pool": list(DEFAULT_POOL),
        "etf_names": dict(DEFAULT_NAMES),
        "momentum": {
            "method": "slope",
            "window": 20,
            "secondary_enabled": False,
            "secondary_method": "simple",
            "secondary_window": 60,
            "secondary_min": 0.0,
        },
        "selection": {
            "score_min": None,
            "score_max": None,
            "top_n": 1,
            "equal_weight": False,
        },
        "holding": {
            "min_hold_days": 8,
            "day_count_type": "trading",
            "fallback_code": None,
        },
        "take_profit": {
            "enabled": False,
            "threshold": 0.18,
            "cooldown_days": 8,
        },
        "stop_loss": {
            "enabled": False,
            "pct_enabled": True,
            "pct_threshold": 0.08,
            "drawdown_enabled": False,
            "drawdown_threshold": 0.05,
            "cooldown_days": 0,
        },
        "extreme_filter": {
            "skip_limit_up": False,
            "skip_limit_down": False,
        },
        "condition_filter": {
            "price_above_ma": False,
            "ma_period": 60,
            "ma_bull": False,
            "ma_fast": 20,
            "ma_slow": 60,
        },
        "market_timing": {
            "enabled": False,
            "benchmark_code": "510300",
        },
        "costs": {
            "commission_rate": 0.0001,
            "slippage_rate": 0.0005,
        },
        "backtest": {
            "initial_nav": 1000.0,
            # Align local window with 小薪公开实盘 start when bars allow.
            "start_date": "2024-11-11",
            "end_date": None,
        },
        "approx_label": "本地近似",
        "source": "local",
    }


DEFAULT_XIAOXIN_CONFIG = default_config()


def deep_merge(base: dict[str, Any], overlay: dict[str, Any] | None) -> dict[str, Any]:
    out = copy.deepcopy(base)
    if not overlay:
        return out
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    cfg = deep_merge(default_config(), raw or {})
    pool = [str(c).zfill(6)[-6:] for c in (cfg.get("etf_pool") or []) if str(c).strip()]
    if not pool:
        pool = list(DEFAULT_POOL)
    # preserve order, unique
    seen: set[str] = set()
    ordered: list[str] = []
    for code in pool:
        if code not in seen:
            seen.add(code)
            ordered.append(code)
    cfg["etf_pool"] = ordered
    names = cfg.get("etf_names") or {}
    cfg["etf_names"] = {
        code: str(names.get(code) or DEFAULT_NAMES.get(code) or code) for code in ordered
    }
    return cfg


def validate_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    cfg = normalize_config(raw)
    mom = cfg["momentum"]
    mom["method"] = MOMENTUM_ALIASES.get(str(mom["method"]), str(mom["method"]))
    mom["secondary_method"] = MOMENTUM_ALIASES.get(
        str(mom["secondary_method"]), str(mom["secondary_method"])
    )
    concrete = {"simple", "slope", "weighted_slope", "rsrs"}
    if mom["method"] not in concrete:
        raise ValueError(f"unsupported_momentum_method:{mom['method']}")
    if mom["secondary_method"] not in concrete:
        raise ValueError(f"unsupported_secondary_momentum_method:{mom['secondary_method']}")
    for key in ("window", "secondary_window"):
        w = int(mom[key])
        if w < 1 or w > 120:
            raise ValueError(f"momentum_{key}_out_of_range:{w}")
        mom[key] = w
    sel = cfg["selection"]
    top_n = int(sel["top_n"])
    if top_n < 1 or top_n > 10:
        raise ValueError(f"top_n_out_of_range:{top_n}")
    sel["top_n"] = top_n
    hold = cfg["holding"]
    hold["min_hold_days"] = max(1, min(60, int(hold["min_hold_days"])))
    if hold["day_count_type"] not in DAY_COUNT_TYPES:
        raise ValueError(f"unsupported_day_count_type:{hold['day_count_type']}")
    fb = hold.get("fallback_code")
    if fb:
        hold["fallback_code"] = str(fb).zfill(6)[-6:]
    else:
        hold["fallback_code"] = None
    cond = cfg["condition_filter"]
    cond["ma_period"] = max(1, min(250, int(cond["ma_period"])))
    cond["ma_fast"] = max(1, min(250, int(cond["ma_fast"])))
    cond["ma_slow"] = max(1, min(250, int(cond["ma_slow"])))
    if cond["ma_bull"] and cond["ma_fast"] >= cond["ma_slow"]:
        raise ValueError("ma_fast_must_be_lt_ma_slow")
    mt = cfg["market_timing"]
    mt["benchmark_code"] = str(mt.get("benchmark_code") or "510300").zfill(6)[-6:]
    tp = cfg["take_profit"]
    tp["threshold"] = float(tp["threshold"])
    tp["cooldown_days"] = max(0, min(90, int(tp["cooldown_days"])))
    sl = cfg["stop_loss"]
    sl["pct_threshold"] = float(sl["pct_threshold"])
    sl["drawdown_threshold"] = float(sl["drawdown_threshold"])
    sl["cooldown_days"] = max(0, min(90, int(sl["cooldown_days"])))
    costs = cfg["costs"]
    costs["commission_rate"] = max(0.0, float(costs["commission_rate"]))
    costs["slippage_rate"] = max(0.0, float(costs["slippage_rate"]))
    bt = cfg["backtest"]
    bt["initial_nav"] = float(bt.get("initial_nav") or 1000.0)
    start = bt.get("start_date")
    end = bt.get("end_date")
    bt["start_date"] = str(start) if start else None
    bt["end_date"] = str(end) if end else None
    return cfg


def builtin_strategies() -> list[dict[str, Any]]:
    from .zhibei_import import builtin_zhibei_clone

    return [
        builtin_zhibei_clone(),
        {
            "id": XIAOXIN_PRESET_ID,
            "name": "ETF轮动实盘（本地近似·四池）",
            "readonly": True,
            "approx": True,
            "updated_at": _now_iso(),
            "config": validate_config(DEFAULT_XIAOXIN_CONFIG),
        },
    ]


def strategy_record(
    *,
    strategy_id: str,
    name: str,
    config: dict[str, Any],
    readonly: bool = False,
    approx: bool = False,
) -> dict[str, Any]:
    return {
        "id": strategy_id,
        "name": name,
        "readonly": readonly,
        "approx": approx,
        "updated_at": _now_iso(),
        "config": validate_config(config),
    }
