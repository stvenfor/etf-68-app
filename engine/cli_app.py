#!/usr/bin/env python3.12
"""One-shot daily ETF-68 pipeline for the desktop app.

Writes artifacts under engine/reports/ and a UI bundle at ../data/out/latest.json.
Prints a summary JSON object to stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ENGINE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = ENGINE_ROOT.parent
OUT_DIR = Path(os.environ.get("ETF68_OUT_DIR") or (REPO_ROOT / "data" / "out"))
REPORTS = Path(os.environ.get("ETF68_REPORTS_DIR") or (ENGINE_ROOT / "reports"))
SHANGHAI = ZoneInfo("Asia/Shanghai")
PY = sys.executable


def _clear_proxy_env() -> dict[str, str]:
    env = os.environ.copy()
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"
    for k in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
    ):
        env.pop(k, None)
    env["PYTHONPATH"] = str(ENGINE_ROOT)
    return env


def _run(args: list[str], *, step: str) -> None:
    print(json.dumps({"event": "step_start", "step": step}, ensure_ascii=False), flush=True)
    proc = subprocess.run(
        args,
        cwd=str(ENGINE_ROOT),
        env=_clear_proxy_env(),
        capture_output=True,
        text=True,
    )
    if proc.stdout.strip():
        for line in proc.stdout.strip().splitlines()[-20:]:
            print(json.dumps({"event": "log", "step": step, "line": line}, ensure_ascii=False), flush=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "unknown_error").strip()
        raise RuntimeError(f"{step}_failed:{err[-2000:]}")
    print(json.dumps({"event": "step_done", "step": step}, ensure_ascii=False), flush=True)


def _find_seed(day: str) -> Path:
    preferred = REPORTS / f"representative-technical-review-{day}.json"
    if preferred.exists():
        return preferred
    dated = sorted(REPORTS.glob("representative-technical-review-*.json"))
    if dated:
        return dated[-1]
    raise FileNotFoundError(
        "no_seed_review: put a representative-technical-review-YYYY-MM-DD.json under engine/reports/"
    )


def _prev_day(day: str) -> str:
    d = date.fromisoformat(day)
    return (d - timedelta(days=1)).isoformat()


def assemble_ui_bundle(day: str) -> dict[str, Any]:
    review_path = REPORTS / f"representative-technical-review-{day}.json"
    edge_path = REPORTS / f"etf68-edge-conditions-{day}.json"
    weekly_path = REPORTS / f"etf68-weekly-macd-ma-backtest-{day}.json"
    kdj_path = REPORTS / f"etf68-daily-kdj-macd-backtest-{day}.json"
    impact_path = REPORTS / f"etf68-impact-events-{day}.json"
    matrix_path = REPORTS / f"etf68-event-etf-matrix-{day}.json"

    review = json.loads(review_path.read_text(encoding="utf-8"))
    edge_by = {}
    if edge_path.exists():
        edge = json.loads(edge_path.read_text(encoding="utf-8"))
        edge_by = {str(r["code"]): r for r in edge.get("rows", [])}
    weekly_by = {}
    if weekly_path.exists():
        weekly = json.loads(weekly_path.read_text(encoding="utf-8"))
        weekly_by = {str(r["code"]): r for r in weekly.get("rows", [])}
    kdj_by = {}
    if kdj_path.exists():
        kdj = json.loads(kdj_path.read_text(encoding="utf-8"))
        kdj_by = {str(r["code"]): r for r in kdj.get("rows", [])}

    sector_cn = {
        "advanced_equipment": "高端装备",
        "agriculture": "农业",
        "agriculture_commodity": "农产品",
        "artificial_intelligence": "人工智能",
        "bank": "银行",
        "battery": "电池",
        "biotechnology": "生物科技",
        "broad_market": "宽基",
        "broad_tech": "科技宽基",
        "building_materials": "建材",
        "cashflow_factor": "现金流因子",
        "coal": "煤炭",
        "commodity_equity": "商品股",
        "communication": "通信",
        "consumer": "消费",
        "consumer_electronics": "消费电子",
        "convertible_bond": "可转债",
        "credit_bond": "信用债",
        "defense": "军工",
        "dividend_factor": "红利",
        "education": "教育",
        "electric_utility": "电力公用",
        "electronics": "电子",
        "energy": "能源",
        "energy_chemical": "能源化工",
        "food_beverage": "食品饮料",
        "gaming": "游戏",
        "gold": "黄金",
        "government_bond": "国债",
        "growth_board": "创业板",
        "healthcare": "医药",
        "infrastructure": "基建",
        "innovative_drug": "创新药",
        "intelligent_manufacturing": "智能制造",
        "internet": "互联网",
        "large_cap": "大盘",
        "liquor": "白酒",
        "livestock": "畜牧",
        "machinery": "机械",
        "media": "传媒",
        "mid_cap": "中盘",
        "mid_cap_factor": "中盘因子",
        "new_energy": "新能源",
        "new_energy_vehicle": "新能源汽车",
        "new_materials": "新材料",
        "nonferrous_metals": "有色金属",
        "oil_gas": "油气",
        "rare_earth": "稀土",
        "real_estate": "地产",
        "robotics": "机器人",
        "satellite": "卫星",
        "securities": "证券",
        "securities_insurance": "证券保险",
        "semiconductor": "半导体",
        "small_cap": "小盘",
        "smart_driving": "智能驾驶",
        "software": "软件",
        "solar": "光伏",
        "star_50": "科创50",
        "state_owned_enterprise": "国企",
        "steel": "钢铁",
        "technology": "科技",
    }

    def _state(obj: Any) -> str:
        if isinstance(obj, dict):
            return str(obj.get("state") or "—")
        return str(obj or "—")

    def _weekly_ma_label(obj: Any) -> str:
        if not isinstance(obj, dict):
            return str(obj or "—")
        fast = obj.get("fast")
        slow = obj.get("slow")
        mark = "✓" if obj.get("aligned") else "✗"
        if fast is None or slow is None:
            return mark
        return f"W{fast}/{slow}{mark}"

    def _flow_yi(flows: Any, key: str) -> float | None:
        if not isinstance(flows, dict):
            return None
        node = flows.get(key) or flows.get(int(key))  # type: ignore[arg-type]
        if not isinstance(node, dict):
            return None
        v = node.get("value_cny")
        if v is None:
            return None
        return round(float(v) / 1e8, 4)

    def _params(r: dict[str, Any], wk: dict[str, Any]) -> str:
        bp = wk.get("bestParams") or r.get("bestWeeklyParams") or {}
        if isinstance(bp, dict) and bp:
            return f"W{bp.get('fast')}/{bp.get('slow')}·{bp.get('macdMode') or bp.get('mode') or ''}"
        return str(r.get("weeklyParams") or wk.get("weeklyParams") or "—")

    rows_out: list[dict[str, Any]] = []
    for i, r in enumerate(review.get("rows", [])):
        code = str(r["code"])
        eg = edge_by.get(code) or {}
        wk = weekly_by.get(code) or {}
        kd = kdj_by.get(code) or {}
        sent = r.get("sentiment") if isinstance(r.get("sentiment"), dict) else {}
        vp = r.get("volumePrice") if isinstance(r.get("volumePrice"), dict) else {}
        sector_key = str(r.get("sector") or "")
        rows_out.append(
            {
                "action": r.get("action"),
                "mom20Ma28": r.get("mom20Ma28") or "—",
                "wmDailySignal": r.get("wmDailySignal") or "—",
                "monthlyTrend": r.get("monthlyTrend") or "—",
                "wmDailyDetail": r.get("wmDailyDetail") or "—",
                "maMacdVol": r.get("maMacdVol") or "—",
                "maMacdVolDetail": r.get("maMacdVolDetail") or "—",
                "ret20Rank": r.get("ret20_rank"),
                "aboveMa28": bool(r.get("above_ma28")),
                "code": code,
                "name": r.get("name"),
                "trend": r.get("trend") or r.get("weeklyTrend"),
                "ret30Hold": r.get("ret30_hold_pct"),
                "ret1": r.get("ret1_pct"),
                "ret5": r.get("ret5_pct"),
                "ret10": r.get("ret10_pct"),
                "ret20": r.get("ret20_pct"),
                "dd10": eg.get("dd10") or 0,
                "dd20": eg.get("dd20") or 0,
                "dd30": eg.get("dd30") or 0,
                "dd60": eg.get("dd60") or 0,
                "dd120": eg.get("dd120") or 0,
                "bestEdge": eg.get("best_edge") or eg.get("bestEdge") or "—",
                "rsi": r.get("rsi14"),
                "kdj": _state(r.get("kdj")),
                "macd": _state(r.get("macd")),
                "weeklyMacd": _state(wk.get("weeklyMacd") or r.get("weeklyMacd")),
                "weeklyMa": _weekly_ma_label(wk.get("weeklyMa") or r.get("weeklyMa")),
                "backtestPass": bool(
                    wk["backtestPass"] if "backtestPass" in wk else r.get("backtestPass")
                ),
                "weeklyParams": _params(r, wk),
                "volumePrice": vp.get("label") or "中性",
                "sentiment": round(float(sent.get("score") or 0), 1),
                "sentimentLabel": sent.get("label") or "—",
                "flow1": _flow_yi(r.get("flows"), "1"),
                "flow5": _flow_yi(r.get("flows"), "5"),
                "flow10": _flow_yi(r.get("flows"), "10"),
                "sector": sector_cn.get(sector_key, sector_key),
                "reportIndex": i,
                "kdjMacdRef": kd.get("kdjMacdRef") or "—",
            }
        )

    by_action: dict[str, int] = {}
    by_trend: dict[str, int] = {}
    for row in rows_out:
        a = str(row.get("action") or "")
        t = str(row.get("trend") or "")
        by_action[a] = by_action.get(a, 0) + 1
        by_trend[t] = by_trend.get(t, 0) + 1

    # Prefer ret30Hold from optional canvas-data seed when review lacks it.
    canvas_path = REPORTS / f"etf68-canvas-data-{day}.json"
    if canvas_path.exists():
        canvas = json.loads(canvas_path.read_text(encoding="utf-8"))
        ret_by = {str(r["code"]): r.get("ret30Hold") for r in canvas.get("rows", [])}
        for row in rows_out:
            if row.get("ret30Hold") is None and row["code"] in ret_by:
                row["ret30Hold"] = ret_by[row["code"]]

    static_dir = Path(os.environ.get("ETF68_STATIC_DIR") or (REPO_ROOT / "data" / "static"))
    delivery = _read_json(static_dir / "equity-index-futures-delivery-calendar-2026.json")
    citic = _read_json(static_dir / "citic-monthly-daily-2026.json")
    delivery_citic = _read_json(static_dir / "delivery-days-citic-and-index-2026.json")

    data_date = str(review.get("data_date") or day)
    market_board = _build_market_board_soft(data_date)
    citic = _sync_citic_monthly(citic, market_board=market_board, as_of=data_date, static_dir=static_dir)
    impact_events = _soft_refresh_impact_events(impact_path, as_of=data_date)
    bond_review = _build_bond_review_soft(as_of=data_date, rows=rows_out)

    bundle = {
        "dataDate": data_date,
        "generatedAt": datetime.now(SHANGHAI).isoformat(),
        "breadthPct": review.get("breadth_pct"),
        "ret30Entry": review.get("ret30_entry"),
        "ret30AsOf": review.get("ret30_as_of") or review.get("data_date"),
        "counts": {"byAction": by_action, "byTrend": by_trend},
        "bondReview": bond_review,
        "marketBoard": market_board,
        "rows": rows_out,
        "impactEvents": impact_events,
        "eventMatrix": _read_json(matrix_path),
        "deliveryCalendar": delivery,
        "citicMonthly": citic,
        "deliveryCiticIndex": delivery_citic,
    }
    return bundle


def _sync_citic_monthly(
    citic: dict[str, Any] | None,
    *,
    market_board: dict[str, Any] | None,
    as_of: str,
    static_dir: Path,
) -> dict[str, Any] | None:
    """Merge local cffex-daily exports into citicMonthly and persist when changed."""
    from src.citic_sync import default_cffex_dirs, merge_cffex_into_citic_monthly

    merged = merge_cffex_into_citic_monthly(
        citic,
        cffex_dirs=default_cffex_dirs(REPO_ROOT),
        market_board=market_board,
        as_of=as_of,
    )
    if not isinstance(merged, dict):
        return citic
    # Persist so next offline assemble keeps the new day.
    try:
        if merged is not citic:
            target = static_dir / "citic-monthly-daily-2026.json"
            target.write_text(
                json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    except OSError:
        pass
    return merged


def _build_market_board_soft(as_of: str, *, live: bool | None = None) -> dict[str, Any]:
    """Best-effort two-market turnover + major indices for the dashboard."""
    try:
        from src.market_snapshot import build_market_board

        return build_market_board(as_of=as_of or None, live=live)
    except Exception as exc:  # noqa: BLE001 — dashboard still renders without it
        return {
            "ok": False,
            "error": str(exc)[:160],
            "asOf": as_of or None,
            "live": bool(live),
            "fetchedAt": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
            "turnover": {},
            "indices": [],
        }


def _patch_latest_market_board(
    *,
    live: bool = True,
    with_news: bool = False,
) -> dict[str, Any]:
    """Refresh live open-board fields into latest.json without full assemble."""
    latest_path = OUT_DIR / "latest.json"
    if not latest_path.exists():
        return {"ok": False, "error": "no_latest_json"}
    try:
        bundle = json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"latest_unreadable:{exc}"}
    if not isinstance(bundle, dict):
        return {"ok": False, "error": "latest_not_object"}

    data_date = str(bundle.get("dataDate") or "")
    market_board = _build_market_board_soft(data_date, live=live)
    static_dir = Path(os.environ.get("ETF68_STATIC_DIR") or (REPO_ROOT / "data" / "static"))
    citic = bundle.get("citicMonthly")
    if isinstance(citic, dict) or citic is None:
        citic = _sync_citic_monthly(
            citic if isinstance(citic, dict) else None,
            market_board=market_board,
            as_of=data_date or datetime.now(SHANGHAI).date().isoformat(),
            static_dir=static_dir,
        )
        bundle["citicMonthly"] = citic

    if with_news:
        impact_path = REPORTS / f"etf68-impact-events-{data_date}.json"
        refreshed = _soft_refresh_impact_events(impact_path, as_of=data_date)
        if refreshed is not None:
            bundle["impactEvents"] = refreshed

    bundle["marketBoard"] = market_board
    rows = bundle.get("rows") if isinstance(bundle.get("rows"), list) else []
    bond_review = _build_bond_review_soft(as_of=data_date, rows=rows)
    bundle["bondReview"] = bond_review
    bundle.pop("trendScoreCard", None)
    # Keep full-generate timestamp; surface live stamp on marketBoard.fetchedAt.
    try:
        text = json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"
        latest_path.write_text(text, encoding="utf-8")
    except OSError as exc:
        return {
            "ok": False,
            "error": f"write_failed:{exc}",
            "marketBoard": market_board,
            "bondReview": bond_review,
        }

    return {
        "ok": True,
        "dataDate": data_date,
        "marketBoard": market_board,
        "bondReview": bond_review,
        "citicMonthly": bundle.get("citicMonthly"),
        "impactEvents": bundle.get("impactEvents") if with_news else None,
        "latestPath": str(latest_path),
    }


def cmd_refresh_board(args: argparse.Namespace) -> int:
    """Soft-refresh dashboard live fields (indices/turnover[/news]) into latest.json."""
    try:
        result = _patch_latest_market_board(
            live=not bool(getattr(args, "historical", False)),
            with_news=bool(getattr(args, "with_news", False)),
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") else 1
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1



def _build_bond_review_soft(
    *,
    as_of: str,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Best-effort 今日债市收评 for the dashboard."""
    try:
        from src.bond_review import build_bond_review

        return build_bond_review(as_of=as_of or None, rows=rows or [])
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc)[:160],
            "asOf": as_of or None,
            "fetchedAt": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
            "rate": {"buckets": []},
            "credit": {},
            "summary": "",
        }


def _build_trend_score_from_review(review: dict[str, Any]) -> dict[str, Any]:
    from src.trend_score import build_trend_score_card

    rows = review.get("rows") or []
    return build_trend_score_card(rows if isinstance(rows, list) else [])


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _soft_refresh_impact_events(path: Path, *, as_of: str) -> Any | None:
    """Merge Eastmoney live headlines into existing 实质利好/利空; soft-fail."""
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return payload
    try:
        from build_substantive_impact_events import merge_live_into_impact, parse_event_date

        day = parse_event_date(as_of) or datetime.now(SHANGHAI).date()
        refreshed = merge_live_into_impact(payload, as_of=day)
        if refreshed is not payload and path.parent.exists():
            try:
                path.write_text(json.dumps(refreshed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except OSError:
                pass
        return refreshed
    except Exception:  # noqa: BLE001
        return payload


def cmd_check_python(_: argparse.Namespace) -> int:
    tts_ok = False
    tts_error = None
    try:
        import edge_tts  # noqa: F401

        tts_ok = True
    except Exception as exc:  # noqa: BLE001
        tts_error = str(exc)
    print(
        json.dumps(
            {
                "ok": True,
                "python": sys.version.split()[0],
                "executable": sys.executable,
                "engineRoot": str(ENGINE_ROOT),
                "ttsOk": tts_ok,
                "ttsError": tts_error,
            },
            ensure_ascii=False,
        )
    )
    return 0


def cmd_tts(args: argparse.Namespace) -> int:
    """Synthesize Chinese speech with Edge TTS; prints JSON with audio path."""
    text = (args.text or "").strip()
    if not text and args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8").strip()
    if not text:
        print(json.dumps({"ok": False, "error": "empty_text"}, ensure_ascii=False))
        return 1

    from src.tts_edge import DEFAULT_PITCH, DEFAULT_RATE, DEFAULT_VOICE, cache_key, synthesize

    voice = args.voice or DEFAULT_VOICE
    rate = args.rate or DEFAULT_RATE
    pitch = args.pitch or DEFAULT_PITCH
    cache_dir = Path(os.environ.get("ETF68_TTS_CACHE") or (OUT_DIR / "tts-cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = cache_key(text, voice, rate, pitch)
    out_path = Path(args.output) if args.output else (cache_dir / f"{key}.mp3")

    try:
        if out_path.exists() and out_path.stat().st_size > 256 and not args.force:
            result = {
                "ok": True,
                "path": str(out_path),
                "bytes": out_path.stat().st_size,
                "voice": voice,
                "rate": rate,
                "pitch": pitch,
                "cached": True,
            }
        else:
            result = synthesize(text, out_path, voice=voice, rate=rate, pitch=pitch)
            result["cached"] = False
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


def cmd_load_latest(_: argparse.Namespace) -> int:
    latest = OUT_DIR / "latest.json"
    if not latest.exists():
        print(json.dumps({"ok": False, "error": "no_latest_bundle"}, ensure_ascii=False))
        return 1
    data = json.loads(latest.read_text(encoding="utf-8"))
    print(json.dumps({"ok": True, "bundle": data}, ensure_ascii=False))
    return 0


def _refresh_funds_top30(*, rebuild: bool = False, output: Path | None = None) -> dict[str, Any]:
    """Refresh 30-fund pool NAV / estimates; returns summary dict (raises on hard failure)."""
    from src.funds_top30 import build_funds_top30, write_funds_top30

    out = output or (OUT_DIR / "funds-top30.json")
    previous = None
    if out.exists() and not rebuild:
        try:
            previous = json.loads(out.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            previous = None

    result = build_funds_top30(rebuild=rebuild, previous=previous)
    write_funds_top30(out, result)
    return {
        "ok": True,
        "asOf": result.get("asOf"),
        "counts": result.get("counts"),
        "rowCount": len(result.get("rows") or []),
        "outputPath": str(out),
        "rebuilt": bool(rebuild) or not previous,
    }


def cmd_funds_top30(args: argparse.Namespace) -> int:
    """Build / refresh the 30 open-end mutual-fund representative pool."""
    out = Path(args.output) if args.output else (OUT_DIR / "funds-top30.json")
    try:
        summary = _refresh_funds_top30(rebuild=bool(args.rebuild), output=out)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


def _refresh_my_holdings(*, output: Path | None = None) -> dict[str, Any]:
    """Refresh personal holdings NAV / estimates + position advice."""
    from src.my_holdings import build_my_holdings, write_my_holdings

    out = output or (OUT_DIR / "my-holdings.json")
    previous = None
    if out.exists():
        try:
            previous = json.loads(out.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            previous = None
    result = build_my_holdings(previous=previous)
    write_my_holdings(out, result)
    return {
        "ok": True,
        "asOf": result.get("asOf"),
        "counts": result.get("counts"),
        "rowCount": len(result.get("rows") or []),
        "outputPath": str(out),
    }


def cmd_my_holdings(args: argparse.Namespace) -> int:
    """Build / refresh personal fund holdings archive."""
    out = Path(args.output) if args.output else (OUT_DIR / "my-holdings.json")
    try:
        summary = _refresh_my_holdings(output=out)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


def cmd_macro_pmi(args: argparse.Namespace) -> int:
    """Fetch Eastmoney PMI snapshot (+ optional curated overlay) to data/out."""
    from src.macro_pmi import fetch_macro_pmi, write_macro_pmi

    month = args.month
    out = Path(args.output) if args.output else (
        OUT_DIR / (f"macro-pmi-{month}.json" if month else "macro-pmi-latest.json")
    )
    try:
        snap = fetch_macro_pmi(month)
        if not snap.get("ok"):
            print(json.dumps(snap, ensure_ascii=False))
            return 1
        write_macro_pmi(out, snap)
        # Also refresh latest pointer when month omitted or explicit
        latest = OUT_DIR / "macro-pmi-latest.json"
        if out.resolve() != latest.resolve():
            write_macro_pmi(latest, snap)
        print(
            json.dumps(
                {
                    "ok": True,
                    "month": snap.get("month"),
                    "manufacturing": (snap.get("manufacturing") or {}).get("value"),
                    "nonManufacturing": (snap.get("nonManufacturing") or {}).get("value"),
                    "composite": (snap.get("composite") or {}).get("value")
                    if isinstance(snap.get("composite"), dict)
                    else None,
                    "outputPath": str(out),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


def cmd_macro_flash_script(args: argparse.Namespace) -> int:
    """Build macro-flash narration JSON from a PMI snapshot."""
    from src.macro_flash_script import build_macro_flash_script
    from src.macro_pmi import fetch_macro_pmi

    if args.snapshot:
        path = Path(args.snapshot)
        if not path.exists():
            print(json.dumps({"ok": False, "error": f"snapshot_missing:{path}"}, ensure_ascii=False))
            return 1
        snap = json.loads(path.read_text(encoding="utf-8"))
    else:
        snap = fetch_macro_pmi(args.month)
        if snap.get("ok"):
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / "macro-pmi-latest.json").write_text(
                json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

    result = build_macro_flash_script(snap, tone=args.tone, polish=bool(args.polish))
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = {**result, "outputPath": str(out)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def cmd_review_script(args: argparse.Namespace) -> int:
    """Build daily market-review narration JSON from a UiBundle."""
    from src.review_script import build_review_script

    if args.date:
        try:
            bundle = assemble_ui_bundle(args.date)
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            latest = OUT_DIR / "latest.json"
            latest.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1
    else:
        path = Path(args.bundle) if args.bundle else (OUT_DIR / "latest.json")
        if not path.exists():
            print(json.dumps({"ok": False, "error": f"bundle_missing:{path}"}, ensure_ascii=False))
            return 1
        bundle = json.loads(path.read_text(encoding="utf-8"))
        # Soft-refresh live headlines so video news is not stale vs. last assemble.
        day = str(bundle.get("dataDate") or "").strip()
        if day:
            impact_path = REPORTS / f"etf68-impact-events-{day}.json"
            refreshed = _soft_refresh_impact_events(impact_path, as_of=day)
            if isinstance(refreshed, dict):
                bundle["impactEvents"] = refreshed
                try:
                    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                except OSError:
                    pass

    result = build_review_script(bundle, polish=bool(args.polish))
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = {**result, "outputPath": str(out)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def cmd_assemble(args: argparse.Namespace) -> int:
    """Assemble UI bundle from existing engine/reports without network."""
    day = args.date
    if not day:
        dated = sorted(REPORTS.glob("representative-technical-review-*.json"))
        if not dated:
            print(json.dumps({"ok": False, "error": "no_review_json"}, ensure_ascii=False))
            return 1
        day = dated[-1].stem.split("-", 3)[-1] if False else dated[-1].name.replace(
            "representative-technical-review-", ""
        ).replace(".json", "")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        bundle = assemble_ui_bundle(day)
        latest = OUT_DIR / "latest.json"
        dated = OUT_DIR / f"bundle-{day}.json"
        text = json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"
        latest.write_text(text, encoding="utf-8")
        dated.write_text(text, encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": True,
                    "dataDate": bundle["dataDate"],
                    "rowCount": len(bundle["rows"]),
                    "latestPath": str(latest),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


def cmd_generate(args: argparse.Namespace) -> int:
    day = args.date or datetime.now(SHANGHAI).date().isoformat()
    REPORTS.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    seed = Path(args.seed) if args.seed else _find_seed(_prev_day(day))
    if not seed.exists():
        seed = _find_seed(day)

    review_json = REPORTS / f"representative-technical-review-{day}.json"
    review_md = REPORTS / f"representative-technical-review-{day}.md"
    review_csv = REPORTS / f"representative-technical-review-{day}.csv"
    edge_json = REPORTS / f"etf68-edge-conditions-{day}.json"
    weekly_json = REPORTS / f"etf68-weekly-macd-ma-backtest-{day}.json"
    kdj_json = REPORTS / f"etf68-daily-kdj-macd-backtest-{day}.json"
    impact_json = REPORTS / f"etf68-impact-events-{day}.json"
    matrix_json = REPORTS / f"etf68-event-etf-matrix-{day}.json"

    try:
        _run(
            [
                PY,
                "generate_review.py",
                "--seed",
                str(seed),
                "--output-json",
                str(review_json),
                "--output-markdown",
                str(review_md),
                "--output-csv",
                str(review_csv),
                "--workers",
                str(args.workers),
            ],
            step="generate_review",
        )
        _run(
            [
                PY,
                "analyze_edge_conditions.py",
                "--seed",
                str(review_json),
                "--output",
                str(edge_json),
                "--workers",
                str(max(2, args.workers // 2)),
            ],
            step="edge_conditions",
        )
        _run(
            [
                PY,
                "backtest_weekly_macd_ma.py",
                "--seed",
                str(review_json),
                "--output",
                str(weekly_json),
                "--apply-review",
                str(review_json),
                "--workers",
                str(args.workers),
            ],
            step="weekly_backtest",
        )
        _run(
            [
                PY,
                "backtest_daily_kdj_macd.py",
                "--date",
                day,
                "--workers",
                str(args.workers),
                "--output",
                str(kdj_json),
            ],
            step="daily_kdj_macd",
        )
        _run(
            [
                PY,
                "build_substantive_impact_events.py",
                "--date",
                day,
                "--per-side",
                "10",
                "--workers",
                str(args.workers),
                "--output",
                str(impact_json),
            ],
            step="impact_events",
        )
        _run(
            [
                PY,
                "build_event_etf_impact_matrix.py",
                "--date",
                day,
                "--output",
                str(matrix_json),
            ],
            step="event_matrix",
        )

        bundle = assemble_ui_bundle(day)
        latest = OUT_DIR / "latest.json"
        dated = OUT_DIR / f"bundle-{day}.json"
        latest.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        dated.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # 30 公募与 ETF 日更并存；失败不阻断 ETF 产物
        funds_summary: dict[str, Any] | None = None
        print(json.dumps({"event": "step_start", "step": "funds_top30"}, ensure_ascii=False), flush=True)
        try:
            funds_summary = _refresh_funds_top30(rebuild=False)
            print(
                json.dumps({"event": "step_done", "step": "funds_top30", **funds_summary}, ensure_ascii=False),
                flush=True,
            )
        except Exception as funds_exc:  # noqa: BLE001
            print(
                json.dumps(
                    {
                        "event": "step_error",
                        "step": "funds_top30",
                        "ok": False,
                        "error": str(funds_exc),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

        holdings_summary: dict[str, Any] | None = None
        print(json.dumps({"event": "step_start", "step": "my_holdings"}, ensure_ascii=False), flush=True)
        try:
            holdings_summary = _refresh_my_holdings()
            print(
                json.dumps({"event": "step_done", "step": "my_holdings", **holdings_summary}, ensure_ascii=False),
                flush=True,
            )
        except Exception as hold_exc:  # noqa: BLE001
            print(
                json.dumps(
                    {
                        "event": "step_error",
                        "step": "my_holdings",
                        "ok": False,
                        "error": str(hold_exc),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

        print(
            json.dumps(
                {
                    "event": "done",
                    "ok": True,
                    "dataDate": bundle["dataDate"],
                    "rowCount": len(bundle["rows"]),
                    "latestPath": str(latest),
                    "counts": bundle["counts"],
                    "fundsTop30": funds_summary,
                    "myHoldings": holdings_summary,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"event": "error", "ok": False, "error": str(exc)}, ensure_ascii=False), flush=True)
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_gen = sub.add_parser("generate", help="Run full daily pipeline")
    p_gen.add_argument("--date", default=None)
    p_gen.add_argument("--seed", default=None)
    p_gen.add_argument("--workers", type=int, default=6)
    p_gen.set_defaults(func=cmd_generate)

    p_load = sub.add_parser("load-latest", help="Print latest UI bundle")
    p_load.set_defaults(func=cmd_load_latest)

    p_asm = sub.add_parser("assemble", help="Assemble UI bundle from existing reports")
    p_asm.add_argument("--date", default=None)
    p_asm.set_defaults(func=cmd_assemble)

    p_chk = sub.add_parser("check-python", help="Verify runtime")
    p_chk.set_defaults(func=cmd_check_python)

    p_tts = sub.add_parser("tts", help="Synthesize speech with Edge TTS")
    p_tts.add_argument("--text", default=None, help="Plain Chinese text to speak")
    p_tts.add_argument("--text-file", default=None, help="Read text from file")
    p_tts.add_argument("--output", default=None, help="Output mp3 path")
    p_tts.add_argument("--voice", default=None, help="Edge neural voice id")
    p_tts.add_argument("--rate", default=None, help='Prosody rate, e.g. "-8%"')
    p_tts.add_argument("--pitch", default=None, help='Prosody pitch, e.g. "+0Hz"')
    p_tts.add_argument("--force", action="store_true", help="Ignore cache")
    p_tts.set_defaults(func=cmd_tts)

    p_rev = sub.add_parser("review-script", help="Build daily market-review narration JSON")
    p_rev.add_argument("--date", default=None, help="Assemble this date before scripting")
    p_rev.add_argument(
        "--bundle",
        default=None,
        help="Path to UiBundle JSON (default: latest.json)",
    )
    p_rev.add_argument(
        "--output",
        default=None,
        help="Optional path to write the review-script JSON",
    )
    p_rev.add_argument(
        "--polish",
        dest="polish",
        action="store_true",
        default=True,
        help="Oral-polish narration (default on)",
    )
    p_rev.add_argument(
        "--no-polish",
        dest="polish",
        action="store_false",
        help="Keep raw template narration",
    )
    p_rev.set_defaults(func=cmd_review_script)

    p_pmi = sub.add_parser("macro-pmi", help="Fetch China PMI snapshot (Eastmoney + overlay)")
    p_pmi.add_argument("--month", default=None, help="YYYY-MM (default: latest in feed)")
    p_pmi.add_argument(
        "--output",
        default=None,
        help="Output JSON (default: data/out/macro-pmi-{month}.json)",
    )
    p_pmi.set_defaults(func=cmd_macro_pmi)

    p_flash = sub.add_parser("macro-flash-script", help="Build PMI macro-flash narration JSON")
    p_flash.add_argument("--month", default=None, help="YYYY-MM; fetches PMI if no --snapshot")
    p_flash.add_argument(
        "--snapshot",
        default=None,
        help="Path to macro-pmi JSON (skip network)",
    )
    p_flash.add_argument(
        "--tone",
        choices=("neutral", "caution"),
        default="neutral",
        help="Metaphor tone (default neutral; avoids copying viral hooks)",
    )
    p_flash.add_argument(
        "--output",
        default=None,
        help="Optional path to write macro_flash_script.json",
    )
    p_flash.add_argument(
        "--polish",
        dest="polish",
        action="store_true",
        default=True,
        help="Oral-polish narration (default on)",
    )
    p_flash.add_argument(
        "--no-polish",
        dest="polish",
        action="store_false",
        help="Keep raw template narration",
    )
    p_flash.set_defaults(func=cmd_macro_flash_script)

    p_funds = sub.add_parser("funds-top30", help="Build/refresh 30 open-end fund pool + NAV")
    p_funds.add_argument(
        "--rebuild",
        action="store_true",
        help="Re-rank universe by AUM (otherwise reuse cached codes)",
    )
    p_funds.add_argument(
        "--output",
        default=None,
        help="Output JSON path (default: data/out/funds-top30.json)",
    )
    p_funds.set_defaults(func=cmd_funds_top30)

    p_hold = sub.add_parser("my-holdings", help="Build/refresh personal fund holdings + position advice")
    p_hold.add_argument(
        "--output",
        default=None,
        help="Output JSON path (default: data/out/my-holdings.json)",
    )
    p_hold.set_defaults(func=cmd_my_holdings)

    p_board = sub.add_parser(
        "refresh-board",
        help="Soft-refresh dashboard live market board (indices/turnover) into latest.json",
    )
    p_board.add_argument(
        "--historical",
        action="store_true",
        help="Use end-of-day bars for bundle dataDate instead of live tape",
    )
    p_board.add_argument(
        "--with-news",
        action="store_true",
        help="Also soft-refresh 实质利好/利空 live headlines",
    )
    p_board.set_defaults(func=cmd_refresh_board)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
