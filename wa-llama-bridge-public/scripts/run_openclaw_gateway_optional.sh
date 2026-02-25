#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# 🦞 OpenClaw Gateway (Opcional) — Runner
# Autor: Eto Demerzel (Gustavo Silva Da Costa)
# Licencia: CC BY-NC-SA 4.0
# ═══════════════════════════════════════════════════════════
set -euo pipefail

# Solo si quieres coexistencia con OpenClaw para otros canales/herramientas.
# El bridge WhatsApp->llama.cpp NO lo necesita.

PORT="${PORT:-18789}"
openclaw gateway run --bind loopback --port "$PORT" --force --verbose
