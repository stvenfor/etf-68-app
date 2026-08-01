"""Sync CFFEX daily citic exports into static citic-monthly JSON for the dashboard."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


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


def merge_cffex_into_citic_monthly(
    monthly: dict[str, Any] | None,
    *,
    cffex_dirs: list[Path],
    market_board: dict[str, Any] | None = None,
    as_of: str | None = None,
) -> dict[str, Any] | None:
    """Upsert daily citic-net-positions-*.json rows into citicMonthly payload."""
    if not isinstance(monthly, dict):
        return monthly
    files: list[Path] = []
    for d in cffex_dirs:
        if not d.is_dir():
            continue
        files.extend(sorted(d.glob("citic-net-positions-????????.json")))
    if not files:
        return monthly

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
    ]
