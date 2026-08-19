"""Sync CFFEX daily citic exports into static citic-monthly JSON for the dashboard."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional

from src.a_share_calendar import recent_trading_days

WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

# Full generate should backfill any missing rows in this window.
LOOKBACK_TRADING_DAYS = 10
_FETCH_TIMEOUT_S = 18.0


def _num(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def _stance(lots: Optional[float]) -> str:
    if lots is None:
        return "—"
    if lots > 0:
        return "净加多"
    if lots < 0:
        return "净加空"
    return "平"


def _label(lots: Optional[float]) -> str:
    if lots is None:
        return "—"
    n = int(lots)
    if n >= 0:
        return f"加多单{n}手"
    return f"加空单{abs(n)}手"


def _load_cffex(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _day_from_cffex(
    data: dict[str, Any],
    *,
    index_pct: dict[str, Optional[float]] | None = None,
) -> dict[str, Any] | None:
    stem = str(data.get("trade_date") or "")
    if len(stem) != 8:
        return None
    day = f"{stem[:4]}-{stem[4:6]}-{stem[6:8]}"
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return None
    by = data.get("citic_by_symbol") or {}
    citic_total = _num(data.get("citic_total"))
    if citic_total is None:
        vals = [_num(by.get(k)) for k in ("IH", "IF", "IC", "IM")]
        if all(v is not None for v in vals):
            citic_total = sum(vals)  # type: ignore[arg-type]
    grand = _num(data.get("net_buy_total"))
    other = None
    if grand is not None and citic_total is not None:
        other = grand - citic_total
    row: dict[str, Any] = {
        "date": day,
        "weekday": WEEKDAYS[d.weekday()],
        "citicTotal": int(citic_total) if citic_total is not None else None,
        "stance": _stance(citic_total),
        "label": _label(citic_total),
        "IH": int(by["IH"]) if _num(by.get("IH")) is not None else None,
        "IF": int(by["IF"]) if _num(by.get("IF")) is not None else None,
        "IC": int(by["IC"]) if _num(by.get("IC")) is not None else None,
        "IM": int(by["IM"]) if _num(by.get("IM")) is not None else None,
        "isDelivery": False,
        "otherTotal": int(other) if other is not None else None,
        "grandTotal": int(grand) if grand is not None else None,
        "otherStance": _stance(other),
        "grandStance": _stance(grand),
    }
    if index_pct:
        for key in ("shPct", "szPct", "cybPct", "kcbPct"):
            if index_pct.get(key) is not None:
                row[key] = index_pct[key]
    return row


def _index_pct_from_board(board: dict[str, Any] | None) -> dict[str, Optional[float]]:
    out: dict[str, Optional[float]] = {
        "shPct": None,
        "szPct": None,
        "cybPct": None,
        "kcbPct": None,
    }
    if not board:
        return out
    mapping = {"sh": "shPct", "sz": "szPct", "cyb": "cybPct", "kcb": "kcbPct"}
    for idx in board.get("indices") or []:
        key = mapping.get(str(idx.get("id") or ""))
        if not key:
            continue
        out[key] = _num(idx.get("changePct"))
    return out


_INDEX_PCT_KEYS = ("shPct", "szPct", "cybPct", "kcbPct")


def _index_pct_incomplete(day: dict[str, Any]) -> bool:
    vals = [day.get(k) for k in _INDEX_PCT_KEYS]
    if any(v is None for v in vals):
        return True
    return all(_num(v) == 0 for v in vals)


def _apply_index_pct_map(
    by_date: dict[str, dict[str, Any]],
    index_pct_by_date: dict[str, dict[str, Any]] | None,
) -> bool:
    """Fill missing / all-zero 四大指数涨跌 from historical close-to-close map."""
    if not index_pct_by_date:
        return False
    changed = False
    for iso, day in by_date.items():
        if not _index_pct_incomplete(day):
            continue
        src = index_pct_by_date.get(iso)
        if not src:
            continue
        placeholder = all(_num(day.get(k)) == 0 for k in _INDEX_PCT_KEYS) and all(
            day.get(k) is not None for k in _INDEX_PCT_KEYS
        )
        for key in _INDEX_PCT_KEYS:
            incoming = _num(src.get(key))
            if incoming is None:
                continue
            current = day.get(key)
            if current is None or (placeholder and _num(current) == 0):
                day[key] = incoming
                changed = True
    return changed


def merge_cffex_into_citic_monthly(
    monthly: dict[str, Any] | None,
    *,
    cffex_dirs: list[Path],
    market_board: dict[str, Any] | None = None,
    as_of: str | None = None,
    index_pct_by_date: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Upsert daily citic-net-positions-*.json rows into citicMonthly payload."""
    if not isinstance(monthly, dict):
        return monthly
    files: list[Path] = []
    for d in cffex_dirs:
        if not d.is_dir():
            continue
        files.extend(sorted(d.glob("citic-net-positions-????????.json")))

    index_pct = _index_pct_from_board(market_board)
    board_as_of = str((market_board or {}).get("asOf") or "")

    by_date: dict[str, dict[str, Any]] = {}
    for month in monthly.get("months") or []:
        for day in month.get("days") or []:
            if day.get("date"):
                by_date[str(day["date"])] = dict(day)

    changed = False
    for path in files:
        data = _load_cffex(path)
        if not data:
            continue
        # Only attach live index pct when the board session matches this day.
        stem = str(data.get("trade_date") or "")
        day_iso = f"{stem[:4]}-{stem[4:6]}-{stem[6:8]}" if len(stem) == 8 else ""
        pct = index_pct if day_iso and day_iso == board_as_of else None
        row = _day_from_cffex(data, index_pct=pct)
        if not row or not row.get("date"):
            continue
        prev = by_date.get(row["date"])
        if prev:
            merged = dict(prev)
            for k, v in row.items():
                if v is not None:
                    merged[k] = v
            # Keep prior index pcts if this file has none.
            row = merged
        if prev != row:
            changed = True
        by_date[row["date"]] = row

    if _apply_index_pct_map(by_date, index_pct_by_date):
        changed = True

    if not changed and as_of and as_of in by_date:
        # Still refresh asOf stamp when today's row already present.
        out = dict(monthly)
        out["asOf"] = max(str(monthly.get("asOf") or ""), as_of)
        return out
    if not changed:
        return monthly

    # Rebuild months 1..12 for the year of as_of / latest day.
    year = int((as_of or max(by_date))[:4])
    months_out: list[dict[str, Any]] = []
    for month_i in range(1, 13):
        days = sorted(
            (d for d in by_date.values() if str(d["date"]).startswith(f"{year}-{month_i:02d}")),
            key=lambda x: str(x["date"]),
        )
        if not days and not any(
            str(m.get("month")) == str(month_i) for m in (monthly.get("months") or [])
        ):
            # Preserve empty placeholder months only if they existed.
            continue
        # Prefer keeping existing month meta when present.
        prev_month = next(
            (m for m in (monthly.get("months") or []) if int(m.get("month") or 0) == month_i),
            None,
        )
        totals = [_num(d.get("citicTotal")) for d in days]
        totals_i = [int(t) for t in totals if t is not None]
        month_net = sum(totals_i) if totals_i else (prev_month or {}).get("monthNet")
        long_days = sum(1 for t in totals_i if t > 0)
        short_days = sum(1 for t in totals_i if t < 0)
        months_out.append(
            {
                "month": month_i,
                "label": f"{year}-{month_i:02d}",
                "days": days,
                "monthNet": month_net,
                "longDays": long_days,
                "shortDays": short_days,
                "n": len(days),
            }
        )

    latest = max(by_date) if by_date else as_of
    out = dict(monthly)
    out["months"] = months_out
    out["asOf"] = latest
    out["generatedAt"] = datetime.now().isoformat(timespec="seconds")
    return out


def default_cffex_dirs(repo_root: Path) -> list[Path]:
    home = Path.home()
    return [
        home / "Desktop/github/my_tool_project/modules/cffex-daily/work/output",
        repo_root / "cffex-daily" / "work" / "output",
        repo_root / "data" / "static" / "cffex-cache",
    ]


def cffex_module_roots(repo_root: Path) -> list[Path]:
    home = Path.home()
    return [
        home / "Desktop/github/my_tool_project/modules/cffex-daily",
        repo_root / "cffex-daily",
    ]


def _existing_dates(monthly: dict[str, Any] | None) -> set[str]:
    out: set[str] = set()
    if not isinstance(monthly, dict):
        return out
    for month in monthly.get("months") or []:
        for day in month.get("days") or []:
            if day.get("date"):
                out.add(str(day["date"]))
    return out


def _export_path_for_day(cffex_dirs: list[Path], day: date) -> Path | None:
    stem = day.strftime("%Y%m%d")
    name = f"citic-net-positions-{stem}.json"
    for d in cffex_dirs:
        path = d / name
        if path.is_file() and path.stat().st_size > 50:
            return path
    return None


def _resolve_fetch_report(repo_root: Path) -> Callable[[date], dict[str, Any]] | None:
    for root in cffex_module_roots(repo_root):
        script = root / "fetch_and_render.py"
        if not script.is_file():
            continue
        root_s = str(root)
        if root_s not in sys.path:
            sys.path.insert(0, root_s)
        try:
            from fetch_and_render import fetch_report  # type: ignore
        except Exception:
            continue
        return fetch_report
    return None


def _write_export(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _curl_get_gbk(url: str, *, timeout_s: float) -> str:
    """Prefer curl --ipv4; CFFEX IPv6 often hangs Python urllib on this host."""
    import subprocess

    cmd = [
        "curl",
        "-fsS",
        "--ipv4",
        "-m",
        str(max(3, int(timeout_s))),
        "-A",
        "Mozilla/5.0",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")[:120]
        raise RuntimeError(f"curl_failed:{proc.returncode}:{err}")
    return proc.stdout.decode("gbk", "replace")


def _parse_cffex_rows(csv_text: str) -> list[list[str]]:
    import csv
    from io import StringIO

    reader = csv.reader(StringIO(csv_text.strip()))
    next(reader, None)
    next(reader, None)
    return [row for row in reader if len(row) >= 12]


CITIC_MEMBER = "中信期货(代客)"


def _citic_net_change(rows: list[list[str]]) -> int:
    long_change = 0
    short_change = 0
    for row in rows:
        if row[6] == CITIC_MEMBER:
            long_change += int(row[8])
        if row[9] == CITIC_MEMBER:
            short_change += int(row[11])
    return long_change - short_change


def _all_members_net_buy(rows: list[list[str]]) -> int:
    from collections import defaultdict

    members: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        members[row[6]][0] += int(row[8])
        members[row[9]][1] += int(row[11])
    return sum(long_c - short_c for long_c, short_c in members.values())


def fetch_cffex_report_direct(trade_date: date, *, timeout_s: float = _FETCH_TIMEOUT_S) -> dict[str, Any]:
    """Fetch IH/IF/IC/IM ranking CSVs and build the citic-net-positions payload."""
    symbol_rows: dict[str, list[list[str]]] = {}
    ymd = trade_date.strftime("%Y%m%d")
    y, m, d = ymd[:4], ymd[4:6], ymd[6:8]
    for symbol in ("IH", "IF", "IC", "IM"):
        url = f"http://www.cffex.com.cn/sj/ccpm/{y}{m}/{d}/{symbol}_1.csv"
        csv_text = _curl_get_gbk(url, timeout_s=timeout_s)
        rows = _parse_cffex_rows(csv_text)
        if not rows:
            raise RuntimeError(f"{symbol}_empty_rows:{ymd}")
        symbol_rows[symbol] = rows

    citic_by_symbol = {symbol: _citic_net_change(rows) for symbol, rows in symbol_rows.items()}
    citic_total = sum(citic_by_symbol.values())
    net_buy_total = sum(_all_members_net_buy(rows) for rows in symbol_rows.values())
    return {
        "trade_date": ymd,
        "citic_by_symbol": citic_by_symbol,
        "citic_total": citic_total,
        "net_buy_total": net_buy_total,
    }


def _call_with_timeout(fn: Callable[[], Any], *, timeout_s: float) -> Any:
    import threading

    box: dict[str, Any] = {}

    def _run() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        raise TimeoutError(f"fetch_timeout_{timeout_s}s")
    if "error" in box:
        raise box["error"]
    return box.get("value")


def ensure_recent_cffex_exports(
    monthly: dict[str, Any] | None,
    *,
    as_of: str,
    repo_root: Path,
    cffex_dirs: list[Path] | None = None,
    lookback_trading_days: int = LOOKBACK_TRADING_DAYS,
    fetch_report: Callable[[date], dict[str, Any]] | None = None,
    timeout_s: float = _FETCH_TIMEOUT_S,
) -> dict[str, Any]:
    """Fetch missing citic-net-positions for the last N trading days (缺日就补).

    Soft-fails per day: network/CFFEX gaps never raise. Returns a small summary
    for generate logs.
    """
    dirs = list(cffex_dirs or default_cffex_dirs(repo_root))
    write_dir = next((d for d in dirs if d.is_dir()), dirs[-1])
    have = _existing_dates(monthly)
    window = recent_trading_days(as_of, count=lookback_trading_days)
    missing = [d for d in window if d.isoformat() not in have]

    summary: dict[str, Any] = {
        "ok": True,
        "asOf": as_of,
        "lookback": lookback_trading_days,
        "window": [d.isoformat() for d in window],
        "missing": [d.isoformat() for d in missing],
        "fetched": [],
        "reused": [],
        "failed": [],
    }
    if not missing:
        return summary

    # Prefer injectable fetcher (tests); else direct curl; else cffex-daily module.
    fallback = _resolve_fetch_report(repo_root)

    for day in missing:
        existing = _export_path_for_day(dirs, day)
        if existing is not None:
            summary["reused"].append(day.isoformat())
            continue
        try:
            per_day_budget = max(timeout_s * 4, 30.0)

            def _do_fetch(d: date = day) -> dict[str, Any]:
                if fetch_report is not None:
                    return fetch_report(d)
                try:
                    return fetch_cffex_report_direct(d, timeout_s=timeout_s)
                except Exception:
                    if fallback is None:
                        raise
                    return fallback(d)

            report = _call_with_timeout(lambda: _do_fetch(), timeout_s=per_day_budget)
            if not isinstance(report, dict) or "citic_total" not in report:
                raise RuntimeError("invalid_cffex_report")
            out_path = write_dir / f"citic-net-positions-{day.strftime('%Y%m%d')}.json"
            _write_export(out_path, report)
            summary["fetched"].append(day.isoformat())
        except Exception as exc:  # noqa: BLE001 — soft-fail for generate
            summary["failed"].append({"date": day.isoformat(), "error": str(exc)[:160]})

    summary["ok"] = not summary["failed"] or bool(summary["fetched"] or summary["reused"])
    return summary
