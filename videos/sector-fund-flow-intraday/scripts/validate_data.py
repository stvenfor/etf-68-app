#!/usr/bin/env python3
"""Validate frozen sector fund-flow JSON before rendering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=Path)
    parser.add_argument("--expect-date", default=None)
    parser.add_argument("--expect-mode", default="close", choices=("close", "latest"))
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    data = json.loads(args.json_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []

    trade_date = data.get("tradeDate")
    if args.expect_date and trade_date != args.expect_date:
        errors.append(f"tradeDate={trade_date!r} != {args.expect_date!r}")
    if data.get("snapshotMode") != args.expect_mode:
        errors.append(
            f"snapshotMode={data.get('snapshotMode')!r} != {args.expect_mode!r}"
        )
    if data.get("synthetic") is True:
        errors.append("synthetic=True (demo data not allowed for delivery)")

    frames = data.get("frames") or []
    if len(frames) < 200:
        errors.append(f"frames too few: {len(frames)}")
    last = frames[-1] if frames else {}
    if args.expect_mode == "close":
        if not str(data.get("dataCutoff") or "").endswith("T15:00:00+08:00"):
            # allow variants without seconds precision issues
            if "15:00" not in str(data.get("dataCutoff") or ""):
                errors.append(f"dataCutoff not close: {data.get('dataCutoff')!r}")
        if last.get("time") != "15:00" and last.get("t") != "15:00":
            errors.append(f"final frame time={last.get('time') or last.get('t')!r}")

    out = last.get("outflowTop") or []
    inn = last.get("inflowTop") or []
    if len(out) < args.top_n:
        errors.append(f"outflowTop size {len(out)} < {args.top_n}")
    if len(inn) < args.top_n:
        errors.append(f"inflowTop size {len(inn)} < {args.top_n}")

    # Rank / sign / sort checks
    for side, rows, want_desc in (
        ("outflowTop", out, True),
        ("inflowTop", inn, True),
    ):
        prev = None
        for i, row in enumerate(rows):
            if int(row.get("rank") or 0) != i + 1:
                errors.append(f"{side}[{i}].rank={row.get('rank')}")
            v = float(row.get("netYi") or 0)
            if v <= 0:
                errors.append(f"{side}[{i}] netYi must be >0, got {v}")
            if prev is not None and v > prev + 1e-9:
                errors.append(f"{side} not sorted desc at {i}: {v} > {prev}")
            prev = v
            if not row.get("name") or not row.get("code"):
                errors.append(f"{side}[{i}] missing name/code")

    out_sum = sum(float(r["netYi"]) for r in out)
    in_sum = sum(float(r["netYi"]) for r in inn)
    exit_yi = float(last.get("marketExitYi") or 0)
    expected_exit = round(out_sum - in_sum, 4)
    if abs(exit_yi - expected_exit) > 0.05:
        errors.append(
            f"marketExitYi={exit_yi} != out-in={expected_exit} "
            f"(out={out_sum:.4f} in={in_sum:.4f})"
        )

    # Sector cast matches final frame
    sectors = data.get("sectors") or []
    by_code = {str(s.get("code")): s for s in sectors}
    for row in out:
        s = by_code.get(str(row["code"]))
        if not s or s.get("side") != "outflow":
            errors.append(f"sector cast missing outflow {row.get('code')}")
        elif abs(float(s.get("finalNetYi") or 0) - float(row["netYi"])) > 0.01:
            errors.append(f"sector finalNetYi mismatch outflow {row.get('name')}")
    for row in inn:
        s = by_code.get(str(row["code"]))
        if not s or s.get("side") != "inflow":
            errors.append(f"sector cast missing inflow {row.get('code')}")
        elif abs(float(s.get("finalNetYi") or 0) - float(row["netYi"])) > 0.01:
            errors.append(f"sector finalNetYi mismatch inflow {row.get('name')}")

    stats = data.get("marketStats") or {}
    total = float(stats.get("totalAmountYi") or 0)
    if total <= 0:
        warnings.append("marketStats.totalAmountYi missing/zero")
    else:
        # Sanity: A-share daily turnover usually thousands of 亿
        if total < 2000 or total > 80000:
            warnings.append(f"turnover unusual: {total} 亿")

    # Monotonic-ish: last frame magnitudes shouldn't all be zero
    if out_sum < 1 and in_sum < 1:
        errors.append("final TOP nets near zero — likely bad freeze")

    report = {
        "status": "ok" if not errors else "fail",
        "path": str(args.json_path),
        "tradeDate": trade_date,
        "snapshotMode": data.get("snapshotMode"),
        "dataCutoff": data.get("dataCutoff"),
        "fetchedAt": data.get("fetchedAt"),
        "frameCount": len(frames),
        "finalOutflowTop5": [
            {"rank": r["rank"], "name": r["name"], "netYi": r["netYi"]} for r in out[:5]
        ],
        "finalInflowTop5": [
            {"rank": r["rank"], "name": r["name"], "netYi": r["netYi"]} for r in inn[:5]
        ],
        "marketExitYi": exit_yi,
        "marketStats": stats,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
