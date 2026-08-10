"""Fetch and normalize 小薪 ETF 轮动 public snapshot."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
PUBLIC_URL = os.environ.get(
    "ETF68_XIAOXIN_PUBLIC_URL",
    "https://etf.zhibeiquant.com/public/xiaoxin-strategy",
)
REPO_ROOT = Path(__file__).resolve().parents[3]


def default_public_path() -> Path:
    env = os.environ.get("ETF68_OUT_DIR")
    root = Path(env) if env else (REPO_ROOT / "data" / "out")
    return root / "xiaoxin-public.json"


def _now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def normalize_public(raw: dict[str, Any]) -> dict[str, Any]:
    strategy = raw.get("strategy") or {}
    momentum = raw.get("momentum") or {}
    history = strategy.get("history") or {}
    rankings = []
    for row in momentum.get("rankings") or []:
        rankings.append(
            {
                "rank": row.get("rank"),
                "code": str(row.get("code") or "").zfill(6)[-6:],
                "name": row.get("name"),
                "score": row.get("score"),
                "annualized_return": row.get("annualized_return"),
                "r_squared": row.get("r_squared"),
            }
        )
    pool = momentum.get("etf_pool") or {}
    returns = strategy.get("returns") or {}
    return {
        "ok": True,
        "source": raw.get("source") or "zhibeiquant.com",
        "live": bool(raw.get("live")),
        "fetched_at": _now_iso(),
        "strategy_name": strategy.get("strategy_name") or "ETF轮动实盘",
        "start_date": strategy.get("start_date"),
        "day_index": strategy.get("day_index"),
        "total_return_pct": strategy.get("total_return"),
        "max_drawdown_pct": strategy.get("max_drawdown"),
        "ytd_return_pct": returns.get("ytd"),
        "returns": returns,
        "as_of": momentum.get("latest_trade_date") or momentum.get("date"),
        "update_time": momentum.get("update_time"),
        "etf_pool": pool,
        "rankings": rankings,
        "hold_code": (rankings[0]["code"] if rankings else None),
        "hold_name": (rankings[0]["name"] if rankings else None),
        "equity": {
            "dates": history.get("full_dates") or history.get("labels") or [],
            "nav": history.get("strategy") or [],
        },
        "status_message": momentum.get("status_message"),
        "approx_note": "公开快照仅供对照；本地回测为近似实现",
    }


def fetch_public_raw(url: str = PUBLIC_URL, *, timeout: float = 20.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "etf-68-app/rotation",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("invalid_public_payload")
    return payload


def load_cached_public(path: Path | None = None) -> dict[str, Any] | None:
    p = path or default_public_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def fetch_and_cache_public(
    *,
    path: Path | None = None,
    url: str = PUBLIC_URL,
) -> dict[str, Any]:
    p = path or default_public_path()
    try:
        raw = fetch_public_raw(url)
        norm = normalize_public(raw)
        norm["cache"] = False
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(norm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return norm
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        cached = load_cached_public(p)
        if cached:
            cached = dict(cached)
            cached["ok"] = True
            cached["cache"] = True
            cached["fetch_error"] = str(exc)
            return cached
        return {
            "ok": False,
            "cache": False,
            "error": str(exc),
            "fetched_at": _now_iso(),
            "rankings": [],
            "equity": {"dates": [], "nav": []},
        }
