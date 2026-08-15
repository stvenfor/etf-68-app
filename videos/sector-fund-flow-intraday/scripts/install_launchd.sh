#!/usr/bin/env bash
# 安装 / 卸载 macOS launchd：交易日 15:30 自动跑资金流向成片+抖音发布
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.etf68.sector-fund-flow-daily"
TEMPLATE="$ROOT/launchd/${LABEL}.plist.template"
BOOT_TEMPLATE="$ROOT/launchd/launchd-boot.sh.template"
DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
APP_SUPPORT="$HOME/Library/Application Support/etf68-sector-fund-flow"
BOOT_SH="$APP_SUPPORT/launchd-boot.sh"
PIPELINE="$ROOT/scripts/daily_close_pipeline.sh"
LOG_DIR="$HOME/Library/Logs/etf68-sector-fund-flow"
ACTION="${1:-install}"

usage() {
  cat <<EOF
用法: $0 [install|uninstall|status|run-now]
  install     写入 LaunchAgents 并 load（工作日 15:30）
  uninstall   unload 并删除 plist
  status      查看是否已加载
  run-now     立即手动跑一遍（今日，可加环境变量）
EOF
}

case "$ACTION" in
  -h|--help) usage; exit 0 ;;
esac

chmod +x "$PIPELINE" "$ROOT/scripts/install_launchd.sh" 2>/dev/null || true

if [[ "$ACTION" == "run-now" ]]; then
  exec /bin/bash "$PIPELINE" "${@:2}"
fi

if [[ "$ACTION" == "uninstall" ]]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || \
    launchctl unload "$DEST" 2>/dev/null || true
  rm -f "$DEST"
  echo "uninstalled $LABEL"
  exit 0
fi

if [[ "$ACTION" == "status" ]]; then
  launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null || \
    launchctl list | grep -F "$LABEL" || echo "not loaded"
  [[ -f "$DEST" ]] && echo "plist=$DEST" || echo "plist=missing"
  [[ -f "$BOOT_SH" ]] && echo "boot=$BOOT_SH" || echo "boot=missing"
  echo "last_exit=$(launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | awk '/last exit code/{print $4; exit}')"
  tail -n 5 "$LOG_DIR/launchd.err.log" 2>/dev/null || true
  exit 0
fi

if [[ "$ACTION" != "install" ]]; then
  usage
  exit 2
fi

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR" "$APP_SUPPORT"
[[ -f "$TEMPLATE" ]] || { echo "missing template $TEMPLATE" >&2; exit 1; }
[[ -f "$BOOT_TEMPLATE" ]] || { echo "missing $BOOT_TEMPLATE" >&2; exit 1; }
[[ -f "$PIPELINE" ]] || { echo "missing $PIPELINE" >&2; exit 1; }
chmod +x "$PIPELINE"

python3.12 -V >/dev/null
node -v >/dev/null
[[ -f "$HOME/.cursor/skills/douyin-image-publish/scripts/publish-video.mjs" ]] || {
  echo "WARN: 未找到抖音 publish-video.mjs，发布阶段会失败" >&2
}

if [[ "$ROOT" == *"/Desktop/"* ]]; then
  echo "NOTE: 工程在 Desktop 下。launchd 不能直接读 Desktop（TCC），"
  echo "      已改为经 Terminal.app 启动流水线。"
fi

PYENV_SHIMS=""
[[ -d "$HOME/.pyenv/shims" ]] && PYENV_SHIMS="$HOME/.pyenv/shims:"
NODE_DIR="$(dirname "$(command -v node)")"
PY_DIR="$(dirname "$(command -v python3.12)")"
LAUNCH_PATH="${PY_DIR}:${NODE_DIR}:${PYENV_SHIMS}/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# 安装可被 launchd 执行的 boot 包装（不在 Desktop）
sed -e "s|__PROJECT_DIR__|$ROOT|g" "$BOOT_TEMPLATE" > "$BOOT_SH"
# 注入 PATH 到 boot 环境（osascript 子 shell 会用）
# boot 脚本里用 PATH 环境变量；确保 plist 传入
chmod +x "$BOOT_SH"

tmp="$(mktemp)"
sed \
  -e "s|__BOOT_SH__|$BOOT_SH|g" \
  -e "s|__APP_SUPPORT__|$APP_SUPPORT|g" \
  -e "s|__PROJECT_DIR__|$ROOT|g" \
  -e "s|__HOME__|$HOME|g" \
  -e "s|__LOG_DIR__|$LOG_DIR|g" \
  -e "s|__PATH__|$LAUNCH_PATH|g" \
  "$TEMPLATE" > "$tmp"
mv "$tmp" "$DEST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || \
  launchctl unload "$DEST" 2>/dev/null || true
if launchctl bootstrap "gui/$(id -u)" "$DEST" 2>/dev/null; then
  launchctl enable "gui/$(id -u)/$LABEL" 2>/dev/null || true
else
  launchctl load -w "$DEST"
fi

echo "installed: $DEST"
echo "boot: $BOOT_SH"
echo "schedule: Mon–Fri 15:30 Asia/Shanghai（脚本内再过滤休市）"
echo "logs: $LOG_DIR/"
echo "manual: $0 run-now"
echo "status: $0 status"
echo "tip: 若仍失败，给「终端」完全磁盘访问，或把仓库移出 Desktop"
