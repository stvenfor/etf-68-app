#!/usr/bin/env bash
# 理财每日新知：拉东财栏目摘要 → data/finance/data.json
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE="$REPO/engine"
LOG_DIR="${ETF68_FINANCE_NEWS_LOG_DIR:-$HOME/Library/Logs/etf68-finance-news}"
PYTHON="${PYTHON:-python3.12}"
STAMP="$(date +%Y%m%d-%H%M%S)"
TODAY="$(date +%F)"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/pipeline-${TODAY}-${STAMP}.log"

exec > >(tee -a "$LOG_FILE") 2>&1

unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy || true
export NO_PROXY='*'
export no_proxy='*'
export TZ=Asia/Shanghai

echo "==== finance-news daily ===="
echo "date=$TODAY repo=$REPO"

# 周末跳过（调休仍跑；失败由拉数结果体现）
dow="$(date +%u)"
if [[ "$dow" -ge 6 && "${FORCE:-0}" != "1" ]]; then
  echo "SKIP weekend"
  exit 0
fi

cd "$ENGINE"
"$PYTHON" cli_app.py finance-news
echo "DONE $(date -Iseconds)"
exit 0
