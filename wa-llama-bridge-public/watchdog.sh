#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# ♻️ Bridge Watchdog — Auto Restart
# Autor: Eto Demerzel (Gustavo Silva Da Costa)
# Licencia: CC BY-NC-SA 4.0
# ═══════════════════════════════════════════════════════════
set -euo pipefail

cd "$(dirname "$0")"

echo "[wa-llama-watchdog] starting loop"
while true; do
  echo "[wa-llama-watchdog] launch $(date '+%F %T')"
  node bridge.js
  code=$?
  echo "[wa-llama-watchdog] bridge exit code=$code"

  if [[ "$code" -eq 130 ]]; then
    echo "[wa-llama-watchdog] stopping by user"
    exit 0
  fi

  sleep 2
done
