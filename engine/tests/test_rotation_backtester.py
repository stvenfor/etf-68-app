from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import date, timedelta

from src.rotation.backtester import run_backtest
from src.rotation.config import default_config, validate_config


@dataclass(frozen=True)
class Bar:
    date: date
    open: float
    close: float
    high: float
    low: float
    volume: float = 1.0
    turnover_cny: float = 1.0
    source: str = "test"
    timestamp: object = None


def _series(start: date, values: list[float]) -> list[Bar]:
    out: list[Bar] = []
    d = start
    for v in values:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append(Bar(date=d, open=v, close=v, high=v * 1.01, low=v * 0.99))
        d += timedelta(days=1)
    return out


class BacktesterTests(unittest.TestCase):
    def test_picks_strongest_simple(self) -> None:
        start = date(2024, 1, 2)
        weak = _series(start, [100.0] * 40)
        strong = _series(start, [100.0 + i for i in range(40)])
        cfg = default_config()
        cfg["etf_pool"] = ["111111", "222222"]
        cfg["etf_names"] = {"111111": "弱", "222222": "强"}
        cfg["momentum"]["method"] = "simple"
        cfg["momentum"]["window"] = 10
        cfg["holding"]["min_hold_days"] = 1
        cfg["costs"]["commission_rate"] = 0.0
        cfg["costs"]["slippage_rate"] = 0.0
        cfg["backtest"]["start_date"] = None
        cfg["backtest"]["end_date"] = None
        cfg = validate_config(cfg)
        result = run_backtest(
            config=cfg,
            bars_by_code={"111111": weak, "222222": strong},
        )
        self.assertEqual(result.hold_code, "222222")
        self.assertGreater(result.day_index, 10)
        self.assertTrue(result.rankings)
        self.assertEqual(result.rankings[0]["code"], "222222")

    def test_stop_loss_triggers(self) -> None:
        start = date(2024, 1, 2)
        # rises then crashes
        vals = [100.0 + i for i in range(25)] + [80.0] * 20
        other = [100.0] * len(vals)
        bars_a = _series(start, vals)
        bars_b = _series(start, other)
        cfg = default_config()
        cfg["etf_pool"] = ["AAAAAA", "BBBBBB"]
        cfg["etf_names"] = {"AAAAAA": "A", "BBBBBB": "B"}
        cfg["momentum"]["method"] = "simple"
        cfg["momentum"]["window"] = 5
        cfg["holding"]["min_hold_days"] = 1
        cfg["stop_loss"]["enabled"] = True
        cfg["stop_loss"]["pct_enabled"] = True
        cfg["stop_loss"]["pct_threshold"] = 0.1
        cfg["costs"]["commission_rate"] = 0.0
        cfg["costs"]["slippage_rate"] = 0.0
        cfg["backtest"]["start_date"] = None
        cfg["backtest"]["end_date"] = None
        result = run_backtest(
            config=cfg,
            bars_by_code={"AAAAAA": bars_a, "BBBBBB": bars_b},
        )
        actions = [t["action"] for t in result.trades]
        self.assertIn("止损", actions)

    def test_min_hold_blocks_switch(self) -> None:
        start = date(2024, 1, 2)
        # A leads first half, B leads second half
        a_vals = [100 + i for i in range(30)] + [130 - 0.2 * i for i in range(30)]
        b_vals = [100 + 0.1 * i for i in range(30)] + [103 + i for i in range(30)]
        cfg = default_config()
        cfg["etf_pool"] = ["AAAAAA", "BBBBBB"]
        cfg["etf_names"] = {"AAAAAA": "A", "BBBBBB": "B"}
        cfg["momentum"]["method"] = "simple"
        cfg["momentum"]["window"] = 5
        cfg["holding"]["min_hold_days"] = 60
        cfg["costs"]["commission_rate"] = 0.0
        cfg["costs"]["slippage_rate"] = 0.0
        cfg["backtest"]["start_date"] = None
        cfg["backtest"]["end_date"] = None
        result = run_backtest(
            config=cfg,
            bars_by_code={
                "AAAAAA": _series(start, a_vals),
                "BBBBBB": _series(start, b_vals),
            },
        )
        switch_count = sum(1 for t in result.trades if t["action"] == "换仓")
        self.assertEqual(switch_count, 0)


if __name__ == "__main__":
    unittest.main()
