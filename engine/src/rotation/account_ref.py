"""Account-strategy reference snapshot for mode B (not homepage public 4-pool)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import DEFAULT_NAMES

REPO_ROOT = Path(__file__).resolve().parents[3]
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _display_name(code: str, raw_name: Any = None) -> str:
    """Prefer website name; fall back to known ETF labels (not bare code)."""
    code = _strip_code(code)
    name = str(raw_name or "").strip()
    if name and name != code and not name.startswith(code + "."):
        return name
    return DEFAULT_NAMES.get(code, code)


def default_account_ref_path() -> Path:
    env = os.environ.get("ETF68_ROTATION_DIR")
    root = Path(env) if env else (REPO_ROOT / "data" / "rotation")
    return root / "zhibei-reference.json"


def _now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def _strip_code(code: Any) -> str:
    raw = str(code or "").strip().upper()
    if "." in raw:
        raw = raw.split(".", 1)[0]
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits.zfill(6)[-6:] if digits else ""


def _pct(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _first(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _pick_strategy_item(payload: dict[str, Any], strategy_id: str | None = None) -> dict[str, Any]:
    """Accept list/detail/result/persisted_run envelopes from 智贝 APIs."""
    # persisted backtest run: { kind, result: {equity_curve,...}, run: {...} }
    if payload.get("kind") == "persisted_run" or (
        isinstance(payload.get("result"), dict)
        and isinstance(payload["result"].get("equity_curve"), list)
    ):
        run = payload.get("run") if isinstance(payload.get("run"), dict) else {}
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        cfg = (
            result.get("config")
            or run.get("config_snapshot")
            or (run.get("result") or {}).get("config")
            or {}
        )
        return {
            "id": strategy_id or run.get("strategy_id") or payload.get("id"),
            "name": run.get("strategy_name") or "我的策略",
            "config": cfg if isinstance(cfg, dict) else {},
            "result": result,
            "kind": "persisted_run",
        }

    if "items" in payload and isinstance(payload["items"], list) and payload["items"]:
        items = [x for x in payload["items"] if isinstance(x, dict)]
        if strategy_id:
            wanted = str(strategy_id)
            for it in items:
                if str(it.get("id") or "") == wanted:
                    return it
            for it in items:
                if str(it.get("strategy_id") or "") == wanted:
                    return it

        def _rank(it: dict[str, Any]) -> tuple:
            result = it.get("result") if isinstance(it.get("result"), dict) else {}
            metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
            curve = result.get("equity_curve") if isinstance(result.get("equity_curve"), list) else []
            return (
                str(it.get("updated_at") or it.get("created_at") or ""),
                1 if curve else 0,
                1 if metrics else 0,
                1 if it.get("simulation") else 0,
            )

        return max(items, key=_rank)
    if "config" in payload or "result" in payload or "id" in payload:
        return payload
    if "history" in payload or "momentum" in payload or "strategy" in payload:
        return {"result": payload, "name": payload.get("strategy_name") or "我的策略"}
    raise ValueError("unsupported_account_payload")


def _rankings_from_rows(rows: Any, *, ann_as_fraction: bool = False) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        code = _strip_code(row.get("code") or row.get("symbol"))
        ann = row.get("annualized_return")
        if ann_as_fraction and isinstance(ann, (int, float)):
            ann = float(ann) * 100.0
        out.append(
            {
                "rank": row.get("rank") if row.get("rank") is not None else i + 1,
                "code": code,
                "name": _display_name(code, row.get("name")),
                "score": row.get("score"),
                "annualized_return": ann,
                "r_squared": row.get("r_squared"),
            }
        )
    return out


def _equity_from_curve(curve: Any) -> tuple[list[str], list[float]]:
    dates: list[str] = []
    nav: list[float] = []
    for pt in curve or []:
        if not isinstance(pt, dict):
            continue
        d = str(pt.get("date") or "").strip()
        v = pt.get("strategy_value")
        if v is None:
            v = pt.get("nav") or pt.get("value")
        if not d or v is None:
            continue
        try:
            dates.append(d[:10])
            nav.append(float(v))
        except (TypeError, ValueError):
            continue
    return dates, nav


def _hold_event_from_trade(row: dict[str, Any]) -> tuple[str, str | None, str | None] | None:
    """Return (date, code|None, name|None). None code means flat/cash."""
    d = str(row.get("date") or "").strip()[:10]
    if not d:
        return None
    # Website persisted_run trades
    targets = row.get("target_holdings")
    if isinstance(targets, list):
        if not targets:
            return d, None, None
        code = _strip_code(targets[0])
        details = row.get("target_holding_details") or row.get("buy_details") or []
        name = None
        if isinstance(details, list) and details:
            first = details[0] if isinstance(details[0], dict) else {}
            name = first.get("name")
        return d, code or None, _display_name(code, name) if code else None
    # Local rotation trades
    action = str(row.get("action") or "")
    if action in {"空仓", "止损", "止盈"}:
        return d, None, None
    code = _strip_code(row.get("code"))
    if not code:
        return None
    return d, code, _display_name(code, row.get("name"))


def _holds_series_from_trades(
    dates: list[str], trades: Any
) -> tuple[list[str | None], list[str | None]]:
    events: list[tuple[str, str | None, str | None]] = []
    for row in trades or []:
        if not isinstance(row, dict):
            continue
        ev = _hold_event_from_trade(row)
        if ev is None:
            continue
        events.append(ev)
    events.sort(key=lambda x: x[0])
    codes: list[str | None] = []
    names: list[str | None] = []
    cur_code: str | None = None
    cur_name: str | None = None
    j = 0
    for d in dates:
        while j < len(events) and events[j][0] <= d:
            cur_code, cur_name = events[j][1], events[j][2]
            j += 1
        codes.append(cur_code)
        names.append(cur_name)
    return codes, names


def _pct_from_fraction(v: Any) -> float | None:
    """Website metrics use fractions (0.47 / -0.21); return positive magnitude % for MDD-like values."""
    if not isinstance(v, (int, float)):
        return None
    x = float(v)
    if abs(x) <= 2.0:
        return abs(x) * 100.0 if x < 0 or abs(x) < 1.5 else x * 100.0
    return abs(x)


def normalize_account_payload(
    payload: dict[str, Any],
    *,
    strategy_id: str | None = None,
) -> dict[str, Any]:
    item = _pick_strategy_item(payload, strategy_id=strategy_id)
    sim = item.get("simulation") if isinstance(item.get("simulation"), dict) else {}
    cfg = item.get("config") if isinstance(item.get("config"), dict) else {}
    if not cfg and isinstance(item.get("config_snapshot"), dict):
        cfg = item["config_snapshot"]
    if not cfg and isinstance(sim.get("config_snapshot"), dict):
        cfg = sim["config_snapshot"]

    result = sim.get("result") if isinstance(sim, dict) else None
    if result is None:
        result = item.get("result")
    if result is None and isinstance(item.get("strategy"), dict):
        result = {
            "strategy": item.get("strategy"),
            "momentum": item.get("momentum"),
        }

    sim_rankings = _rankings_from_rows(
        sim.get("latest_close_rankings") or item.get("rankings") or []
    )

    if not isinstance(result, dict):
        hold_code = sim_rankings[0]["code"] if sim_rankings else None
        hold_name = sim_rankings[0]["name"] if sim_rankings else None
        pool = [_strip_code(c) for c in (cfg.get("codes") or []) if _strip_code(c)]
        return {
            "ok": True,
            "mode": "account",
            "label": "账号策略对照",
            "strategy_name": item.get("name") or item.get("strategy_name") or "我的策略",
            "strategy_id": item.get("id") or strategy_id,
            "pool": pool or None,
            "as_of": sim.get("latest_close_date") or item.get("as_of"),
            "hold_code": hold_code,
            "hold_name": hold_name,
            "signal": "模拟盘最新收盘第1名" if sim_rankings else None,
            "total_return_pct": None,
            "max_drawdown_pct": None,
            "ytd_return_pct": None,
            "day_index": None,
            "result": None,
            "simulation_status": sim.get("status"),
            "simulation_start_date": sim.get("simulation_start_date"),
            "last_refreshed_at": sim.get("last_refreshed_at"),
            "equity_source": "none",
            "rankings": sim_rankings,
            "equity": {"dates": [], "nav": [], "codes": [], "names": []},
            "config_summary": {
                "scoring_method": cfg.get("scoring_method"),
                "momentum_days": cfg.get("momentum_days"),
                "hold_count": cfg.get("hold_count"),
                "rebalance_frequency": cfg.get("rebalance_frequency"),
                "execution_time": cfg.get("execution_time"),
                "commission_rate": cfg.get("commission_rate"),
                "slippage_rate": cfg.get("slippage_rate"),
                "start": cfg.get("start"),
                "end": cfg.get("end"),
            }
            if cfg
            else None,
            "note": (
                (
                    "已开通向前模拟盘（simulation.active），但 result/metrics 仍为空："
                    "这是纸交易从开通日起累计，不会立刻给出 2025-01-01 起的历史净值。"
                    "当前可对照 latest_close_rankings；要并排净值请在网站对该 config 跑「回测」"
                    "（Network 里 POST /backtests/run 或 GET persisted_run 的响应）再导入。"
                )
                if str(sim.get("status") or "") == "active"
                else (
                    "已导入账号策略配置，但尚无回测净值 / 模拟盘结果。"
                    "左侧暂用同参本地复现；要并排网站净值请在智贝对该策略跑「回测」后把"
                    " persisted_run / equity_curve 响应再导入。"
                )
            ),
            "imported_at": _now_iso(),
        }

    # --- equity: prefer equity_curve (account backtest) then public history ---
    dates: list[str] = []
    nav: list[float] = []
    if isinstance(result.get("equity_curve"), list):
        dates, nav = _equity_from_curve(result["equity_curve"])

    strategy = result.get("strategy") if isinstance(result.get("strategy"), dict) else result
    momentum = result.get("momentum") if isinstance(result.get("momentum"), dict) else {}
    if not momentum and isinstance(result.get("rankings"), list):
        momentum = {"rankings": result.get("rankings")}

    history = strategy.get("history") if isinstance(strategy, dict) else {}
    if not isinstance(history, dict):
        history = result.get("history") if isinstance(result.get("history"), dict) else {}

    if not dates:
        dates = list(history.get("full_dates") or history.get("labels") or [])
        raw_nav = history.get("strategy") or history.get("nav") or []
        if isinstance(raw_nav, dict):
            raw_nav = raw_nav.get("values") or raw_nav.get("data") or []
        nav = [float(x) for x in raw_nav if isinstance(x, (int, float))]

    # rankings: current_suggestion.scores (backtest) → momentum → sim
    suggestion = (
        result.get("current_suggestion") if isinstance(result.get("current_suggestion"), dict) else {}
    )
    if isinstance(suggestion.get("scores"), list) and suggestion["scores"]:
        rankings = _rankings_from_rows(suggestion["scores"], ann_as_fraction=True)
        hold_list = suggestion.get("target_holdings") or []
        hold_code = _strip_code(hold_list[0]) if hold_list else (rankings[0]["code"] if rankings else None)
        hold_name = next((r.get("name") for r in rankings if r.get("code") == hold_code), None)
        if not hold_name and rankings:
            hold_name = rankings[0].get("name")
        hold_name = _display_name(hold_code or "", hold_name) if hold_code else hold_name
    else:
        rankings = _rankings_from_rows(momentum.get("rankings") or sim_rankings)
        hold = (
            (momentum.get("holdings") or [None])[0]
            if isinstance(momentum.get("holdings"), list)
            else None
        )
        hold_code = _strip_code(hold.get("code") if isinstance(hold, dict) else hold)
        hold_name = hold.get("name") if isinstance(hold, dict) else None
        if not hold_code and rankings:
            hold_code = rankings[0].get("code")
            hold_name = rankings[0].get("name")
        if hold_code:
            hold_name = _display_name(hold_code, hold_name)

    if not cfg and isinstance(result.get("config"), dict):
        cfg = result["config"]

    pool = [_strip_code(c) for c in (cfg.get("codes") or strategy.get("codes") or []) if _strip_code(c)]

    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    total = strategy.get("total_return")
    mdd = strategy.get("max_drawdown")
    if total is None and nav:
        try:
            first = float(nav[0])
            last = float(nav[-1])
            if first:
                # curve usually starts near 1.0 after first trade; use last/1.0-1 if first≈1
                base = 1.0 if 0.95 <= first <= 1.05 else first
                total = (last / base - 1.0) * 100.0
        except (TypeError, ValueError, ZeroDivisionError):
            total = None
    if mdd is None and metrics.get("max_drawdown") is not None:
        mdd = _pct_from_fraction(metrics.get("max_drawdown"))
    elif isinstance(mdd, (int, float)) and abs(float(mdd)) <= 2.0:
        mdd = abs(float(mdd)) * 100.0

    equity_ok = bool(dates) and bool(nav) and len(dates) == len(nav)
    equity_source = "account_import" if equity_ok else "none"
    hold_codes: list[str | None] = []
    hold_names: list[str | None] = []
    if equity_ok:
        hold_codes, hold_names = _holds_series_from_trades(dates, result.get("trades"))
        if hold_code and hold_codes and not any(hold_codes):
            # no trade timeline — paint final hold across curve as weak fallback
            hold_codes = [hold_code] * len(dates)
            hold_names = [_display_name(hold_code, hold_name)] * len(dates)
    curve_raw = result.get("equity_curve")
    has_curve_field = isinstance(curve_raw, list)
    has_nonempty_curve = has_curve_field and len(curve_raw) > 0
    is_backtest = (
        has_nonempty_curve
        or item.get("kind") == "persisted_run"
        or bool(metrics)
        or bool(suggestion)
    )
    note = None
    if equity_source == "none" and has_curve_field and metrics:
        note = (
            "已导入回测摘要（年化/回撤/持仓/排名），但本接口把 equity_curve 置空。"
            "左侧净值暂用同参本地复现；要并排网站真曲线，请打开该次 run 详情"
            "（Network 里 kind=persisted_run 且 equity_curve 非空的响应）再导入。"
        )
    elif equity_source == "none" and rankings:
        note = (
            "已导入账号策略快照，但历史净值曲线为空（常见于刚开通的向前模拟盘）。"
            "左侧暂用本地同配置重建曲线做对照；持仓/排名以网站为准。"
        )
    elif is_backtest and equity_source == "account_import":
        note = (
            f"已导入网站回测净值（{len(dates)} 个交易日）。"
            "与本地差异主要来自成交价（网站 10:00 执行 vs 本地收盘）与计息口径。"
        )
    elif equity_source == "account_import":
        note = "对照来自账号工作台模拟盘导入（含净值）。勿与首页四池公开实盘横比。"

    sid = (
        item.get("strategy_id")
        or item.get("id")
        or strategy.get("id")
        or strategy_id
    )
    sname = (
        item.get("strategy_name")
        or item.get("name")
        or strategy.get("name")
        or "我的策略"
    )

    return {
        "ok": True,
        "mode": "account",
        "label": "账号策略对照",
        "strategy_name": sname,
        "strategy_id": sid,
        "pool": pool or None,
        "as_of": (
            suggestion.get("date")
            or strategy.get("as_of")
            or strategy.get("end_date")
            or (dates[-1] if dates else None)
            or sim.get("latest_close_date")
            or cfg.get("end")
        ),
        "hold_code": hold_code,
        "hold_name": hold_name,
        "signal": "网站回测持仓" if is_backtest else (strategy.get("signal") or "模拟盘最新收盘第1名"),
        "total_return_pct": _pct(total),
        "max_drawdown_pct": _pct(mdd),
        "annualized_return_pct": _pct_from_fraction(metrics.get("annualized_return"))
        if metrics.get("annualized_return") is not None
        else strategy.get("annualized_return"),
        "sharpe_ratio": metrics.get("sharpe_ratio"),
        "trade_count": metrics.get("trade_count"),
        "ytd_return_pct": _pct(
            _first(
                strategy.get("ytd_return"),
                (strategy.get("returns") or {}).get("ytd")
                if isinstance(strategy.get("returns"), dict)
                else None,
            )
        ),
        "day_index": strategy.get("day_index") or (len(dates) if equity_ok else None),
        "result": strategy.get("result") or ("回测完成" if is_backtest else None),
        "simulation_status": sim.get("status") or ("completed" if is_backtest else None),
        "simulation_start_date": sim.get("simulation_start_date") or metrics.get("effective_start_date"),
        "last_refreshed_at": sim.get("last_refreshed_at"),
        "equity_source": equity_source,
        "rankings": rankings,
        "equity": (
            {
                "dates": list(dates),
                "nav": list(nav),
                "codes": list(hold_codes),
                "names": list(hold_names),
            }
            if equity_ok
            else {"dates": [], "nav": [], "codes": [], "names": []}
        ),
        "config_summary": {
            "scoring_method": cfg.get("scoring_method"),
            "momentum_days": cfg.get("momentum_days"),
            "hold_count": cfg.get("hold_count"),
            "rebalance_frequency": cfg.get("rebalance_frequency"),
            "execution_time": cfg.get("execution_time"),
            "commission_rate": cfg.get("commission_rate"),
            "slippage_rate": cfg.get("slippage_rate"),
            "start": cfg.get("start"),
            "end": cfg.get("end"),
        }
        if cfg
        else None,
        "note": note,
        "imported_at": _now_iso(),
    }


def save_account_reference(data: dict[str, Any], path: Path | None = None) -> Path:
    p = path or default_account_ref_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def import_account_reference(
    payload: dict[str, Any],
    *,
    strategy_id: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    snap = normalize_account_payload(payload, strategy_id=strategy_id)
    save_account_reference(snap, path=path)
    return snap


def load_account_reference(path: Path | None = None) -> dict[str, Any]:
    p = path or default_account_ref_path()
    if not p.exists():
        return {
            "ok": False,
            "mode": "account",
            "label": "账号策略对照",
            "error": "account_reference_missing",
            "rankings": [],
            "equity": {"dates": [], "nav": []},
            "note": "缺少账号策略对照快照",
        }
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "mode": "account",
            "label": "账号策略对照",
            "error": str(exc),
            "rankings": [],
            "equity": {"dates": [], "nav": []},
        }
    data = dict(data)
    data.setdefault("ok", True)
    data.setdefault("mode", "account")
    data.setdefault("label", "账号策略对照")
    return data
