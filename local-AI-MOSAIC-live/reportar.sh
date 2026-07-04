#!/bin/bash
# 📋 =====================================================================
# 📋 REPORTAR — EL escritor único y SEGURO del epistolar (RONDA 3 · diseño Opus).
# 📋   Por aquí pasan TODOS: el modal [R] del monitor, los agentes y el humano.
# 📋   Mecánica: bloque COMPLETO en tmp → cerrojo (lock.sh, con RETRY) → append
# 📋   íntegro a info/CARTAS.md → soltar. El monitor ve el mtime y repinta solo.
# 📋   CARTAS = fuente ÚNICA (decisión de Gustavo, R3): sin actual.md aparte.
# 📋 Uso:  ./reportar.sh "Informe|Decisión|Incidente" "titulo" "cuerpo" ["tag1 tag2"] ["autor"]
# 📋   autor por defecto: $REPORTAR_AUTOR o Gustavo (el humano en la terminal).
# 📋 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
CARTAS="${CARTAS_MD:-$BASE/info/CARTAS.md}"

# shellcheck disable=SC1091
export LOCK_MAXEDAD="${LOCK_MAXEDAD:-60}"   # el lock de CARTAS dura ms → uno >60s está muerto: auto-cura el huérfano
source "$BASE/lock.sh"
TMPBLOQUE=""
cleanup() { soltar_locks 2>/dev/null || true; [ -n "$TMPBLOQUE" ] && rm -f "$TMPBLOQUE" 2>/dev/null || true; }
trap cleanup EXIT

log() { printf '[%s] 📋 %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

TIPO="${1:-}"; TITULO="${2:-}"; CUERPO="${3:-}"; ETIQ="${4:-}"; AUTOR="${5:-${REPORTAR_AUTOR:-Gustavo}}"

validar() {
    if [ -z "$TIPO" ] || [ -z "$TITULO" ] || [ -z "$CUERPO" ]; then
        err 'uso: reportar.sh "Informe|Decisión|Incidente" "titulo" "cuerpo" ["tag1 tag2"] ["autor"]'
        exit 2
    fi
    case "$TIPO" in
        Informe|Incidente|Decisión) : ;;
        Decision) TIPO="Decisión" ;;
        *) err "tipo desconocido: $TIPO (Informe | Decisión | Incidente)"; exit 2 ;;
    esac
    [ -f "$CARTAS" ] || { err "no encuentro el epistolar: $CARTAS"; exit 1; }
    command -v date >/dev/null || { err "sin date (imposible)"; exit 1; }
}

emoji_de() {   # firma automática: autor + su emoji de la mesa
    case "$1" in
        Opus*) printf '🔭' ;; Fable*) printf '🔧' ;; MOSAIC*) printf '🤖' ;;
        Gustavo*) printf '💚' ;; *) printf '✉️' ;;
    esac
}

ejecutar() {
    local ts tags="" t
    ts="$(TZ=Europe/Madrid date '+%Y-%m-%d %H:%M')"
    # etiquetas → `#tag1 #tag2` (acepta con o sin #, comas o espacios)
    if [ -n "$ETIQ" ]; then
        set -f                                   # noglob: un tag '*' es literal, NO la lista de ficheros (lupa Opus R3)
        for t in $(printf '%s' "$ETIQ" | tr ',' ' '); do
            case "$t" in \#*) tags="$tags$t " ;; *) tags="$tags#$t " ;; esac
        done
        set +f
        tags="${tags% }"
    fi
    TMPBLOQUE="$(mktemp "${TMPDIR:-/tmp}/reporte.XXXXXX")"
    {
        printf '\n======\n\n'
        printf '## 📋 %s → la mesa · %s: %s · %s\n\n' "$AUTOR" "$TIPO" "$TITULO" "$ts"
        printf '%s\n' "$CUERPO"
        [ -n "$tags" ] && printf '\n`%s`\n' "$tags"
        printf '\n— %s %s\n' "$AUTOR" "$(emoji_de "$AUTOR")"
    } > "$TMPBLOQUE"
    # cerrojo con RETRY (diseño Opus R3): el append dura ms — no fallamos por un pestañeo
    local i=0
    until tomar_lock cartas 2>/dev/null; do
        i=$((i + 1))
        [ "$i" -ge 10 ] && { err "el epistolar lleva ocupado ~2s (¿lock huérfano? mira data/.lock_cartas)"; exit 1; }
        sleep 0.2
    done
    cat "$TMPBLOQUE" >> "$CARTAS"       # bloque COMPLETO bajo el cerrojo → jamás media entrada
    log "depositado: $TIPO «${TITULO}» ($AUTOR) → $(basename "$CARTAS")"   # llaves: el » pegado no se traga la var (macOS bash + set -u)
}

validar
ejecutar
