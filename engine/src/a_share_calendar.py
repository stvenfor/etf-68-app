"""A-share trading calendar helpers (static holidays + makeup sessions)."""

from __future__ import annotations

from datetime import date, timedelta

# SSE/SZSE closed weekdays (国务院放假). Makeup Saturdays listed separately.
_CLOSED_WEEKDAYS = frozenset(
    {
        # 2025
        "2025-01-01",
        "2025-01-28",
        "2025-01-29",
        "2025-01-30",
        "2025-01-31",
        "2025-02-03",
        "2025-02-04",
        "2025-04-04",
        "2025-05-01",
        "2025-05-02",
        "2025-05-05",
        "2025-06-02",
        "2025-10-01",
        "2025-10-02",
        "2025-10-03",
        "2025-10-06",
        "2025-10-07",
        "2025-10-08",
        # 2026
        "2026-01-01",
        "2026-01-02",
        "2026-02-16",
        "2026-02-17",
        "2026-02-18",
        "2026-02-19",
        "2026-02-20",
        "2026-02-23",
        "2026-04-06",
        "2026-05-01",
        "2026-05-04",
        "2026-05-05",
        "2026-06-19",
        "2026-09-25",
        "2026-10-01",
        "2026-10-02",
        "2026-10-05",
        "2026-10-06",
        "2026-10-07",
    }
)

_MAKEUP_TRADING_DAYS = frozenset(
    {
        "2025-01-26",
        "2025-02-08",
        "2025-04-27",
        "2025-09-28",
        "2025-10-11",
        "2026-01-04",
        "2026-02-14",
        "2026-02-28",
        "2026-05-09",
        "2026-09-20",
        "2026-10-10",
    }
)


def is_trading_day(d: date) -> bool:
    iso = d.isoformat()
    if iso in _MAKEUP_TRADING_DAYS:
        return True
    if iso in _CLOSED_WEEKDAYS:
        return False
    return d.weekday() < 5


def recent_trading_days(as_of: date | str, *, count: int = 10) -> list[date]:
    """Return the last ``count`` trading days on or before ``as_of`` (ascending)."""
    if count <= 0:
        return []
    end = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
    out: list[date] = []
    cur = end
    # Hard cap avoids infinite loops if calendar is misconfigured.
    for _ in range(max(count * 6, 40)):
        if is_trading_day(cur):
            out.append(cur)
            if len(out) >= count:
                break
        cur -= timedelta(days=1)
    out.reverse()
    return out
