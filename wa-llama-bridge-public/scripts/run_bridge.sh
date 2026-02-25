#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# 📲 WhatsApp -> llama.cpp Bridge — Runner
# Autor: Eto Demerzel (Gustavo Silva Da Costa)
# Licencia: CC BY-NC-SA 4.0
# ═══════════════════════════════════════════════════════════
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

if [[ ! -f ".env" ]]; then
  echo "❌ Falta .env. Ejecuta: cp .env.example .env"
  exit 1
fi

echo "🚀 Iniciando bridge en: $ROOT_DIR"
node bridge.js
