#!/bin/bash
# 🧹 =====================================================================
# 🧹 MANTENIMIENTO — poda de resultados/, rotación de trash y guard de disco.
# 🧹 Nada se borra: todo va a trash/ y se comprime al llegar al tope (política Gustavo).
# 🧹 Uso:  ./mantenimiento.sh poda|rotar|disco|all
# 🧹 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
RES="$BASE/resultados"
TRASH="$BASE/trash"
MAX_RES_MB="${MAX_RES_MB:-200}"      # si resultados/ pasa de esto, poda los más viejos
TRASH_MAX_MB="${TRASH_MAX_MB:-30}"   # cubo que llega aquí -> tar.gz y se vacía
MIN_FREE_GB="${MIN_FREE_GB:-5}"      # por debajo de esto, 'disco' falla (salta consolidar)

ts() { date '+%H:%M:%S'; }
log()  { printf '[%s] 🧹 %s\n' "$(ts)" "$*"; }
warn() { printf '[%s] ⚠️  %s\n' "$(ts)" "$*" >&2; }
cleanup() { :; }
trap cleanup EXIT

validar() {
    [ -d "$BASE" ] || { warn "no existe $BASE"; exit 1; }
    for c in du df tar; do command -v "$c" >/dev/null || { warn "falta $c"; exit 1; }; done
    mkdir -p "$TRASH"/{logs,historico,backups,otros,comprimidos}
}

mb_de() { du -sm "$1" 2>/dev/null | cut -f1; }

# --- resultados/ : mover subcarpetas más viejas a trash/historico hasta bajar del tope ---
podar_resultados() {
    [ -d "$RES" ] || { log "no hay resultados/ todavía"; return 0; }
    local mb; mb="$(mb_de "$RES")"
    if [ "${mb:-0}" -le "$MAX_RES_MB" ]; then
        log "resultados/ ${mb:-0}MB ≤ ${MAX_RES_MB}MB · nada que podar"; return 0
    fi
    log "resultados/ ${mb}MB > ${MAX_RES_MB}MB · podo los más viejos → trash/historico"
    while [ "${mb:-0}" -gt "$MAX_RES_MB" ]; do
        local viejo; viejo="$(ls -1tr "$RES" 2>/dev/null | head -1)"
        [ -z "$viejo" ] && break
        mv "$RES/$viejo" "$TRASH/historico/" 2>/dev/null || break
        log "  → movido: $viejo"
        mb="$(mb_de "$RES")"
    done
}

# --- trash/ : cubo que llega a TRASH_MAX_MB -> tar.gz a comprimidos/ y se vacía ---
rotar_trash() {
    for b in logs historico backups otros; do
        local d="$TRASH/$b"; [ -d "$d" ] || continue
        [ -z "$(ls -A "$d" 2>/dev/null)" ] && continue
        local mb; mb="$(mb_de "$d")"
        if [ "${mb:-0}" -ge "$TRASH_MAX_MB" ]; then
            local tgz="$TRASH/comprimidos/${b}_$(date +%Y%m%d_%H%M%S).tar.gz"
            if tar -czf "$tgz" -C "$TRASH" "$b" 2>/dev/null; then
                rm -rf "${d:?}/"* 2>/dev/null || true
                log "📦 $b ${mb}MB → $(basename "$tgz") (cubo vaciado)"
            fi
        fi
    done
}

# --- disco : informa libre; falla (3) si por debajo del mínimo ---
disco() {
    local free; free="$(df -P -k "$BASE" 2>/dev/null | awk 'NR==2{print int($4/1048576)}')"
    log "disco libre: ${free:-?}GB (mínimo ${MIN_FREE_GB}GB)"
    if [ "${free:-0}" -lt "$MIN_FREE_GB" ]; then warn "ESPACIO BAJO — conviene no consolidar"; return 3; fi
    return 0
}

main() {
    validar
    case "${1:-all}" in
        poda)  podar_resultados ;;
        rotar) rotar_trash ;;
        disco) disco ;;
        all)   podar_resultados; rotar_trash; disco || true ;;
        *)     warn "uso: $0 poda|rotar|disco|all"; exit 1 ;;
    esac
}
main "$@"
