#!/usr/bin/env bash
# 安装：工作日 17:00 自动刷新「理财每日新知」
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.etf68.finance-news-daily"
PIPELINE="$REPO/scripts/daily_finance_news.sh"
BOOT_TEMPLATE="$REPO/scripts/launchd/finance-news-boot.sh.template"
APP_SUPPORT="$HOME/Library/Application Support/etf68-finance-news"
BOOT_SH="$APP_SUPPORT/launchd-boot.sh"
DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/Library/Logs/etf68-finance-news"
ACTION="${1:-install}"

usage() {
  cat <<EOF
用法: $0 [install|uninstall|status|run-now]
EOF
}

chmod +x "$PIPELINE" "$0" 2>/dev/null || true

case "$ACTION" in
  -h|--help) usage; exit 0 ;;
  run-now) FORCE=1 exec /bin/bash "$PIPELINE" ;;
  uninstall)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$DEST"
    echo "uninstalled $LABEL"
    exit 0
    ;;
  status)
    launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | head -40 || echo "not loaded"
    exit 0
    ;;
  install) ;;
  *) usage; exit 2 ;;
esac

mkdir -p "$APP_SUPPORT" "$LOG_DIR" "$HOME/Library/LaunchAgents"
python3.12 -V >/dev/null

PYENV_SHIMS=""; [[ -d "$HOME/.pyenv/shims" ]] && PYENV_SHIMS="$HOME/.pyenv/shims:"
PATH_VAL="${HOME}/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

sed -e "s|__PIPELINE__|$PIPELINE|g" "$BOOT_TEMPLATE" > "$BOOT_SH"
chmod +x "$BOOT_SH"

cat > "$DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>${BOOT_SH}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${APP_SUPPORT}</string>
    <key>StartCalendarInterval</key>
    <array>
      <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
      <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
      <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
      <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
      <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key><string>${PATH_VAL}</string>
      <key>HOME</key><string>${HOME}</string>
      <key>TZ</key><string>Asia/Shanghai</string>
      <key>NO_PROXY</key><string>*</string>
    </dict>
    <key>StandardOutPath</key><string>${LOG_DIR}/launchd.out.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/launchd.err.log</string>
    <key>LimitLoadToSessionType</key><string>Aqua</string>
    <key>ProcessType</key><string>Interactive</string>
    <key>RunAtLoad</key><false/>
  </dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
launchctl enable "gui/$(id -u)/$LABEL" 2>/dev/null || true
echo "installed $DEST"
echo "schedule: Mon–Fri 17:00（Terminal 拉起，避开 Desktop TCC）"
echo "manual: $0 run-now"
echo "also: npm run engine:generate 末尾会顺带刷理财每日新知"
