#!/usr/bin/env python3
"""Unit checks for Eastmoney multi-level industry dedupe."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "fetch_intraday_flow", ROOT / "fetch_intraday_flow.py"
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_stem() -> None:
    assert mod.industry_stem("银行") == "银行"
    assert mod.industry_stem("银行Ⅱ") == "银行"
    assert mod.industry_stem("国有大型银行Ⅲ") == "国有大型银行"
    assert mod.industry_stem("电子") == "电子"


def test_dedupe_keeps_base_drops_level2() -> None:
    rows = [
        ("BK1283", "银行", -5.8317),
        ("BK0475", "银行Ⅱ", -5.8317),
        ("BK1611", "国有大型银行Ⅲ", -4.3266),
        ("BK0465", "化学制药", -12.0),
    ]
    out = mod.dedupe_hierarchical_nets(rows)
    codes = [c for c, _, _ in out]
    assert codes == ["BK1283", "BK1611", "BK0465"]
    assert "BK0475" not in codes


def test_dedupe_keeps_different_nets_same_family() -> None:
    rows = [
        ("BK1033", "电池", -9.6),
        ("BK1303", "锂电池", -6.4),
    ]
    out = mod.dedupe_hierarchical_nets(rows)
    assert len(out) == 2


def test_prefer_shallower_when_both_suffixed() -> None:
    rows = [
        ("BK2", "某某Ⅱ", 1.0),
        ("BK1", "某某Ⅰ", 1.0),
    ]
    out = mod.dedupe_hierarchical_nets(rows)
    assert out[0][0] == "BK1"


if __name__ == "__main__":
    test_stem()
    test_dedupe_keeps_base_drops_level2()
    test_dedupe_keeps_different_nets_same_family()
    test_prefer_shallower_when_both_suffixed()
    print("ok")
