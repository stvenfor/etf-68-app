"""Unit tests for 20-day momentum + MA28 rotation."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from src.market_data import DailyBar  # noqa: E402
from src.mom20_ma28 import (  # noqa: E402
    SIGNAL_BUY,
    SIGNAL_HOLD,
    SIGNAL_NONE,
    SIGNAL_SWITCH,
    apply_mom20_ma28,
    metrics_on_date,
    should_exit_hold,
    simulate_rotation,
    step_rotation,
    strongest_eligible,
)


FETCHED_AT = datetime(2026, 7, 20, 18, 0, tzinfo=timezone(timedelta(hours=8)))


def _series(start: date, closes: list[float]) -> list[DailyBar]:
    return [
        DailyBar(
            date=start + timedelta(days=i),
            open=close,
            close=close,
            high=close * 1.01,
            low=close * 0.99,
            volume=1_000_000,
            turnover_cny=10_000_000,
            source="fixture",
            timestamp=FETCHED_AT,
        )
        for i, close in enumerate(closes)
    ]


def _flat_then(start: date, flat: float, n_flat: int, tail: list[float]) -> list[DailyBar]:
    return _series(start, [flat] * n_flat + tail)


class Mom20Ma28Tests(unittest.TestCase):
    def test_rank1_above_ma28_is_strongest_eligible(self) -> None:
        start = date(2026, 1, 1)
        # 50 flat days then strong rally on A; B stays flat.
        bars_a = _flat_then(start, 10.0, 40, [10 + i * 0.5 for i in range(1, 21)])
        bars_b = _flat_then(start, 10.0, 60, [])
        as_of = bars_a[-1].date
        metrics = metrics_on_date({"A": bars_a, "B": bars_b}, as_of)
        self.assertEqual(metrics[0].code, "A")
        self.assertEqual(metrics[0].rank, 1)
        self.assertTrue(metrics[0].above_ma28)
        self.assertEqual(strongest_eligible(metrics), "A")

    def test_rank1_below_ma28_blocks_entry(self) -> None:
        start = date(2026, 1, 1)
        # Climb for strong 20d ret, then gap well below the trailing MA28.
        body = [10.0] * 35 + [10 + i * 0.5 for i in range(1, 28)]
        closes = body[:-1] + [1.0]
        bars_a = _series(start, closes)
        bars_b = _flat_then(start, 10.0, len(closes), [])
        as_of = bars_a[-1].date
        metrics = metrics_on_date({"A": bars_a, "B": bars_b}, as_of)
        by_code = {m.code: m for m in metrics}
        # After the gap, B's flat ret20 can win; force the eligibility gate via mocks.
        self.assertFalse(by_code["A"].above_ma28)
        blocked = [
            type(
                "M",
                (),
                {
                    "code": "A",
                    "ret20": 50.0,
                    "close": 1.0,
                    "ma28": 12.0,
                    "above_ma28": False,
                    "rank": 1,
                },
            )(),
            type(
                "M",
                (),
                {
                    "code": "B",
                    "ret20": 1.0,
                    "close": 10.0,
                    "ma28": 9.0,
                    "above_ma28": True,
                    "rank": 2,
                },
            )(),
        ]
        self.assertIsNone(strongest_eligible(blocked))

    def test_exit_when_rank_drops_or_breaks_ma28(self) -> None:
        hold_ok = type("M", (), {"rank": 1, "above_ma28": True})()
        hold_top3 = type("M", (), {"rank": 3, "above_ma28": True})()
        hold_rank = type("M", (), {"rank": 4, "above_ma28": True})()
        hold_ma = type("M", (), {"rank": 1, "above_ma28": False})()
        self.assertFalse(should_exit_hold("X", {"X": hold_ok}))
        self.assertFalse(should_exit_hold("X", {"X": hold_top3}))
        self.assertTrue(should_exit_hold("X", {"X": hold_rank}))
        self.assertTrue(should_exit_hold("X", {"X": hold_ma}))
        self.assertTrue(should_exit_hold("X", {}))

    def test_step_buy_hold_switch(self) -> None:
        a1 = type(
            "M",
            (),
            {
                "code": "A",
                "ret20": 10.0,
                "close": 12.0,
                "ma28": 11.0,
                "above_ma28": True,
                "rank": 1,
            },
        )()
        b2 = type(
            "M",
            (),
            {
                "code": "B",
                "ret20": 5.0,
                "close": 10.0,
                "ma28": 9.0,
                "above_ma28": True,
                "rank": 2,
            },
        )()
        bought = step_rotation(None, [a1, b2])
        self.assertEqual(bought.hold, "A")
        self.assertEqual(bought.signal_by_code["A"], SIGNAL_BUY)

        held = step_rotation("A", [a1, b2])
        self.assertEqual(held.hold, "A")
        self.assertEqual(held.signal_by_code["A"], SIGNAL_HOLD)

        # Still in top 3 → keep hold even if no longer #1
        b1 = type(
            "M",
            (),
            {
                "code": "B",
                "ret20": 12.0,
                "close": 11.0,
                "ma28": 10.0,
                "above_ma28": True,
                "rank": 1,
            },
        )()
        a2 = type(
            "M",
            (),
            {
                "code": "A",
                "ret20": 3.0,
                "close": 12.0,
                "ma28": 11.0,
                "above_ma28": True,
                "rank": 2,
            },
        )()
        still = step_rotation("A", [b1, a2])
        self.assertEqual(still.hold, "A")
        self.assertEqual(still.signal_by_code["A"], SIGNAL_HOLD)

        # Drop out of top 3 → switch into new #1
        a4 = type(
            "M",
            (),
            {
                "code": "A",
                "ret20": 1.0,
                "close": 12.0,
                "ma28": 11.0,
                "above_ma28": True,
                "rank": 4,
            },
        )()
        switched = step_rotation("A", [b1, a4])
        self.assertEqual(switched.hold, "B")
        self.assertEqual(switched.signal_by_code["B"], SIGNAL_SWITCH)
        self.assertEqual(switched.signal_by_code["A"], SIGNAL_NONE)

    def test_simulate_and_apply_annotate_rows(self) -> None:
        start = date(2026, 1, 1)
        bars_a = _flat_then(start, 10.0, 40, [10 + i * 0.4 for i in range(1, 25)])
        bars_b = _flat_then(start, 10.0, 64, [])
        rows = [{"code": "A"}, {"code": "B"}]
        meta = apply_mom20_ma28(rows, {"A": bars_a, "B": bars_b}, as_of=bars_a[-1].date)
        self.assertEqual(meta["hold"], "A")
        self.assertIn(rows[0]["mom20Ma28"], {SIGNAL_BUY, SIGNAL_HOLD, SIGNAL_SWITCH})
        self.assertEqual(rows[0]["ret20_rank"], 1)
        self.assertTrue(rows[0]["above_ma28"])
        self.assertEqual(rows[1]["mom20Ma28"], SIGNAL_NONE)

        state = simulate_rotation({"A": bars_a, "B": bars_b}, as_of=bars_a[-1].date)
        self.assertEqual(state.hold, "A")


if __name__ == "__main__":
    unittest.main()
