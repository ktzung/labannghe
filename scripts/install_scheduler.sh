#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.labannghe.daily.plist"
LABEL="com.labannghe.daily"
FORCE=0
ASSUME_YES=0
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --yes) ASSUME_YES=1 ;;
    --dry-run) DRY_RUN=1 ;;
    *) echo "Tham số không hợp lệ: $arg" >&2; exit 2 ;;
  esac
done

if [ -e "$PLIST" ] && [ "$FORCE" -ne 1 ]; then
  echo "Đã có $PLIST. Dùng --force để ghi đè." >&2
  exit 1
fi

if [ "$DRY_RUN" -ne 1 ] && [ "$ASSUME_YES" -ne 1 ]; then
  echo "Sẽ cài lịch chạy 06:30 hằng ngày bằng launchd:"
  echo "  $PLIST"
  printf "Tiếp tục? [y/N] "
  read -r answer
  case "$answer" in
    y|Y|yes|YES) ;;
    *) echo "Đã huỷ."; exit 0 ;;
  esac
fi

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/data/logs"
chmod +x "$ROOT/scripts/run_daily.sh"

PLIST_CONTENT='<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.labannghe.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>__ROOT__/scripts/run_daily.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>__ROOT__</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>30</integer>
  </dict>
  <key>RunAtLoad</key>
  <false/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>StandardOutPath</key>
  <string>__ROOT__/data/logs/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>__ROOT__/data/logs/launchd.err.log</string>
</dict>
</plist>'

PLIST_CONTENT="${PLIST_CONTENT//__ROOT__/$ROOT}"

if [ "$DRY_RUN" -eq 1 ]; then
  printf '%s\n' "$PLIST_CONTENT"
  exit 0
fi

printf '%s\n' "$PLIST_CONTENT" > "$PLIST"
plutil -lint "$PLIST"
launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST"

echo "Đã cài lịch. Kiểm tra:"
echo "  launchctl print gui/$UID/$LABEL | head -40"
echo "Gỡ bỏ:"
echo "  launchctl bootout gui/$UID/$PLIST && rm $PLIST"
