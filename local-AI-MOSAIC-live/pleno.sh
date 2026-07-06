#!/bin/bash
# 🏛️ =====================================================================
# 🏛️ PLENO — la orquesta ENTERA habla, de una orden (orden de Gustavo 5-jul).
# 🏛️   Recorre roles/turnos/*.yaml y da el turno a cada silla por el MISMO motor
# 🏛️   (turno_rol.sh): salvaguardas, cadencia y kill-switches intactos — un rol
# 🏛️   callado por cadencia o switch NO es un fallo, es disciplina. Un rol que
# 🏛️   falla NO tumba el pleno: se apunta y se sigue. Resumen al final.
# 🏛️   El portavoz global (autodiagnosis.sh) cierra el pleno si está activo.
# 🏛️   SQUAD (debate noventero 5-jul, mockup de Gustavo): con args de roles, SOLO esas
# 🏛️   sillas entran en la sala — la CADENCIA sigue mandando (elegir no es forzar).
# 🏛️ Uso:  ./pleno.sh                       (todos los turnos + portavoz)
# 🏛️       ./pleno.sh --dry                 (qué diría cada silla; NO postea nada)
# 🏛️       ./pleno.sh --sin-portavoz
# 🏛️       ./pleno.sh seguridad auditor …   (SQUAD: solo esas sillas)
# 🏛️ =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
TURNOS_DIR="${TURNOS_DIR:-$BASE/roles/turnos}"
DRYFLAG=""; PORTAVOZ=1; SQUAD=()
for a in "$@"; do case "$a" in
    --dry) DRYFLAG="--dry" ;;
    --sin-portavoz) PORTAVOZ=0 ;;
    -*) printf '⚠️  flag desconocida: %s\n' "$a" >&2; exit 2 ;;
    *) SQUAD+=("$a") ;;
esac; done
[ "${#SQUAD[@]}" -gt 0 ] && PORTAVOZ=0                     # el portavoz cierra PLENOS COMPLETOS, no squads

log() { printf '[%s] 🏛️  %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

validar() {
    [ -d "$TURNOS_DIR" ] || { err "sin sillas: $TURNOS_DIR"; exit 1; }
    [ -f "$BASE/turno_rol.sh" ] || { err "sin motor: turno_rol.sh"; exit 1; }   # -f: lo invocamos por bash (lupa Opus)
    ls "$TURNOS_DIR"/*.yaml >/dev/null 2>&1 || { err "ningún rol registrado en $TURNOS_DIR"; exit 1; }
    local r
    for r in "${SQUAD[@]:-}"; do                            # squad: solo sillas que EXISTEN
        [ -z "$r" ] && continue
        [[ "$r" =~ ^[a-z0-9_-]+$ ]] || { err "rol raro en el squad: $r"; exit 2; }
        [ -f "$TURNOS_DIR/$r.yaml" ] || { err "el squad pide una silla que no existe: $r"; exit 2; }
    done
    # 🔒 ANTI-SOLAPE (estudio 15:46 · encargo perpetuo): un pleno MANUAL no pisa un ciclo en
    #    marcha — patrón mosaic.sh:199. Ocupado → ceder el paso (exit 0: el perpetuo reintenta).
    #    Lanzado DESDE ciclo.sh (MOSAIC_PLENO=1) el padre ya sostiene el lock: no se re-toma.
    if [ -z "${MOSAIC_EN_ORQUESTADOR:-}" ] && [ -z "$DRYFLAG" ] && [ -f "$BASE/lock.sh" ]; then
        export LOCK_BASE="${LOCK_BASE:-$BASE/data}"
        # shellcheck disable=SC1091
        source "$BASE/lock.sh"
        tomar_lock orquestador || { log "hay un ciclo/aprendizaje en marcha — el pleno cede el paso (reintenta en el próximo punto seguro)"; exit 0; }
        trap 'soltar_locks 2>/dev/null || true' EXIT
        export MOSAIC_EN_ORQUESTADOR=1
    fi
}

ejecutar() {
    local ok=0 mal=0 rol y salida
    if [ "${#SQUAD[@]}" -gt 0 ]; then
        log "PLENO $([ -n "$DRYFLAG" ] && echo '(dry) ')— SQUAD: ${SQUAD[*]} (la cadencia sigue mandando)"
    else
        log "PLENO $([ -n "$DRYFLAG" ] && echo '(dry) ')— sillas: $(ls "$TURNOS_DIR"/*.yaml | wc -l | tr -d ' ')"
    fi
    for y in "$TURNOS_DIR"/*.yaml; do
        rol="$(basename "$y" .yaml)"
        if [ "${#SQUAD[@]}" -gt 0 ]; then
            local en_squad=0 s
            for s in "${SQUAD[@]}"; do [ "$s" = "$rol" ] && en_squad=1 && break; done
            [ "$en_squad" = 1 ] || continue
        fi
        log "── turno de «${rol}» ──"
        if salida="$(MOSAIC_BASE="$BASE" bash "$BASE/turno_rol.sh" "$rol" $DRYFLAG 2>&1)"; then
            ok=$((ok + 1))
            printf '%s\n' "$salida" | tail -2
        else
            mal=$((mal + 1))
            err "«${rol}» falló (el pleno sigue):"
            printf '%s\n' "$salida" | tail -2 >&2
        fi
    done
    if [ "$PORTAVOZ" = 1 ] && [ -x "$BASE/autodiagnosis.sh" ] && [ -z "$DRYFLAG" ]; then
        log "── cierra el PORTAVOZ (autodiagnosis) ──"
        MOSAIC_BASE="$BASE" bash "$BASE/autodiagnosis.sh" 2>&1 | tail -1 || err "el portavoz no pudo hablar (el pleno ya valió)"
    fi
    log "pleno terminado: ${ok} turnos bien · ${mal} con fallo$( [ "$mal" -gt 0 ] && printf ' (revisa arriba)')"
    [ "$mal" = 0 ]
}

validar
ejecutar
