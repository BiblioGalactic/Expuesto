#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# 🎵 Instalar ffmpeg (macOS)
# Autor: Eto Demerzel (Gustavo Silva Da Costa)
# Licencia: CC BY-NC-SA 4.0
# ═══════════════════════════════════════════════════════════
set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  echo "❌ Homebrew no encontrado. Instala Homebrew primero: https://brew.sh"
  exit 1
fi

brew install ffmpeg
which ffmpeg
ffmpeg -version | head -n 1
