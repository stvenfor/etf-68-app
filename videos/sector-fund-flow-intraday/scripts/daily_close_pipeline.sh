#!/usr/bin/env bash
# 交易日盘后：拉全日资金流向 → 渲染 → 封面 → 抖音发布
# 用法：
#   ./scripts/daily_close_pipeline.sh
#   ./scripts/daily_close_pipeline.sh --date 2026-08-14
#   ./scripts/daily_close_pipeline.sh --skip-publish
#   VISIBILITY=private ./scripts/daily_close_pipeline.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
LOG_DIR="${ETF68_FUND_FLOW_LOG_DIR:-$HOME/Library/Logs/etf68-sector-fund-flow}"
DOUYIN_DIR="${ETF68_DOUYIN_DIR:-/tmp/etf68-douyin}"
PUBLISH_SCRIPT="${ETF68_DOUYIN_PUBLISH:-$HOME/.cursor/skills/douyin-image-publish/scripts/publish-video.mjs}"
VISIBILITY="${VISIBILITY:-public}"
COLLECTION="${COLLECTION:-资金流向}"
PYTHON="${PYTHON:-python3.12}"
SKIP_PUBLISH=0
FORCE=0
TRADE_DATE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date) TRADE_DATE="$2"; shift 2 ;;
    --skip-publish) SKIP_PUBLISH=1; shift ;;
    --force) FORCE=1; shift ;;
    --private) VISIBILITY=private; shift ;;
    --public) VISIBILITY=public; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$LOG_DIR" "$DOUYIN_DIR/covers" "$ROOT/out"
export TZ=Asia/Shanghai
# 清代理，避免东财/抖音被拦
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy || true
export NO_PROXY='*'
export no_proxy='*'

if [[ -z "$TRADE_DATE" ]]; then
  TRADE_DATE="$(date +%F)"
fi
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/pipeline-${TRADE_DATE}-${STAMP}.log"
DONE_MARK="$LOG_DIR/done-${TRADE_DATE}.ok"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "==== sector-fund-flow daily pipeline ===="
echo "trade_date=$TRADE_DATE visibility=$VISIBILITY skip_publish=$SKIP_PUBLISH"
echo "root=$ROOT log=$LOG_FILE"

cd "$ROOT"

if [[ "$FORCE" -ne 1 ]]; then
  if ! "$PYTHON" scripts/is_trading_day.py --date "$TRADE_DATE"; then
    echo "SKIP: $TRADE_DATE 非交易日"
    exit 0
  fi
fi

if [[ -f "$DONE_MARK" && "$FORCE" -ne 1 ]]; then
  echo "SKIP: 已存在完成标记 $DONE_MARK（加 --force 可重跑）"
  exit 0
fi

DATA_JSON="src/data/sector-fund-flow-${TRADE_DATE}.json"
LATEST_JSON="src/data/sector-fund-flow-latest.json"

# ---- 1. 拉数（盘后数据偶发延迟，轻量重试）----
FETCH_OK=0
for attempt in 1 2 3 4 5 6; do
  echo "fetch attempt $attempt/6 ..."
  if "$PYTHON" scripts/fetch_intraday_flow.py \
      --trade-date "$TRADE_DATE" \
      --snapshot-mode close \
      --output "$DATA_JSON"; then
    if "$PYTHON" scripts/validate_data.py \
        "$DATA_JSON" \
        --expect-date "$TRADE_DATE" \
        --expect-mode close; then
      FETCH_OK=1
      break
    fi
  fi
  echo "WARN: fetch/validate failed; sleep 90s"
  sleep 90
done
if [[ "$FETCH_OK" -ne 1 ]]; then
  echo "ERROR: 无法取得 $TRADE_DATE close 资金流向数据" >&2
  exit 1
fi

# 固定 latest 入口，避免日更改 Root.tsx
cp -f "$DATA_JSON" "$LATEST_JSON"
# 兼容旧 Root 若仍指向某日文件：同步改 import（幂等）
if grep -q "sector-fund-flow-.*\\.json" src/Root.tsx; then
  perl -i -pe "s#import raw from './data/sector-fund-flow-[^']+\\.json';#import raw from './data/sector-fund-flow-latest.json';#" src/Root.tsx
fi

# ---- 2. 渲染 + 校验 + 封面 ----
if [[ ! -d node_modules ]]; then
  npm install
fi
npm run render
npm run validate
npm run cover

MMDD="${TRADE_DATE:5:2}${TRADE_DATE:8:2}"
VIDEO_OUT="$ROOT/out/sector-fund-flow.mp4"
COVER_P="$ROOT/out/cover-竖3x4.jpg"
COVER_L="$ROOT/out/cover-横4x3.jpg"
COVER_9="$ROOT/out/cover.jpg"

for f in "$VIDEO_OUT" "$COVER_P" "$COVER_L" "$COVER_9"; do
  [[ -f "$f" ]] || { echo "ERROR: missing $f" >&2; exit 1; }
done

# 桌面副本（便于人工抽查）
DESK="$HOME/Desktop"
cp -f "$VIDEO_OUT" "$DESK/板块资金流向-${TRADE_DATE}.mp4"
cp -f "$COVER_9" "$DESK/板块资金流向-${TRADE_DATE}-封面.jpg"
cp -f "$COVER_P" "$DESK/板块资金流向-${TRADE_DATE}-封面-竖3x4.jpg"
cp -f "$COVER_L" "$DESK/板块资金流向-${TRADE_DATE}-封面-横4x3.jpg"

# 发布用封面拷到 ASCII 路径（Playwright 更稳）
PORT_COPY="$DOUYIN_DIR/covers/port-${MMDD}.jpg"
LAND_COPY="$DOUYIN_DIR/covers/land-${MMDD}.jpg"
cp -f "$COVER_P" "$PORT_COPY"
cp -f "$COVER_L" "$LAND_COPY"

PAYLOAD="$DOUYIN_DIR/video-fundflow-${MMDD}.json"
"$PYTHON" scripts/build_douyin_payload.py \
  --data "$DATA_JSON" \
  --video "$VIDEO_OUT" \
  --cover-portrait "$PORT_COPY" \
  --cover-landscape "$LAND_COPY" \
  --output "$PAYLOAD" \
  --visibility "$VISIBILITY" \
  --collection "$COLLECTION"

if [[ "$SKIP_PUBLISH" -eq 1 ]]; then
  echo "SKIP publish (--skip-publish). payload=$PAYLOAD"
  echo "$TRADE_DATE render-only $(date -Iseconds)" > "$DONE_MARK"
  exit 0
fi

if [[ ! -f "$PUBLISH_SCRIPT" ]]; then
  echo "ERROR: 找不到抖音发布脚本: $PUBLISH_SCRIPT" >&2
  exit 1
fi

# ---- 3. 解锁 profile + 发布 ----
pkill -f 'user-data-dir=.*/.douyin-playwright/profile' 2>/dev/null || true
rm -f "$HOME/.douyin-playwright/profile/SingletonLock" \
      "$HOME/.douyin-playwright/profile/SingletonCookie" \
      "$HOME/.douyin-playwright/profile/SingletonSocket" || true
sleep 1

PUBLISH_LOG="$DOUYIN_DIR/publish-${MMDD}.log"
echo "publish via $PUBLISH_SCRIPT ..."
(
  cd "$(dirname "$PUBLISH_SCRIPT")"
  node "$(basename "$PUBLISH_SCRIPT")" "$PAYLOAD"
) 2>&1 | tee "$PUBLISH_LOG"

if ! grep -qE '视频已提交发布|发布成功' "$PUBLISH_LOG"; then
  echo "ERROR: 抖音发布未确认成功，见 $PUBLISH_LOG" >&2
  exit 1
fi

echo "$TRADE_DATE published $(date -Iseconds)" > "$DONE_MARK"
echo "DONE ok trade_date=$TRADE_DATE"
echo "repo hint: $REPO"
exit 0
