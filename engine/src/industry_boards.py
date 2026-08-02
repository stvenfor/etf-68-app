"""Eastmoney industry board (行业板块) change rankings for review video.

True sector-level rises/falls — not averages of ETF pool sector labels.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any, Callable, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

EM_UT = "b2884a393a59ad64002292a3e90d46a5"
EM_HOSTS = (
    "https://push2delay.eastmoney.com",
    "https://push2.eastmoney.com",
    "https://82.push2.eastmoney.com",
)
# 东方财富行业板块
BOARD_FS = "m:90+t:2+f:!50"

_LEVEL_SUFFIX_RE = re.compile(r"(Ⅰ|Ⅱ|Ⅲ|Ⅳ|Ⅴ|III|II|IV|IX|VI{0,3}|I)$")
_LEVEL_ORDER = {
    "": 0,
    "Ⅰ": 1,
    "I": 1,
    "Ⅱ": 2,
    "II": 2,
    "Ⅲ": 3,
    "III": 3,
    "Ⅳ": 4,
    "IV": 4,
    "Ⅴ": 5,
    "V": 5,
}

_DIRECT = build_opener(ProxyHandler({}))

FetchFn = Callable[[str], str]


def _default_fetch(url: str, *, timeout: float = 25.0) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "*/*",
        },
    )
    with _DIRECT.open(req, timeout=timeout) as resp:  # noqa: S310 — public market data
        return resp.read().decode("utf-8", "replace")


def _num(v: Any) -> Optional[float]:
    if v is None or v == "-" or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def industry_stem(name: str) -> str:
    """Strip Eastmoney level suffixes: 银行Ⅱ → 银行."""
    return _LEVEL_SUFFIX_RE.sub("", (name or "").strip()).strip()


def _level_rank(name: str) -> int:
    stem = industry_stem(name)
    if name == stem:
        return 0
    return _LEVEL_ORDER.get(name[len(stem) :], 9)


def prefer_industry_row(
    left: tuple[str, str, float],
    right: tuple[str, str, float],
) -> tuple[str, str, float]:
    """Prefer unsuffixed / shallower level / shorter name / smaller code."""
    left_key = (_level_rank(left[1]), len(left[1]), left[0])
    right_key = (_level_rank(right[1]), len(right[1]), right[0])
    return left if left_key <= right_key else right


def dedupe_hierarchical_boards(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One board per industry stem; prefer shallowest raw name; display as stem."""
    winners: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        name = str(row.get("name") or "")
        chg = _num(row.get("changePct"))
        if chg is None or not name:
            continue
        stem = industry_stem(name)
        if not stem:
            continue
        code = str(row.get("code") or "")
        tup = (code, name, chg)
        if stem not in winners:
            winners[stem] = {**row, "name": stem, "_rawName": name}
            order.append(stem)
            continue
        cur = winners[stem]
        kept = prefer_industry_row(
            (
                str(cur.get("code") or ""),
                str(cur.get("_rawName") or cur.get("name") or stem),
                float(_num(cur.get("changePct")) or 0),
            ),
            tup,
        )
        if kept[0] == code:
            winners[stem] = {**row, "name": stem, "_rawName": name}
    out: list[dict[str, Any]] = []
    for key in order:
        item = dict(winners[key])
        item.pop("_rawName", None)
        out.append(item)
    return out


def _clist_url(host: str, *, pn: int, pz: int = 100) -> str:
    q = urlencode(
        {
            "pn": str(pn),
            "pz": str(pz),
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": BOARD_FS,
            "fields": "f12,f14,f2,f3",
            "ut": EM_UT,
            "_": str(int(time.time() * 1000)),
        }
    )
    return f"{host}/api/qt/clist/get?{q}"


def fetch_industry_boards(
    *,
    fetch: FetchFn | None = None,
    min_boards: int = 40,
) -> list[dict[str, Any]]:
    """Fetch all Eastmoney industry boards with day changePct."""
    fetch = fetch or _default_fetch
    rows: list[dict[str, Any]] = []
    last_err: Exception | None = None
    for pn in range(1, 20):
        payload: dict[str, Any] | None = None
        for host in EM_HOSTS:
            url = _clist_url(host, pn=pn)
            try:
                raw = fetch(url)
                payload = json.loads(raw)
                break
            except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
                last_err = exc
                continue
        if payload is None:
            if pn == 1 and last_err is not None:
                raise RuntimeError(f"industry_boards_fetch_failed:{last_err}") from last_err
            break
        diff = (payload.get("data") or {}).get("diff") or []
        items = diff if isinstance(diff, list) else list(diff.values())
        if not items:
            break
        for item in items:
            if not isinstance(item, dict):
                continue
            code = str(item.get("f12") or "").strip()
            name = str(item.get("f14") or "").strip()
            chg = _num(item.get("f3"))
            if not code or not name or chg is None:
                continue
            rows.append(
                {
                    "code": code,
                    "name": name,
                    "changePct": round(chg, 4),
                    "price": _num(item.get("f2")),
                }
            )
        if len(items) < 100:
            break

    by_code: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_code[str(row["code"])] = row
    unique = dedupe_hierarchical_boards(list(by_code.values()))
    unique.sort(key=lambda r: float(r["changePct"]), reverse=True)
    if len(unique) < min_boards:
        raise RuntimeError(f"industry_boards_too_few:{len(unique)}<{min_boards}")
    return unique


def top_bottom_industry_boards(
    boards: list[dict[str, Any]],
    n: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    """Map industry boards into review_script sector shape (sector + avgRet1)."""
    if not boards:
        return {"gainers": [], "losers": [], "source": "eastmoney_industry", "ok": False}

    def _row(b: dict[str, Any]) -> dict[str, Any]:
        return {
            "sector": str(b.get("name") or ""),
            "avgRet1": round(float(b["changePct"]), 4),
            "count": 1,
            "code": b.get("code"),
            "source": "eastmoney_industry",
        }

    ranked = sorted(boards, key=lambda b: float(b["changePct"]), reverse=True)
    gainers = [_row(b) for b in ranked[:n]]
    losers_raw = list(reversed(ranked[-n:])) if len(ranked) > n else list(reversed(ranked))
    g_names = {g["sector"] for g in gainers}
    losers = [x for x in (_row(b) for b in losers_raw) if x["sector"] not in g_names][:n]
    return {
        "gainers": gainers,
        "losers": losers,
        "source": "eastmoney_industry",
        "ok": True,
        "boardCount": len(ranked),
        "fetchedAt": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
    }


def build_industry_sector_ranks(
    *,
    n: int = 3,
    fetch: FetchFn | None = None,
) -> dict[str, Any]:
    """Fetch + rank; soft shape always returns gainers/losers keys."""
    try:
        boards = fetch_industry_boards(fetch=fetch)
        out = top_bottom_industry_boards(boards, n)
        return out
    except Exception as exc:  # noqa: BLE001 — soft-fail for review pipeline
        return {
            "gainers": [],
            "losers": [],
            "source": "eastmoney_industry",
            "ok": False,
            "error": str(exc)[:160],
            "fetchedAt": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        }
