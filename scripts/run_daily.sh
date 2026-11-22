#!/bin/zsh
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/data/logs"
LOG="$LOG_DIR/ingest.log"
mkdir -p "$LOG_DIR"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3)"
fi

if [ -z "$PY" ]; then
  echo "Không tìm thấy python3." >&2
  exit 1
fi

if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" | tr -d ' ')" -gt 5000000 ]; then
  mv "$LOG" "$LOG.1"
fi

cd "$ROOT" || exit 1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] bắt đầu cập nhật" >> "$LOG"

rc=0
"$PY" -m laban.cli ingest --max-pages 30 >> "$LOG" 2>&1 || rc=$?
"$PY" -m laban.cli social-ingest --mode auto >> "$LOG" 2>&1 || rc=$?
"$PY" -m laban.cli reclassify >> "$LOG" 2>&1 || rc=$?
"$PY" -m laban.cli prune --raw-days 21 --vacuum >> "$LOG" 2>&1 || rc=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] kết thúc, mã lỗi $rc" >> "$LOG"
exit "$rc"
