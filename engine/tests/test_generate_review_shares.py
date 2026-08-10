"""Chunked SZSE share collection helpers."""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from generate_review import SZSE_SHARE_CHUNK_TRADING_DAYS, _szse_date_chunks  # noqa: E402


class SzseShareChunkTests(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual([], _szse_date_chunks([]))

    def test_single_day(self) -> None:
        d = date(2026, 8, 4)
        self.assertEqual([(d, d)], _szse_date_chunks([d]))

    def test_chunks_cover_full_range_without_gaps(self) -> None:
        days = [date(2026, 1, 1) + timedelta(days=i) for i in range(37)]
        chunks = _szse_date_chunks(days)
        self.assertEqual(3, len(chunks))
        self.assertEqual(SZSE_SHARE_CHUNK_TRADING_DAYS, 15)
        flat: list[date] = []
        for start, end in chunks:
            idx_start = days.index(start)
            idx_end = days.index(end)
            flat.extend(days[idx_start : idx_end + 1])
        self.assertEqual(days, flat)
        self.assertEqual(days[0], chunks[0][0])
        self.assertEqual(days[-1], chunks[-1][1])


if __name__ == "__main__":
    unittest.main()
