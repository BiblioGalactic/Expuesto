#!/bin/bash
# 🚚 Recoge la despensa del mini → ~/oraculo local (hallazgos+lotes). NO bloquea:
#    si el mini no responde en 60s, sigue. Llamar en 2º plano al INICIO de FASE 1:
#        "$HOME/Mosaic_privado/recoger_del_mini.sh" &
set -uo pipefail
MINI_SSH="${MINI_SSH:-$USER@localhost}"
ORACULO_DIR="${ORACULO_DIR:-$HOME/oraculo}"   # multi-empresa: destino local por empresa (colisión c)
mkdir -p "$ORACULO_DIR/hallazgos" "$ORACULO_DIR/lotes"
for sub in hallazgos lotes; do
    timeout 60 rsync -az -e ssh "$MINI_SSH:${MINI_HOME:-$HOME}/oraculo/$sub/" "${ORACULO_DIR:-$HOME/oraculo}/$sub/" 2>/dev/null \
        && echo "🚚 recogido $sub del mini" || echo "🚚 mini no disponible ($sub) — sigo sin esperar"
done
