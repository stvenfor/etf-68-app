"""Import 智贝/小薪 website strategy config into local rotation schema."""

from __future__ import annotations

from typing import Any

from .config import DEFAULT_NAMES, validate_config

# Website scoring_method → local momentum.method
SCORE_METHOD_MAP = {
    "log_trend": "slope",  # score ≈ (ann_return/100) * R² on log-price OLS
    "simple_return": "simple",
    "simple": "simple",
    "slope": "slope",
    "weighted_slope": "weighted_slope",
    "rsrs": "rsrs",
}

ZHIBEI_CLONE_ID = "zhibei-official-clone"
# Latest website「我的策略」id (四池：创业板/纳指/红利低波/黄金)
DEFAULT_ZHIBEI_STRATEGY_ID = "514c372c-0d6e-4b30-810d-774a0c7418ae"


def strip_code(code: str) -> str:
    raw = str(code or "").strip().upper()
    if "." in raw:
        raw = raw.split(".", 1)[0]
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise ValueError(f"invalid_code:{code}")
    return digits.zfill(6)[-6:]


def _pick_zhibei_item(
    payload: dict[str, Any], *, strategy_id: str | None = None
) -> dict[str, Any]:
    items = [x for x in (payload.get("items") or []) if isinstance(x, dict)]
    if not items:
        return payload
    wanted = str(strategy_id or "").strip() or DEFAULT_ZHIBEI_STRATEGY_ID
    for it in items:
        if str(it.get("id") or "") == wanted:
            return it
    # Prefer most recently updated when id not found
    def _ts(it: dict[str, Any]) -> str:
        return str(it.get("updated_at") or it.get("created_at") or "")

    return max(items, key=_ts)


def from_zhibei_config(
    raw: dict[str, Any], *, strategy_id: str | None = None
) -> dict[str, Any]:
    """Map website `config` object to local rotation config."""

    if not isinstance(raw, dict):
        raise ValueError("zhibei_config_not_object")

    # Allow wrapping: {items:[...]} / {config:{...}} / strategy item
    if "items" in raw and isinstance(raw["items"], list) and raw["items"]:
        item = _pick_zhibei_item(raw, strategy_id=strategy_id)
        raw = item.get("config") or item
    if "config" in raw and isinstance(raw["config"], dict) and "codes" in raw["config"]:
        raw = raw["config"]

    codes_raw = list(raw.get("codes") or [])
    if not codes_raw:
        raise ValueError("zhibei_codes_empty")
    pool = [strip_code(c) for c in codes_raw]
    names = {code: DEFAULT_NAMES.get(code, code) for code in pool}
    # Prefer website names if present in rankings later; keep defaults for known codes.
    names.update(
        {
            "510300": "沪深300ETF",
            "159915": "创业板ETF",
            "513100": "纳指ETF",
            "518880": "黄金ETF",
            "512890": "红利低波ETF",
        }
    )

    method_raw = str(raw.get("scoring_method") or "log_trend").lower()
    method = SCORE_METHOD_MAP.get(method_raw)
    if method is None:
        raise ValueError(f"unsupported_scoring_method:{method_raw}")

    window = int(raw.get("momentum_days") or 25)
    top_n = int(raw.get("hold_count") or 1)
    timing = raw.get("timing") or {}
    risk = raw.get("risk_control") or {}

    # Website classic template has no min-hold field; daily rebalance ⇒ allow switch next day.
    min_hold = 1
    if raw.get("min_hold_days") is not None:
        min_hold = max(1, int(raw["min_hold_days"]))

    ma_enabled = bool(timing.get("ma_filter_enabled"))
    abs_mom = bool(timing.get("absolute_momentum_enabled"))
    # absolute momentum ≈ require score > threshold (use score_min)
    score_min = None
    if abs_mom:
        score_min = float(timing.get("absolute_momentum_min_score") or 0.0)

    stop_enabled = bool(risk.get("portfolio_drawdown_enabled") or risk.get("crash_protection_enabled"))

    cfg: dict[str, Any] = {
        "etf_pool": pool,
        "etf_names": {c: names.get(c, c) for c in pool},
        "momentum": {
            "method": method,
            "window": window,
            "secondary_enabled": False,
            "secondary_method": "simple",
            "secondary_window": int(timing.get("absolute_momentum_days") or 20),
            "secondary_min": 0.0,
        },
        "selection": {
            "score_min": score_min,
            "score_max": None,
            "top_n": top_n,
            "equal_weight": False,
        },
        "holding": {
            "min_hold_days": min_hold,
            "day_count_type": "trading",
            "fallback_code": None,
        },
        "take_profit": {
            "enabled": False,
            "threshold": 0.18,
            "cooldown_days": 8,
        },
        "stop_loss": {
            "enabled": stop_enabled and bool(risk.get("portfolio_drawdown_enabled")),
            "pct_enabled": False,
            "pct_threshold": 0.08,
            "drawdown_enabled": bool(risk.get("portfolio_drawdown_enabled")),
            "drawdown_threshold": float(risk.get("portfolio_drawdown_threshold") or 0.12),
            "cooldown_days": int(risk.get("crash_cooldown_days") or 0),
        },
        "extreme_filter": {
            "skip_limit_up": False,
            "skip_limit_down": False,
        },
        "condition_filter": {
            "price_above_ma": ma_enabled,
            "ma_period": int(timing.get("ma_days") or 20),
            "ma_bull": False,
            "ma_fast": 20,
            "ma_slow": 60,
        },
        "market_timing": {
            "enabled": False,
            "benchmark_code": strip_code(str(raw.get("benchmark_code") or "510300")),
        },
        "costs": {
            "commission_rate": float(raw.get("commission_rate") or 0.0002),
            "slippage_rate": float(raw.get("slippage_rate") or 0.001),
        },
        "backtest": {
            "initial_nav": 1000.0,
            "start_date": raw.get("start") or "2025-01-01",
            "end_date": raw.get("end"),
        },
        "approx_label": "网站策略克隆",
        "source": "zhibei",
        "zhibei": {
            "scoring_method": method_raw,
            "rebalance_frequency": raw.get("rebalance_frequency") or "daily",
            "execution_time": raw.get("execution_time"),
            "template_id": raw.get("template_id"),
            "signal_interval": raw.get("signal_interval"),
            "defensive_enabled": bool(raw.get("defensive_enabled")),
            "note": "日K收盘近似；网站 execution_time 盘中价本地无法精确还原",
        },
    }
    return validate_config(cfg)


def builtin_zhibei_clone() -> dict[str, Any]:
    """Preset matching the user's copied website strategy."""

    official = {
        "codes": ["159915.XSHE", "513100.XSHG", "512890.XSHG", "518880.XSHG"],
        "benchmark_code": "510300.XSHG",
        "start": "2025-01-01",
        "end": "2026-08-07",
        "momentum_days": 25,
        "hold_count": 1,
        "scoring_method": "log_trend",
        "rebalance_frequency": "daily",
        "execution_time": "10:00:00",
        "slippage_rate": 0.001,
        "commission_rate": 0.0002,
        "defensive_enabled": False,
        "timing": {
            "absolute_momentum_enabled": False,
            "ma_filter_enabled": False,
            "breadth_filter_enabled": False,
        },
        "risk_control": {
            "crash_protection_enabled": False,
            "portfolio_drawdown_enabled": False,
        },
        "template_id": "classic",
        "signal_interval": "daily",
    }
    from .config import strategy_record

    return strategy_record(
        strategy_id=ZHIBEI_CLONE_ID,
        name="网站策略克隆（log_trend/四池）",
        config=from_zhibei_config(official),
        readonly=True,
        approx=False,
    )
