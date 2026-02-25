#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# 🧠 llama-server (Fallback) — Template
# Autor: Eto Demerzel (Gustavo Silva Da Costa)
# Licencia: CC BY-NC-SA 4.0
# ═══════════════════════════════════════════════════════════
set -euo pipefail

# Edita estas rutas antes de usar.
LLAMA_BIN="/absolute/path/to/llama.cpp/build/bin/llama-server"
MODEL_PATH="/absolute/path/to/fallback-model.gguf"

CTX_SIZE="${CTX_SIZE:-32000}"
N_PREDICT="${N_PREDICT:-500}"
TEMP="${TEMP:-1.0}"
THREADS="${THREADS:-6}"
THREADS_BATCH="${THREADS_BATCH:-6}"
PORT="${PORT:-8081}"

"$LLAMA_BIN" \
  -m "$MODEL_PATH" \
  --ctx-size "$CTX_SIZE" \
  --n-predict "$N_PREDICT" \
  --temp "$TEMP" \
  --threads "$THREADS" \
  --threads-batch "$THREADS_BATCH" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --jinja \
  --color \
  --cache-ram 0
