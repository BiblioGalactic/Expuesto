#!/usr/bin/env bash
# ════════════════════════════════════════
# 🖥️ BiblioGalactic Dashboard — Server
# ════════════════════════════════════════
# Sirve el dashboard en localhost con Python http.server.
# Sin dependencias externas.
#
# Uso: bash Expuesto/dashboard/serve.sh [port]
# Default: http://localhost:8420
# ════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${1:-8420}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 no encontrado"
    exit 1
fi

echo ""
echo "  ═══════════════════════════════════════"
echo "  🖥️  BiblioGalactic Dashboard"
echo "  ═══════════════════════════════════════"
echo ""
echo "  URL: http://localhost:$PORT"
echo "  Dir: $SCRIPT_DIR"
echo "  Ctrl+C para detener"
echo ""

cd "$SCRIPT_DIR"
python3 -m http.server "$PORT" --bind 127.0.0.1
