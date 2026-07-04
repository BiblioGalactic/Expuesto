#!/bin/bash
# 🔭 =====================================================================
# 🔭 SILO CONVERSACIONES — MOSAIC observa tu historial de chats de la MÁS ANTIGUA
# 🔭 hacia HOY (evolución cronológica), depositando una nota en el calendario por cada
# 🔭 conversación (vía mosaic_observador.py). Reanudable (memoria unificada, ámbito
# 🔭 'conversaciones'). Cada chat es enorme (tamaño Gutenberg) → de UNA en una.
# 🔭 Relleno de BAJA PRIORIDAD: el modo 'idle' digiere solo cuando NO hay tareas y el
# 🔭 server sigue vivo, y CEDE el paso en cuanto llega trabajo real.
# 🔭 Uso:
# 🔭   ./silo_conversaciones.sh [N]    procesa N (def. 1) de la más antigua sin observar
# 🔭   ./silo_conversaciones.sh idle   bucle ocioso preemptable (máx CONV_IDLE_MIN min)
# 🔭 =====================================================================
set -uo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
CAL="${CALENDARIO_DIR:-$HOME/proyecto/calendario_mental}"
CHATS="${CHATS_DIR:-$CAL/chats}"
CHATS_TXT="${CHATS_TXT_DIR:-$CAL/conversaciones_txt}"   # fix Fase B (2-jul): aquí deja los 4.8k .txt el extractor — nadie los leía
NOTAS="${NOTAS_DIR:-$CAL/notas_clasificadas}"
MEM="${MEMORIA:-$BASE/memoria.sh}"
OBS="${OBSERVADOR:-$BASE/mosaic_observador.py}"
COLA="${COLA_SH:-$BASE/cola.sh}"
CLUSTER="${MOSAIC_LLM_BASE_URL:-http://127.0.0.1:8090/v1}"
PYBIN="${PYBIN:-$HOME/wikirag/venv/bin/python3}"; [ -x "$PYBIN" ] || PYBIN="$(command -v python3)"
IDLE_MIN="${CONV_IDLE_MIN:-20}"
PROC_LOCK="$BASE/data/.conversaciones.lock"

log()  { printf '[%s] 🔭 %s\n' "$(date +%H:%M:%S)" "$*"; }
vivo() { curl -s -m 4 "$CLUSTER/models" >/dev/null 2>&1; }
cola_size() { "$COLA" size 2>/dev/null || echo 0; }

# conversaciones de la MÁS ANTIGUA a la más nueva (por la fecha del nombre; sin fecha → al final)
por_antiguedad() {
    find "$CHATS" "$CHATS_TXT" -type f \( -name '*.txt' -o -name '*.json' \) 2>/dev/null | while IFS= read -r f; do
        d="$(basename "$f" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)"
        printf '%s\t%s\n' "${d:-9999-99-99}" "$f"
    done | sort | cut -f2-
}

# observa hasta N conversaciones nuevas; deja el nº en PROCESADAS
procesar_n() {
    local objetivo="$1"; PROCESADAS=0
    while IFS= read -r f; do
        [ "$PROCESADAS" -ge "$objetivo" ] && break
        [ -f "$f" ] || continue
        bash "$MEM" visto conversaciones "$f" && continue          # ya observada (reanudable)
        log "observando (viejo→hoy): $(basename "$f")"
        if "$PYBIN" "$OBS" "$f" "$NOTAS" >/dev/null 2>&1; then
            bash "$MEM" marcar conversaciones "$f"; PROCESADAS=$((PROCESADAS + 1))
            log "  ✅ nota depositada en el calendario"
        else
            log "  ⚠️ observación falló (¿cluster?) → no marco, se reintenta luego"; break
        fi
    done < <(por_antiguedad)
}

modo_idle() {
    mkdir "$PROC_LOCK" 2>/dev/null || { log "ya hay una digestión ociosa en marcha; salgo"; exit 0; }
    trap 'rmdir "$PROC_LOCK" 2>/dev/null || true' EXIT
    local hasta=$(( $(date +%s) + IDLE_MIN * 60 ))
    log "modo ocioso: digiero conversaciones (máx ${IDLE_MIN}min) mientras no haya tareas y el server viva"
    while [ "$(date +%s)" -lt "$hasta" ]; do
        local c; c="$(cola_size)"
        [ "${c:-0}" -gt 0 ] && { log "llegó trabajo real (cola=$c) → cedo prioridad y salgo"; break; }
        vivo || { log "server caído → paro"; break; }
        procesar_n 1
        [ "$PROCESADAS" -eq 0 ] && { log "nada nuevo que observar (o falló) → paro"; break; }
        sleep "${CONV_PAUSA:-2}"
    done
    log "digestión ociosa: terminada."
}

case "${1:-1}" in
    idle) modo_idle ;;
    *)  [ -d "$CHATS" ] || { log "no encuentro chats en $CHATS (define CHATS_DIR)"; exit 0; }
        [ -f "$OBS" ]  || { log "falta el observador: $OBS"; exit 0; }
        procesar_n "${1:-1}"
        log "observadas esta pasada: $PROCESADAS (de la más antigua hacia hoy)" ;;
esac
