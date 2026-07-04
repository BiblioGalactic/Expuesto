#!/bin/bash
# 🧠 =====================================================================
# 🧠 MINI — control del "segundo cerebro" (Mac mini) DESDE el MacBook, por SSH.
# 🧠 Lo lanzamos con nohup (sobrevive al cierre de sesión) -> Ctrl+C NO lo para:
# 🧠 hay que pararlo a propósito con 'parar' (mata el PID guardado + pkill de respaldo).
# 🧠 Uso:  ./mini.sh lanzar | parar | reiniciar | estado | ver
# 🧠 =====================================================================
set -euo pipefail

MINI_SSH="${MINI_SSH:-$USER@localhost}"
MINI_HOST="${MINI_HOST:-localhost}"
MINI_PORT="${MINI_PORT:-8090}"
MINI_MODEL="${MINI_MODEL:-\$HOME/modelo/modelos_grandes/mistral3/Ministral-8B-Instruct-2410-Q8_0.gguf}"
MINI_CTX="${MINI_CTX:-4096}"
MINI_LOG="${MINI_LOG:-mini_llama.log}"
MINI_PIDF="${MINI_PIDF:-mini_llama.pid}"
ESPERA="${ESPERA:-120}"
MINI_URL="http://$MINI_HOST:$MINI_PORT/v1"
DIR="$(cd "$(dirname "$0")" && pwd)"

log() { printf '[%s] 🧠 %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ✗  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
command -v ssh  >/dev/null 2>&1 || { err "falta ssh";  exit 1; }
command -v curl >/dev/null 2>&1 || { err "falta curl"; exit 1; }

estado() { curl -s -m 3 "$MINI_URL/models" >/dev/null 2>&1; }

lanzar() {
    if estado; then log "ya arriba ($MINI_URL)"; return 0; fi
    log "lanzando llama-server en el mini (puerto $MINI_PORT, guardo PID)…"
    # nohup -> desencadenado; guardamos el PID para poder pararlo limpio luego
    ssh -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "$MINI_SSH" \
        "nohup \$HOME/modelo/llama.cpp/build/bin/llama-server -m $MINI_MODEL \
         --host 0.0.0.0 --port $MINI_PORT --ctx-size $MINI_CTX -ngl 99 --threads 8 \
         > \$HOME/$MINI_LOG 2>&1 & echo \$! > \$HOME/$MINI_PIDF" \
        || { err "no pude lanzar por SSH"; return 1; }
    local t=0
    until estado; do sleep 3; t=$((t + 3)); [ "$t" -ge "$ESPERA" ] && { err "sin respuesta tras ${t}s"; return 1; }; done
    log "mini ✅ arriba (${t}s) · log: ~/$MINI_LOG · míralo con: ./mini.sh ver"
}

parar() {
    log "parando el mini limpiamente (PID guardado + pkill de respaldo)…"
    ssh -o ConnectTimeout=8 "$MINI_SSH" "
        P=\$(cat \$HOME/$MINI_PIDF 2>/dev/null || true)
        if [ -n \"\$P\" ] && kill -0 \"\$P\" 2>/dev/null; then
            kill \"\$P\" 2>/dev/null; sleep 1; kill -9 \"\$P\" 2>/dev/null || true
            echo \"  PID \$P terminado\"
        fi
        pkill -f 'llama-server.*--port $MINI_PORT' 2>/dev/null && echo '  (pkill de respaldo)' || true
        rm -f \$HOME/$MINI_PIDF
    " || { err "no pude contactar el mini para pararlo"; return 1; }
    if estado; then err "sigue respondiendo… reintenta ./mini.sh parar"; else log "mini parado ✅"; fi
}

reiniciar() { parar || true; sleep 2; lanzar; }

ver() {
    if [ -x "$DIR/ver_mini.sh" ] || [ -f "$DIR/ver_mini.sh" ]; then
        exec bash "$DIR/ver_mini.sh"
    fi
    ssh -t "$MINI_SSH" "tail -n 40 -f \$HOME/$MINI_LOG"
}

case "${1:-estado}" in
    lanzar)    lanzar ;;
    parar)     parar ;;
    reiniciar) reiniciar ;;
    estado)    if estado; then log "mini ✅ arriba ($MINI_URL)"; else log "mini 🔴 caído"; fi ;;
    ver)       ver ;;
    *)         err "uso: mini.sh lanzar | parar | reiniciar | estado | ver"; exit 1 ;;
esac
