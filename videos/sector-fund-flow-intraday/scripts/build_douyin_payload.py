#!/usr/bin/env python3
"""Build Douyin video.json from frozen sector-fund-flow data + render outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def fmt_yi(v: float) -> str:
    if abs(v) >= 100:
        return f"{v:.1f}"
    return f"{v:.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--cover-portrait", type=Path, required=True)
    parser.add_argument("--cover-landscape", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--visibility", default="public", choices=("public", "private"))
    parser.add_argument("--collection", default="资金流向")
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    trade_date = str(data["tradeDate"])
    mmdd = trade_date[5:7] + trade_date[8:10]
    sectors = data.get("sectors") or []
    outflow = [s for s in sectors if s.get("side") == "outflow"][:5]
    inflow = [s for s in sectors if s.get("side") == "inflow"][:5]
    out_names = "、".join(s["name"] for s in outflow) or "—"
    in_names = "、".join(s["name"] for s in inflow) or "—"

    frames = data.get("frames") or []
    market_exit = float(frames[-1]["marketExitYi"]) if frames else 0.0
    stance = "市场离场" if market_exit > 0 else "市场进场" if market_exit < 0 else "多空平衡"
    stance_line = f"{stance}约{fmt_yi(abs(market_exit))}亿"

    stats = data.get("marketStats") or {}
    total = float(stats.get("totalAmountYi") or 0)
    vs_prev = float(stats.get("vsPrevDayYi") or 0)
    vs_sign = "+" if vs_prev >= 0 else ""
    turnover_line = (
        f"两市成交额 {fmt_yi(total)}亿（较前日{vs_sign}{fmt_yi(vs_prev)}亿）"
        if total
        else ""
    )

    description_parts = [
        f"{trade_date} 板块资金流向全日复盘",
        f"流出TOP：{out_names}",
        f"流入TOP：{in_names}",
        stance_line,
    ]
    if turnover_line:
        description_parts.append(turnover_line)
    description_parts.append(
        str(data.get("disclaimer") or "数据来源于网络，仅供参考，不构成投资建议。")
    )

    payload = {
        "videoPath": str(args.video.resolve()),
        "coverPortraitPath": str(args.cover_portrait.resolve()),
        "coverPath": str(args.cover_landscape.resolve()),
        "title": f"{mmdd}行业资金流向全日复盘",
        "description": "\n".join(description_parts),
        "tags": ["资金流向", "A股", "板块复盘", "ETF"],
        "visibility": args.visibility,
        "collection": args.collection or None,
    }
    if not payload["collection"]:
        payload.pop("collection")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"ok": True, "output": str(args.output), "title": payload["title"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
