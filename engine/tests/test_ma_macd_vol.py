"""Tests for MA + MACD + volume authenticity advice."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from src.ma_macd_vol import (  # noqa: E402
    ADVICE_BUY,
    ADVICE_DIR_MIXED,
    ADVICE_HOLD,
    ADVICE_VOL_DOUBT,
    ADVICE_WAIT_MACD,
    ADVICE_WAIT_VOL,
    compute_ma_macd_vol_fields,
    decide_ma_macd_vol,
)


class MaMacdVolTests(unittest.TestCase):
    def test_buy_when_all_three_align(self) -> None:
        self.assertEqual(
            ADVICE_BUY,
            decide_ma_macd_vol(
                daily_trend="多头",
                macd_state="金叉",
                volume_price_bullish=True,
                volume_price_bearish=False,
            ),
        )
        self.assertEqual(
            ADVICE_BUY,
            decide_ma_macd_vol(
                daily_trend="多头",
                macd_state="零轴上多头",
                volume_price_bullish=True,
            ),
        )

    def test_wait_vol_when_macd_ok_volume_neutral(self) -> None:
        self.assertEqual(
            ADVICE_WAIT_VOL,
            decide_ma_macd_vol(
                daily_trend="多头",
                macd_state="金叉",
                volume_price_bullish=False,
                volume_price_bearish=False,
            ),
        )

    def test_vol_doubt_when_volume_bearish(self) -> None:
        self.assertEqual(
            ADVICE_VOL_DOUBT,
            decide_ma_macd_vol(
                daily_trend="多头",
                macd_state="金叉",
                volume_price_bullish=False,
                volume_price_bearish=True,
            ),
        )

    def test_wait_macd_when_no_buy_point(self) -> None:
        for state in ("死叉", "零轴下空头", "收敛"):
            self.assertEqual(
                ADVICE_WAIT_MACD,
                decide_ma_macd_vol(daily_trend="多头", macd_state=state),
                msg=state,
            )

    def test_direction_gates(self) -> None:
        self.assertEqual(
            ADVICE_DIR_MIXED,
            decide_ma_macd_vol(daily_trend="震荡", macd_state="金叉", volume_price_bullish=True),
        )
        self.assertEqual(
            ADVICE_HOLD,
            decide_ma_macd_vol(daily_trend="空头", macd_state="金叉", volume_price_bullish=True),
        )

    def test_compute_fields_detail(self) -> None:
        fields = compute_ma_macd_vol_fields(
            daily_trend="多头",
            macd_state="金叉",
            volume_price_label="量升价增",
            volume_price_bullish=True,
        )
        self.assertEqual(ADVICE_BUY, fields["maMacdVol"])
        self.assertEqual("MA多头·MACD金叉·量升价增", fields["maMacdVolDetail"])


if __name__ == "__main__":
    unittest.main()
