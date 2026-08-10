"""Multi-strategy persistence under data/rotation/strategies.json."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from .config import (
    XIAOXIN_PRESET_ID,
    ZHIBEI_CLONE_ID,
    builtin_strategies,
    strategy_record,
    validate_config,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def default_strategies_path() -> Path:
    env = os.environ.get("ETF68_ROTATION_DIR")
    if env:
        return Path(env) / "strategies.json"
    return REPO_ROOT / "data" / "rotation" / "strategies.json"


def _empty_doc() -> dict[str, Any]:
    builtins = builtin_strategies()
    return {
        "version": 1,
        "active_id": builtins[0]["id"],
        "items": builtins,
    }


def load_doc(path: Path | None = None) -> dict[str, Any]:
    p = path or default_strategies_path()
    if not p.exists():
        doc = _empty_doc()
        save_doc(doc, p)
        return doc
    raw = json.loads(p.read_text(encoding="utf-8"))
    items = list(raw.get("items") or [])
    by_id = {str(it.get("id")): it for it in items if it.get("id")}
    # ensure builtin presets always present / refreshed
    for preset in reversed(builtin_strategies()):
        if preset["id"] not in by_id:
            items.insert(0, preset)
            by_id[preset["id"]] = preset
        else:
            existing = by_id[preset["id"]]
            existing["readonly"] = True
            existing["approx"] = bool(preset.get("approx"))
            existing["name"] = preset.get("name") or existing.get("name")
            # Refresh builtin configs so official clone updates ship to users.
            existing["config"] = preset["config"]
            existing["updated_at"] = preset.get("updated_at") or existing.get("updated_at")
    # stable order: builtins first
    builtin_ids = [p["id"] for p in builtin_strategies()]
    rest = [it for it in items if it.get("id") not in set(builtin_ids)]
    ordered = [by_id[i] for i in builtin_ids if i in by_id] + rest
    active = raw.get("active_id") or ZHIBEI_CLONE_ID or XIAOXIN_PRESET_ID
    if active not in {it.get("id") for it in ordered}:
        active = ZHIBEI_CLONE_ID if ZHIBEI_CLONE_ID in by_id else XIAOXIN_PRESET_ID
    return {"version": 1, "active_id": active, "items": ordered}


def save_doc(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = path or default_strategies_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def list_strategies(path: Path | None = None) -> dict[str, Any]:
    return load_doc(path)


def get_strategy(strategy_id: str, path: Path | None = None) -> dict[str, Any] | None:
    doc = load_doc(path)
    for item in doc["items"]:
        if item.get("id") == strategy_id:
            return item
    return None


def set_active(strategy_id: str, path: Path | None = None) -> dict[str, Any]:
    doc = load_doc(path)
    ids = {it["id"] for it in doc["items"]}
    if strategy_id not in ids:
        raise KeyError(f"strategy_not_found:{strategy_id}")
    doc["active_id"] = strategy_id
    save_doc(doc, path)
    return doc


def save_strategy(
    *,
    strategy_id: str | None,
    name: str,
    config: dict[str, Any],
    make_active: bool = True,
    path: Path | None = None,
) -> dict[str, Any]:
    doc = load_doc(path)
    cfg = validate_config(config)
    sid = strategy_id or f"custom-{uuid.uuid4().hex[:10]}"
    existing = None
    for item in doc["items"]:
        if item.get("id") == sid:
            existing = item
            break
    if existing and existing.get("readonly"):
        # allow updating active selection / cloning path only via new id
        if strategy_id == existing["id"]:
            # permit name-locked config overwrite? plan: readonly preset not overwritten
            raise PermissionError(f"strategy_readonly:{sid}")
    record = strategy_record(
        strategy_id=sid,
        name=name or sid,
        config=cfg,
        readonly=False,
        approx=bool(cfg.get("approx_label")),
    )
    if existing:
        existing.update(record)
    else:
        doc["items"].append(record)
    if make_active:
        doc["active_id"] = sid
    save_doc(doc, path)
    return record


def delete_strategy(strategy_id: str, path: Path | None = None) -> dict[str, Any]:
    doc = load_doc(path)
    item = next((it for it in doc["items"] if it.get("id") == strategy_id), None)
    if not item:
        raise KeyError(f"strategy_not_found:{strategy_id}")
    if item.get("readonly"):
        raise PermissionError(f"strategy_readonly:{strategy_id}")
    doc["items"] = [it for it in doc["items"] if it.get("id") != strategy_id]
    if doc.get("active_id") == strategy_id:
        ids = {it.get("id") for it in doc["items"]}
        doc["active_id"] = (
            ZHIBEI_CLONE_ID
            if ZHIBEI_CLONE_ID in ids
            else (XIAOXIN_PRESET_ID if XIAOXIN_PRESET_ID in ids else doc["items"][0]["id"])
        )
    save_doc(doc, path)
    return doc


def duplicate_strategy(
    strategy_id: str, *, new_name: str | None = None, path: Path | None = None
) -> dict[str, Any]:
    src = get_strategy(strategy_id, path)
    if not src:
        raise KeyError(f"strategy_not_found:{strategy_id}")
    return save_strategy(
        strategy_id=None,
        name=new_name or f"{src.get('name', strategy_id)} 副本",
        config=src.get("config") or {},
        make_active=True,
        path=path,
    )
