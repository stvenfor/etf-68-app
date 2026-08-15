"""Mirror OneChart public macro-timing JSON into data/out/macro-timing/."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
MACRO_BASE = os.environ.get("ETF68_ONECHART_MACRO_BASE", "https://onechart.top/macro").rstrip("/")
DISPERSION_BASE = f"{MACRO_BASE}/dispersion"
REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_SCHEMA = "onechart_macro_daily_bundle_v3"
UA = "etf-68-app/macro-timing"


def default_cache_dir() -> Path:
    env = os.environ.get("ETF68_OUT_DIR")
    root = Path(env) if env else (REPO_ROOT / "data" / "out")
    return root / "macro-timing"


def _now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _fetch_bytes(url: str, *, timeout: float = 90.0) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json,*/*"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _fetch_json(url: str, *, timeout: float = 90.0) -> Any:
    return json.loads(_fetch_bytes(url, timeout=timeout).decode("utf-8"))


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pick_block(state: dict[str, Any], key: str = "current") -> dict[str, Any] | None:
    block = state.get(key)
    return block if isinstance(block, dict) else None


def load_bundle(cache_dir: Path | None = None) -> dict[str, Any]:
    """Load cached macro timing payload for the desktop UI."""
    root = cache_dir or default_cache_dir()
    meta = _read_json(root / "meta.json") or {}
    state = _read_json(root / "state.json")
    series = _read_json(root / "series.json")
    dispersion_meta = _read_json(root / "dispersion" / "meta.json") or {}

    if not state or not series:
        return {
            "ok": False,
            "cache": False,
            "error": meta.get("error") or "macro_timing_cache_missing",
            "fetchedAt": meta.get("fetchedAt"),
            "meta": meta,
        }

    block = _pick_block(state, "current") or _pick_block(state, "last_good") or {}
    summary = (block.get("summary") or {}) if isinstance(block, dict) else {}
    crowding = summary.get("crowding") if isinstance(summary, dict) else None

    return {
        "ok": True,
        "cache": True,
        "fetchedAt": meta.get("fetchedAt"),
        "asOf": block.get("as_of_date") or series.get("as_of_date"),
        "source": MACRO_BASE,
        "releaseStatus": state.get("release_status"),
        "schemaVersion": state.get("schema_version"),
        "crowding": crowding,
        "series": series,
        "dispersion": {
            "ok": bool(dispersion_meta.get("ok")),
            "state": dispersion_meta.get("state"),
            "message": dispersion_meta.get("message"),
            "asOf": dispersion_meta.get("asOf"),
            "buildId": dispersion_meta.get("buildId"),
            "bundleId": dispersion_meta.get("bundleId"),
            "calendarLen": len(dispersion_meta.get("calendar") or []),
            "hasLatest180": bool(dispersion_meta.get("hasLatest180")),
        },
        "meta": meta,
    }


def _cache_dispersion_build(
    *,
    root: Path,
    ref: dict[str, Any],
    slot: str,
) -> dict[str, Any]:
    """Download dispersion manifest + latest180 for a state.dispersion pointer."""
    build_id = str(ref.get("build_id") or "")
    manifest_path = str(ref.get("manifest_path") or "")
    if not build_id or not manifest_path:
        raise ValueError("dispersion_ref_incomplete")

    # OneChart DispersionDataStore base is macro/dispersion/
    manifest_url = f"{DISPERSION_BASE}/{manifest_path.lstrip('/')}"
    build_dir = root / "dispersion" / "builds" / build_id
    build_dir.mkdir(parents=True, exist_ok=True)

    raw_manifest = _fetch_bytes(manifest_url, timeout=60.0)
    expected = str(ref.get("manifest_sha256") or "")
    if expected and _sha256_hex(raw_manifest) != expected:
        raise ValueError("dispersion_manifest_sha_mismatch")
    manifest = json.loads(raw_manifest.decode("utf-8"))
    (build_dir / "manifest.json").write_bytes(raw_manifest)

    latest = None
    for file_meta in manifest.get("files") or []:
        if file_meta.get("kind") == "latest180":
            latest = file_meta
            break
    has_latest = False
    if latest and latest.get("path"):
        rel = str(latest["path"]).lstrip("/")
        file_url = f"{DISPERSION_BASE}/builds/{build_id}/{rel}"
        raw_file = _fetch_bytes(file_url, timeout=180.0)
        expected_file = str(latest.get("sha256") or "")
        if expected_file and _sha256_hex(raw_file) != expected_file:
            raise ValueError("dispersion_latest180_sha_mismatch")
        out_path = build_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(raw_file)
        has_latest = True

    calendar = list(manifest.get("date_index") or [])
    return {
        "ok": True,
        "state": slot,
        "message": "" if slot == "current" else "当前构建不可用，使用最近有效构建。",
        "asOf": ref.get("as_of") or manifest.get("as_of"),
        "buildId": build_id,
        "bundleId": ref.get("bundle_id") or manifest.get("bundle_id"),
        "calendar": calendar,
        "hasLatest180": has_latest,
        "manifestPath": manifest_path,
    }


def refresh_bundle(
    *,
    cache_dir: Path | None = None,
    include_dispersion: bool = True,
) -> dict[str, Any]:
    """Fetch OneChart macro state + series (+ dispersion latest180) into cache."""
    root = cache_dir or default_cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "ok": False,
        "fetchedAt": _now_iso(),
        "source": MACRO_BASE,
    }

    try:
        state = _fetch_json(f"{MACRO_BASE}/state.json", timeout=45.0)
        if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA:
            raise ValueError(f"unexpected_state_schema:{state.get('schema_version')!r}")

        block = _pick_block(state, "current") or _pick_block(state, "last_good")
        if not block:
            raise ValueError("state_missing_current_and_last_good")

        series_rel = ((block.get("manifest") or {}) if isinstance(block, dict) else {}).get(
            "series_path"
        )
        if not series_rel:
            raise ValueError("series_path_missing")
        series = _fetch_json(f"{MACRO_BASE}/{str(series_rel).lstrip('/')}", timeout=120.0)
        if not isinstance(series, dict) or not series.get("dates"):
            raise ValueError("series_invalid")

        _write_json(root / "state.json", state)
        _write_json(root / "series.json", series)

        dispersion_meta: dict[str, Any] = {
            "ok": False,
            "state": "unavailable",
            "message": "离散度贡献暂不可用，高切低指标保持正常。",
            "calendar": [],
            "hasLatest180": False,
        }
        if include_dispersion:
            try:
                chosen_slot = "current"
                ref = (block.get("dispersion") if isinstance(block, dict) else None) or {}
                try:
                    dispersion_meta = _cache_dispersion_build(
                        root=root, ref=ref, slot="current"
                    )
                except Exception:
                    last = _pick_block(state, "last_good") or {}
                    ref = (last.get("dispersion") if isinstance(last, dict) else None) or {}
                    dispersion_meta = _cache_dispersion_build(
                        root=root, ref=ref, slot="last_good"
                    )
                    chosen_slot = "last_good"
                dispersion_meta["chosenSlot"] = chosen_slot
            except Exception as exc:  # noqa: BLE001 — best-effort secondary module
                dispersion_meta = {
                    "ok": False,
                    "state": "unavailable",
                    "message": "离散度贡献暂不可用，高切低指标保持正常。",
                    "error": str(exc),
                    "calendar": [],
                    "hasLatest180": False,
                }
        _write_json(root / "dispersion" / "meta.json", dispersion_meta)

        meta.update(
            {
                "ok": True,
                "asOf": block.get("as_of_date") if isinstance(block, dict) else None,
                "batchId": block.get("batch_id") if isinstance(block, dict) else None,
                "seriesPath": series_rel,
                "dispersionOk": bool(dispersion_meta.get("ok")),
            }
        )
        _write_json(root / "meta.json", meta)
        return load_bundle(root)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError) as exc:
        meta["error"] = str(exc)
        _write_json(root / "meta.json", meta)
        cached = load_bundle(root)
        if cached.get("ok"):
            cached = dict(cached)
            cached["fetchError"] = str(exc)
            return cached
        return {
            "ok": False,
            "cache": False,
            "error": str(exc),
            "fetchedAt": meta["fetchedAt"],
            "meta": meta,
        }


def _load_dispersion_block(root: Path, build_id: str, rel_path: str) -> dict[str, Any] | None:
    path = root / "dispersion" / "builds" / build_id / rel_path
    data = _read_json(path)
    return data if isinstance(data, dict) else None


def _ensure_dispersion_file(
    root: Path,
    build_id: str,
    file_meta: dict[str, Any],
) -> dict[str, Any]:
    rel = str(file_meta.get("path") or "").lstrip("/")
    if not rel:
        raise ValueError("dispersion_file_path_missing")
    existing = _load_dispersion_block(root, build_id, rel)
    if existing and existing.get("rows"):
        return existing

    url = f"{DISPERSION_BASE}/builds/{build_id}/{rel}"
    raw = _fetch_bytes(url, timeout=180.0)
    expected = str(file_meta.get("sha256") or "")
    if expected and _sha256_hex(raw) != expected:
        raise ValueError(f"dispersion_file_sha_mismatch:{rel}")
    out = root / "dispersion" / "builds" / build_id / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("dispersion_file_invalid")
    return data


def load_dispersion_window(
    *,
    end_date: str | None = None,
    cache_dir: Path | None = None,
    fetch_missing: bool = True,
) -> dict[str, Any]:
    """Return a fixed 91-row (90-day window + end) slice for contribution charts."""
    root = cache_dir or default_cache_dir()
    dmeta = _read_json(root / "dispersion" / "meta.json") or {}
    if not dmeta.get("ok") or not dmeta.get("buildId"):
        return {
            "ok": False,
            "error": dmeta.get("message") or "离散度贡献暂不可用，高切低指标保持正常。",
            "state": dmeta.get("state") or "unavailable",
        }

    build_id = str(dmeta["buildId"])
    manifest = _read_json(root / "dispersion" / "builds" / build_id / "manifest.json")
    if not isinstance(manifest, dict):
        return {"ok": False, "error": "dispersion_manifest_missing", "state": "unavailable"}

    calendar: list[str] = list(dmeta.get("calendar") or manifest.get("date_index") or [])
    if not calendar:
        return {"ok": False, "error": "dispersion_calendar_empty", "state": "unavailable"}

    if end_date and end_date in calendar:
        end_index = calendar.index(end_date)
    else:
        end_index = len(calendar) - 1
    if end_index < 90:
        return {"ok": False, "error": "window_before_history", "state": "unavailable"}

    start_index = end_index - 90
    needed = calendar[start_index : end_index + 1]
    files = list(manifest.get("files") or [])

    def file_for(day: str) -> dict[str, Any] | None:
        for f in files:
            if f.get("kind") == "year" and f.get("display_start") <= day <= f.get("display_end"):
                return f
        for f in files:
            if f.get("kind") == "latest180" and f.get("display_start") <= day <= f.get("display_end"):
                return f
        return None

    row_map: dict[str, dict[str, Any]] = {}
    # Prefer latest180 first (covers recent window).
    for f in files:
        if f.get("kind") == "latest180":
            try:
                block = (
                    _ensure_dispersion_file(root, build_id, f)
                    if fetch_missing
                    else _load_dispersion_block(root, build_id, str(f.get("path") or ""))
                )
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": str(exc), "state": "unavailable"}
            if block:
                for row in block.get("rows") or []:
                    if isinstance(row, dict) and row.get("date"):
                        row_map[str(row["date"])] = row
            break

    missing = [d for d in needed if d not in row_map]
    if missing:
        touched: set[str] = set()
        for day in missing:
            f = file_for(day)
            if not f:
                continue
            key = str(f.get("path"))
            if key in touched:
                continue
            touched.add(key)
            try:
                block = (
                    _ensure_dispersion_file(root, build_id, f)
                    if fetch_missing
                    else _load_dispersion_block(root, build_id, str(f.get("path") or ""))
                )
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": str(exc), "state": "unavailable"}
            if block:
                for row in block.get("rows") or []:
                    if isinstance(row, dict) and row.get("date"):
                        row_map[str(row["date"])] = row

    rows = []
    for day in needed:
        row = row_map.get(day)
        if not row:
            return {
                "ok": False,
                "error": f"dispersion_row_missing:{day}",
                "state": "unavailable",
            }
        rows.append(row)

    return {
        "ok": True,
        "state": dmeta.get("state") or "current",
        "message": dmeta.get("message") or "",
        "asOf": dmeta.get("asOf"),
        "buildId": build_id,
        "endDate": calendar[end_index],
        "endIndex": end_index,
        "calendar": calendar,
        "windowStart": needed[0],
        "windowEnd": needed[-1],
        "rows": rows,
    }
