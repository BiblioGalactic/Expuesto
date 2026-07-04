#!/bin/bash
# ♻️ =====================================================================
# ♻️ PLANTA — clasificación y tratamiento del dato (ciclo de vida).
# ♻️ Reciclaje EN ORIGEN: la clase la decide la UBICACIÓN (ver RETENCION.md),
# ♻️ así tratar es casi trivial y "quemar/enterrar" es el último recurso.
# ♻️ Etapas: acopio · identificación · separación · tratamiento · valorización · disposición.
# ♻️ Uso:  ./planta.sh [acopio|tratar|frio-a-ssd]   (sin arg = acopio, el inventario)
# ♻️ Nada se borra en duro: a frío (.gz) o a trash/.
# ♻️ =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
DATA="$BASE/data"; RES="$BASE/resultados"; TRASH="$BASE/trash"; FRIO="$TRASH/frio"
MATERIA="$DATA/materia_prima"
MANT="$BASE/mantenimiento.sh"
LOG_MAX_MB="${LOG_MAX_MB:-30}"          # log creciente que pase de esto -> .gz a frío
HECHOS_MAX_MB="${HECHOS_MAX_MB:-50}"    # silo/.hechos y cuarentena/.hechos: a frío al pasar de esto
SSD_DESTINO="${SSD_DESTINO:-}"          # ruta de la SSD del mini para el acarreo final (rsync)

ts() { date '+%H:%M:%S'; }
log()  { printf '[%s] ♻️  %s\n' "$(ts)" "$*"; }
warn() { printf '[%s] ⚠️  %s\n' "$(ts)" "$*" >&2; }
# shellcheck disable=SC1091
source "$BASE/lock.sh" 2>/dev/null || true
cleanup() { soltar_locks 2>/dev/null || true; }
trap cleanup EXIT

mb()    { du -sm "$1" 2>/dev/null | cut -f1; }
edad_d() {                              # días desde la última modificación (portable)
    local m; m="$(stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0)"
    [[ "$m" =~ ^[0-9]+$ ]] || m="$(date +%s)"
    echo $(( ( $(date +%s) - m ) / 86400 ))
}

# --- MAPA de clasificación (separación en origen): ruta-relativa -> CLASE ---
clase_de() {
    case "$1" in
        capabilities/*) echo ORO ;;
        data/state.json|data/elo.json|data/reward.json|data/*_scores.json|data/dignidad_modelos.json|data/context_cache.json) echo ESTADO ;;
        data/historial.jsonl) echo ACTIVO ;;
        data/historial.consolidado.jsonl|data/tribunal_roles*.jsonl|data/defensa_roles.jsonl|data/*_traza.jsonl) echo LOG_CRECIENTE ;;
        data/*_vistos.txt|data/vistos*.jsonl) echo REGISTRO ;;
        data/seguridad_propuestas.yaml|data/capabilities_staging.yaml|data/gobernanza_rechazadas.yaml) echo GOBERNANZA ;;
        data/materia_prima|data/materia_prima/*) echo MATERIA_PRIMA ;;
        resultados/*) echo TRANSITORIO ;;
        trash/*) echo TRASH ;;
        data/META.md|data/pausa.flag|data/cola.db*|data/.lock_*) echo OPERATIVO ;;
        *) echo SIN_CLASIFICAR ;;
    esac
}

# === ACOPIO + identificación: inventario de data/ por clase ===
acopio() {
    log "ACOPIO · inventario (clase · tamaño · edad)"
    printf '   %-22s %-14s %6s %6s\n' "FICHERO" "CLASE" "MB" "DÍAS"
    shopt -s nullglob
    for f in "$DATA"/* "$RES"/* "$MATERIA"/*; do
        [ -e "$f" ] || continue
        local rel="${f#$BASE/}" cl
        cl="$(clase_de "$rel")"
        printf '   %-22s %-14s %6s %6s\n' "$(basename "$f")" "$cl" "$(mb "$f")" "$(edad_d "$f")"
    done
    shopt -u nullglob
    log "ORO vivo: $(ls "$BASE/capabilities"/*.yaml 2>/dev/null | wc -l | tr -d ' ') ficheros de capacidades"
}

# === TRATAMIENTO: rotar logs crecientes -> .gz a frío ===
tratar_logs() {
    mkdir -p "$FRIO"
    shopt -s nullglob
    for f in "$DATA"/historial.consolidado.jsonl "$DATA"/tribunal_roles*.jsonl "$DATA"/defensa_roles.jsonl; do
        [ -e "$f" ] || continue
        local m; m="$(mb "$f")"
        if [ "${m:-0}" -ge "$LOG_MAX_MB" ]; then
            local gz="$FRIO/$(basename "$f").$(date +%Y%m%d_%H%M%S).gz"
            if gzip -c "$f" > "$gz" 2>/dev/null; then
                : > "$f"                       # log preservado en frío -> se vacía el vivo
                log "TRATAMIENTO · $(basename "$f") ${m}MB → $(basename "$gz") (vivo vaciado)"
            fi
        fi
    done
    shopt -u nullglob
}

# === VALORIZACIÓN: materia prima DIGERIDA -> se suelta el bulto (la lección ya se guardó) ===
valorizar() {
    [ -d "$MATERIA" ] || { log "VALORIZACIÓN · sin materia prima"; return 0; }
    mkdir -p "$FRIO"
    local sueltos=0 espera=0
    shopt -s nullglob
    for d in "$MATERIA"/*/; do
        [ -d "$d" ] || continue
        if [ -e "${d}.digerido" ]; then
            local nom; nom="$(basename "$d")"
            local gz="$FRIO/materia_${nom}_$(date +%Y%m%d_%H%M%S).tar.gz"
            if tar -czf "$gz" -C "$MATERIA" "$nom" 2>/dev/null; then
                rm -rf "${d%/}"; sueltos=$((sueltos+1))
                log "VALORIZACIÓN · $nom digerido → bulto a frío ($(basename "$gz")), hot liberado"
            fi
        else
            espera=$((espera+1))
        fi
    done
    shopt -u nullglob
    log "VALORIZACIÓN · $sueltos soltados · $espera en espera (sin .digerido, aún valen)"
}

# === LIMPIEZA: procesados/ (antes .hechos ocultos — VISIBLES desde el 4-jul) → frío al pasar de tope ===
limpiar_hechos() {
    mkdir -p "$FRIO"
    local par h tam nom gz
    # pares "directorio|etiqueta": los VISIBLES nuevos primero; los .hechos viejos quedan por
    # transición (si algo antiguo los rellenara, también acaban en frío con la misma etiqueta).
    for par in "$BASE/procesados/silo|silo" "$BASE/procesados/cuarentena|cuarentena" \
               "$BASE/silo/.hechos|silo" "$BASE/cuarentena/.hechos|cuarentena"; do
        h="${par%%|*}"; nom="${par##*|}"
        [ -d "$h" ] || continue
        [ -z "$(ls -A "$h" 2>/dev/null)" ] && continue
        tam="$(mb "$h")"
        if [ "${tam:-0}" -ge "$HECHOS_MAX_MB" ]; then
            gz="$FRIO/${nom}_hechos_$(date +%Y%m%d_%H%M%S).tar.gz"
            if tar -czf "$gz" -C "$h" . 2>/dev/null; then
                rm -rf "${h:?}/"* 2>/dev/null || true
                log "LIMPIEZA · procesados/$nom ${tam}MB → $(basename "$gz") (a frío, vaciado)"
            fi
        fi
    done
}

# === DISPOSICIÓN final: lo transitorio/trash via mantenimiento (poda + rotar trash + disco) ===
disposicion() {
    if [ -x "$MANT" ] || [ -f "$MANT" ]; then
        bash "$MANT" poda  || warn "poda con incidencias"
        bash "$MANT" rotar || warn "rotar trash con incidencias"
        bash "$MANT" disco || warn "disco BAJO (revisa)"
    else
        warn "no encuentro mantenimiento.sh; salto poda/rotar/disco"
    fi
}

# === SIN_CLASIFICAR: no se toca, se reporta (decisión del 'director') ===
reportar_sin_clasificar() {
    shopt -s nullglob
    local hay=0
    for f in "$DATA"/*; do
        [ -e "$f" ] || continue
        local rel="${f#$BASE/}"
        [ "$(clase_de "$rel")" = "SIN_CLASIFICAR" ] && { [ "$hay" = 0 ] && log "SIN_CLASIFICAR (no tocado, para el director):"; hay=1; printf '     · %s (%sMB)\n' "$(basename "$f")" "$(mb "$f")"; }
    done
    shopt -u nullglob
    [ "$hay" = 0 ] && log "SIN_CLASIFICAR · nada (todo encaja en el mapa)"
}

tratar() {
    [ -z "${MOSAIC_EN_ORQUESTADOR:-}" ] && { tomar_lock orquestador || { warn "hay un ciclo/aprendizaje en marcha; no trato ahora"; exit 1; }; }
    log "═══ PLANTA · tratamiento en masa ═══"
    tratar_logs          # 4 · tratamiento
    valorizar            # 5 · valorización
    limpiar_hechos       # 5b · silo/.hechos y cuarentena/.hechos (ya procesados) → frío
    disposicion          # 6 · disposición final
    reportar_sin_clasificar
    log "═══ PLANTA · fin ═══"
}

frio_a_ssd() {
    [ -d "$FRIO" ] || { log "sin frío que acarrear"; return 0; }
    [ -n "$SSD_DESTINO" ] || { warn "define SSD_DESTINO (ruta de la SSD del mini) para el acarreo"; return 1; }
    command -v rsync >/dev/null || { warn "falta rsync"; return 1; }
    log "ACARREO · frío → SSD ($SSD_DESTINO)"
    rsync -av --protect-args "$FRIO/" "$SSD_DESTINO/" && log "acarreo OK (revisa y luego puedes vaciar $FRIO)"
}

case "${1:-acopio}" in
    acopio)      acopio ;;
    tratar)      tratar ;;
    frio-a-ssd)  frio_a_ssd ;;
    *)           warn "uso: planta.sh acopio|tratar|frio-a-ssd"; exit 1 ;;
esac
