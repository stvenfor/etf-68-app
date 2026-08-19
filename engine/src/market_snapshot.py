"""Fetch A-share open-board snapshot for daily review visuals.

Provides: two-market turnover (today + 5-day avg) and major index quotes.
Visual-only for the review video open chapter — not narrated.
Supports live tape refresh for the desktop dashboard.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable, Optional
from urllib.request import ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Local HTTP(S)_PROXY often points at a dead client; market hosts need direct egress.
_DIRECT = build_opener(ProxyHandler({}))

INDEX_SPECS: tuple[dict[str, str], ...] = (
    {
        "id": "sh",
        "code": "000001",
        "tencent": "sh000001",
        "name": "上证指数",
        "nameEn": "SSE",
    },
    {
        "id": "sz",
        "code": "399001",
        "tencent": "sz399001",
        "name": "深证成指",
        "nameEn": "SZSE",
    },
    {
        "id": "cyb",
        "code": "399006",
        "tencent": "sz399006",
        "name": "创业板指",
        "nameEn": "ChiNext",
    },
    {
        "id": "kcb",
        "code": "000688",
        "tencent": "sh000688",
        "name": "科创50",
        "nameEn": "STAR 50",
    },
)

FetchFn = Callable[[str], str]


def _default_fetch(url: str, *, timeout: float = 20.0) -> str:
    referer = "https://finance.qq.com/"
    if "eastmoney.com" in url:
        referer = "https://quote.eastmoney.com/"
    elif "sinajs.cn" in url or "sina.com.cn" in url:
        referer = "https://finance.sina.com.cn/"
    elif "gtimg.cn" in url:
        referer = "https://finance.qq.com/"
    req = Request(
        url,
        headers={"User-Agent": UA, "Referer": referer, "Accept": "*/*"},
    )
    with _DIRECT.open(req, timeout=timeout) as resp:  # noqa: S310 — public market data
        raw = resp.read()
    if "sinajs.cn" in url or "gtimg.cn/q=" in url:
        return raw.decode("gb18030", "replace")
    return raw.decode("utf-8", "replace")


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


def fmt_turnover_yi(yi: Optional[float]) -> str:
    """Format turnover in 亿 → readable 万亿 / 亿 label."""
    if yi is None:
        return "—"
    if abs(yi) >= 10_000:
        return f"{yi / 10_000:.2f}万亿"
    if abs(yi) >= 100:
        return f"{yi:.0f}亿"
    return f"{yi:.1f}亿"


def _parse_qq_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    if text.startswith("{"):
        return json.loads(text)
    # JSONP / _var=...
    if "=" in text[:40]:
        text = text.split("=", 1)[1]
    return json.loads(text)


def _fqkline_amount_map(symbol: str, *, fetch: FetchFn, days: int = 12) -> dict[str, float]:
    """Return {date: amount_yi} from Tencent newfqkline (field[8] is 万元)."""
    url = (
        "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
        f"?param={symbol},day,,,{days},qfq&r=0.5"
    )
    data = _parse_qq_json(fetch(url))
    rows = ((data.get("data") or {}).get(symbol) or {}).get("day") or []
    out: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 9:
            continue
        day = str(row[0])[:10]
        # index 8 = amount in 万元
        wan = _num(row[8])
        if not day or wan is None:
            continue
        out[day] = wan / 10_000.0  # → 亿
    return out


def _two_market_turnover(*, fetch: FetchFn, as_of: str | None = None) -> dict[str, Any]:
    sh = _fqkline_amount_map("sh000001", fetch=fetch)
    sz = _fqkline_amount_map("sz399001", fetch=fetch)
    dates = sorted(set(sh) & set(sz))
    if as_of:
        dates = [d for d in dates if d <= as_of]
    if not dates:
        return {"ok": False, "error": "no_turnover_series"}
    last5 = dates[-5:]
    series = [
        {
            "date": d,
            "amountYi": round(sh[d] + sz[d], 2),
            "shYi": round(sh[d], 2),
            "szYi": round(sz[d], 2),
        }
        for d in last5
    ]
    today = series[-1]
    avg5 = round(sum(x["amountYi"] for x in series) / len(series), 2)
    return {
        "ok": True,
        "date": today["date"],
        "amountYi": today["amountYi"],
        "amountLabel": fmt_turnover_yi(today["amountYi"]),
        "avg5Yi": avg5,
        "avg5Label": fmt_turnover_yi(avg5),
        "vsAvgPct": round((today["amountYi"] / avg5 - 1.0) * 100.0, 2) if avg5 else None,
        "series": series,
    }


def _parse_tencent_indices(raw: str) -> list[dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {}
    for chunk in re.split(r";\s*", raw or ""):
        if '="' not in chunk:
            continue
        try:
            body = chunk.split('="', 1)[1].rsplit('"', 1)[0]
        except IndexError:
            continue
        fields = body.split("~")
        if len(fields) < 33:
            continue
        code = str(fields[2] or "").zfill(6)
        price = _num(fields[3])
        prev = _num(fields[4])
        chg_pct = _num(fields[32])
        chg = None
        if price is not None and prev is not None:
            chg = round(price - prev, 2)
        if chg_pct is None and price is not None and prev not in (None, 0):
            chg_pct = round((price / prev - 1.0) * 100.0, 2)
        by_code[code] = {
            "code": code,
            "name": str(fields[1] or "").strip(),
            "price": price,
            "change": chg,
            "changePct": chg_pct,
        }
    out: list[dict[str, Any]] = []
    for spec in INDEX_SPECS:
        row = by_code.get(spec["code"], {})
        out.append(
            {
                "id": spec["id"],
                "code": spec["code"],
                "name": spec["name"],
                "nameEn": spec["nameEn"],
                "price": row.get("price"),
                "change": row.get("change"),
                "changePct": row.get("changePct"),
                "tone": _tone_from_pct(row.get("changePct")),
            }
        )
    return out


def fetch_index_quotes(*, fetch: FetchFn | None = None) -> list[dict[str, Any]]:
    fetch = fetch or _default_fetch
    symbols = ",".join(s["tencent"] for s in INDEX_SPECS)
    raw = fetch(f"https://qt.gtimg.cn/q={symbols}")
    return _parse_tencent_indices(raw)


INDEX_PCT_KEYS: dict[str, str] = {
    "sh": "shPct",
    "sz": "szPct",
    "cyb": "cybPct",
    "kcb": "kcbPct",
}


def fetch_index_pct_by_date(
    *,
    fetch: FetchFn | None = None,
    days: int = 220,
) -> dict[str, dict[str, float]]:
    """Daily close-to-close % for the four board indices: {date: {shPct, szPct, …}}."""
    fetch = fetch or _default_fetch
    out: dict[str, dict[str, float]] = {}
    for spec in INDEX_SPECS:
        key = INDEX_PCT_KEYS[spec["id"]]
        closes = _fqkline_close_map(spec["tencent"], fetch=fetch, days=days)
        dates = sorted(closes)
        for i in range(1, len(dates)):
            prev = closes[dates[i - 1]]
            cur = closes[dates[i]]
            if prev in (None, 0) or cur is None:
                continue
            pct = round((cur / prev - 1.0) * 100.0, 2)
            out.setdefault(dates[i], {})[key] = 0.0 if pct == 0 else pct
    return out


def _fqkline_close_map(symbol: str, *, fetch: FetchFn, days: int = 12) -> dict[str, float]:
    """Return {date: close} from Tencent newfqkline (field[2] is close)."""
    url = (
        "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
        f"?param={symbol},day,,,{days},qfq&r=0.5"
    )
    data = _parse_qq_json(fetch(url))
    rows = ((data.get("data") or {}).get(symbol) or {}).get("day") or []
    out: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue
        day = str(row[0])[:10]
        close = _num(row[2])
        if not day or close is None:
            continue
        out[day] = close
    return out


def _tone_from_pct(pct: Optional[float]) -> str:
    if isinstance(pct, (int, float)):
        if pct > 0:
            return "up"
        if pct < 0:
            return "dn"
    return "flat"


def fetch_index_quotes_as_of(
    as_of: str,
    *,
    fetch: FetchFn | None = None,
) -> list[dict[str, Any]]:
    """Index levels + day change for a specific session (via daily bars)."""
    fetch = fetch or _default_fetch
    out: list[dict[str, Any]] = []
    for spec in INDEX_SPECS:
        closes = _fqkline_close_map(spec["tencent"], fetch=fetch)
        dates = sorted(d for d in closes if d <= as_of)
        price = closes.get(dates[-1]) if dates else None
        prev = closes.get(dates[-2]) if len(dates) >= 2 else None
        chg = None
        chg_pct = None
        if price is not None and prev not in (None, 0):
            chg = round(price - prev, 2)
            chg_pct = round((price / prev - 1.0) * 100.0, 2)
        out.append(
            {
                "id": spec["id"],
                "code": spec["code"],
                "name": spec["name"],
                "nameEn": spec["nameEn"],
                "price": price,
                "change": chg,
                "changePct": chg_pct,
                "tone": _tone_from_pct(chg_pct),
                "asOf": dates[-1] if dates else None,
            }
        )
    return out


def _should_use_live(as_of: str | None, live: bool | None) -> bool:
    """Prefer live tape when explicitly requested or as_of is today/future."""
    if live is True:
        return True
    if live is False:
        return False
    today = datetime.now(SHANGHAI).date().isoformat()
    return as_of is None or as_of >= today


def build_market_board(
    *,
    as_of: str | None = None,
    fetch: FetchFn | None = None,
    live: bool | None = None,
) -> dict[str, Any]:
    """Build open-chapter market board payload (soft-fail friendly).

    ``live=True`` (or as_of is today) pulls Tencent realtime index quotes
    instead of end-of-day bars, for dashboard auto-refresh.
    """
    fetch = fetch or _default_fetch
    use_live = _should_use_live(as_of, live)
    fetched_at = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    turnover: dict[str, Any]
    indices: list[dict[str, Any]]
    try:
        # Live board uses the freshest turnover series (incl. today if present).
        turnover = _two_market_turnover(fetch=fetch, as_of=None if use_live else as_of)
    except Exception as exc:  # noqa: BLE001 — soft-fail for review pipeline
        turnover = {"ok": False, "error": str(exc)[:160]}
    try:
        if use_live:
            indices = fetch_index_quotes(fetch=fetch)
        else:
            indices = fetch_index_quotes_as_of(str(as_of), fetch=fetch)
            # If bars miss the session, fall back to live tape.
            if not any(i.get("price") is not None for i in indices):
                indices = fetch_index_quotes(fetch=fetch)
    except Exception as exc:  # noqa: BLE001
        indices = [
            {
                "id": s["id"],
                "code": s["code"],
                "name": s["name"],
                "nameEn": s["nameEn"],
                "price": None,
                "change": None,
                "changePct": None,
                "tone": "flat",
                "error": str(exc)[:80],
            }
            for s in INDEX_SPECS
        ]
    ok = bool(turnover.get("ok")) and any(i.get("price") is not None for i in indices)
    return {
        "ok": ok,
        "live": use_live,
        "fetchedAt": fetched_at,
        "asOf": (turnover.get("date") if turnover.get("ok") else as_of),
        "turnover": turnover,
        "indices": indices,
    }
