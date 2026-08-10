"""Orchestrate strategy store, public snapshot, and local backtest."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.market_data import PublicMarketDataProvider

from .backtester import run_backtest
from .account_ref import load_account_reference
from .config import XIAOXIN_PRESET_ID, ZHIBEI_CLONE_ID, validate_config
from .public_xiaoxin import default_public_path, fetch_and_cache_public
from .store import (
    default_strategies_path,
    delete_strategy as store_delete,
    duplicate_strategy as store_duplicate,
    get_strategy,
    list_strategies as store_list,
    save_strategy as store_save,
    set_active,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
REPO_ROOT = Path(__file__).resolve().parents[3]


def default_last_path() -> Path:
    env = os.environ.get("ETF68_OUT_DIR")
    root = Path(env) if env else (REPO_ROOT / "data" / "out")
    return root / "rotation-last.json"


def list_strategies(path: Path | None = None) -> dict[str, Any]:
    return store_list(path)


def save_strategy(
    *,
    strategy_id: str | None,
    name: str,
    config: dict[str, Any],
    make_active: bool = True,
    path: Path | None = None,
) -> dict[str, Any]:
    return store_save(
        strategy_id=strategy_id,
        name=name,
        config=config,
        make_active=make_active,
        path=path,
    )


def delete_strategy(strategy_id: str, path: Path | None = None) -> dict[str, Any]:
    return store_delete(strategy_id, path)


def duplicate_strategy(
    strategy_id: str, *, new_name: str | None = None, path: Path | None = None
) -> dict[str, Any]:
    return store_duplicate(strategy_id, new_name=new_name, path=path)


def fetch_public(*, path: Path | None = None) -> dict[str, Any]:
    return fetch_and_cache_public(path=path)


def _fetch_bars(codes: list[str], *, workers: int = 4) -> tuple[dict[str, Any], dict[str, str]]:
    provider = PublicMarketDataProvider(calendar_provider=object(), catalyst_provider=object())
    bars_by_code: dict[str, Any] = {}
    errors: dict[str, str] = {}

    def one(code: str):
        try:
            return code, list(provider.get_daily_bars(code)), None
        except Exception as exc:  # noqa: BLE001
            return code, None, str(getattr(exc, "reason", None) or exc)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = [pool.submit(one, c) for c in codes]
        for fut in as_completed(futs):
            code, bars, err = fut.result()
            if err or not bars:
                errors[code] = err or "empty"
            else:
                bars_by_code[code] = bars
    return bars_by_code, errors


def run_rotation(
    *,
    strategy_id: str | None = None,
    config: dict[str, Any] | None = None,
    include_public: bool = True,
    strategies_path: Path | None = None,
    public_path: Path | None = None,
    output_path: Path | None = None,
    workers: int = 4,
    bars_by_code: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = store_list(strategies_path)
    sid = strategy_id or doc.get("active_id") or ZHIBEI_CLONE_ID or XIAOXIN_PRESET_ID
    item = get_strategy(sid, strategies_path)
    approx = True
    name = sid
    if config is None:
        if not item:
            raise KeyError(f"strategy_not_found:{sid}")
        cfg = validate_config(item.get("config") or {})
        approx = bool(item.get("approx"))
        name = str(item.get("name") or sid)
    else:
        cfg = validate_config(config)
        approx = bool(item.get("approx")) if item else (cfg.get("source") != "zhibei")
        name = str(item.get("name") if item else name)

    codes = list(cfg["etf_pool"])
    fb = cfg["holding"].get("fallback_code")
    if fb:
        codes.append(fb)
    if cfg["market_timing"]["enabled"]:
        codes.append(cfg["market_timing"]["benchmark_code"])
    # unique preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            ordered.append(c)

    fetch_errors: dict[str, str] = {}
    if bars_by_code is None:
        bars_by_code, fetch_errors = _fetch_bars(ordered, workers=workers)

    result = run_backtest(config=cfg, bars_by_code=bars_by_code, names=cfg["etf_names"])
    # Mode B (账号三池克隆): compare against account snapshot, not homepage 4-pool public.
    is_account_mode = (
        sid == ZHIBEI_CLONE_ID
        or cfg.get("source") == "zhibei"
        or str(cfg.get("approx_label") or "").startswith("网站策略克隆")
    )
    reference = load_account_reference() if is_account_mode else None
    public = None
    if include_public and not is_account_mode:
        public = fetch_and_cache_public(path=public_path or default_public_path())

    payload = {
        "ok": True,
        "strategy_id": sid,
        "strategy_name": name,
        "approx": approx,
        "approx_label": cfg.get("approx_label") or ("网站策略克隆" if is_account_mode else "本地近似"),
        "compare_mode": "account" if is_account_mode else "public",
        "generated_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "config": cfg,
        "public": public,
        "reference": reference,
        "fetch_errors": fetch_errors,
        "local": {
            "as_of": None if result.as_of is None else result.as_of.isoformat(),
            "hold_code": result.hold_code,
            "hold_name": result.hold_name,
            "signal": result.signal,
            "total_return_pct": result.total_return_pct,
            "max_drawdown_pct": result.max_drawdown_pct,
            "ytd_return_pct": result.ytd_return_pct,
            "day_index": result.day_index,
            "rankings": result.rankings,
            "equity": {
                "dates": result.equity_dates,
                "nav": result.equity_nav,
                "codes": result.equity_hold_codes,
                "names": result.equity_hold_names,
            },
            "trades": result.trades,
            "warnings": result.warnings,
        },
    }
    out = output_path or default_last_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def load_last(path: Path | None = None) -> dict[str, Any] | None:
    p = path or default_last_path()
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# re-export path helpers for CLI
strategies_path = default_strategies_path
last_path = default_last_path
public_path = default_public_path
activate_strategy = set_active
