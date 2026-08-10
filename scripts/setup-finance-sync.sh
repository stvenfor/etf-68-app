#!/usr/bin/env bash
# Write GitHub token into Electron userData for 理财研究 cloud sync.
# Target repo is fixed in app: stvenfor/etf-68-app (data/finance/*).
set -euo pipefail

APP_SUPPORT="${HOME}/Library/Application Support/etf-68-app"
OUT="${APP_SUPPORT}/finance-sync.json"
PROXY="${FINANCE_GITHUB_PROXY:-}"

mkdir -p "${APP_SUPPORT}"

TOKEN="${1:-${GH_TOKEN:-${GITHUB_TOKEN:-}}}"
if [[ -z "${TOKEN}" ]]; then
  if command -v gh >/dev/null 2>&1 && gh auth token >/dev/null 2>&1; then
    TOKEN="$(gh auth token)"
  fi
fi

if [[ -z "${TOKEN}" ]]; then
  cat <<'EOF'
用法：
  1) 先登录：gh auth login -h github.com -p https -w
  2) 再执行：bash scripts/setup-finance-sync.sh
  或：bash scripts/setup-finance-sync.sh ghp_xxx
  或：GH_TOKEN=ghp_xxx bash scripts/setup-finance-sync.sh

Token 需对本仓库 stvenfor/etf-68-app 的 Contents 有读写权限。
EOF
  exit 1
fi

export ETF68_SYNC_OUT="$OUT"
export ETF68_SYNC_TOKEN="$TOKEN"
export ETF68_SYNC_PROXY="$PROXY"
python3 - <<'PY'
import json, os
from pathlib import Path
out = Path(os.environ["ETF68_SYNC_OUT"])
token = os.environ["ETF68_SYNC_TOKEN"].strip()
proxy = (os.environ.get("ETF68_SYNC_PROXY") or "").strip()
prev = {}
if out.exists():
    try:
        prev = json.loads(out.read_text(encoding="utf-8"))
    except Exception:
        prev = {}
if not proxy:
    proxy = str(prev.get("proxy") or "").strip()
data = {"token": token, "proxy": proxy}
out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"已写入 {out}")
print("hasToken=True；重启桌面应用后，理财研究 → 云端同步 应显示已配置。")
PY
