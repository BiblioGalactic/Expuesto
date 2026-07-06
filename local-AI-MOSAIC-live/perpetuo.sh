#!/bin/bash
# ♾️ =====================================================================
# ♾️ PERPETUO v1 — plenos "cada X" sin fin (spec Opus 15:41 · estudio Fable 15:46
# ♾️   · orden Gustavo 5-jul). Un bucle while+sleep que dispara pleno.sh: la
# ♾️   CADENCIA por rol decide quién habla (quien habló, calla) y el LOCK del
# ♾️   orquestador evita el solape (pleno.sh cede el paso si hay ciclo en marcha
# ♾️   y reintenta en la vuelta siguiente — el punto seguro manda).
# ♾️
# ♾️ ⚠️  PRERREQUISITO DURO (Opus 15:41): NO encenderlo hasta que un pleno se lea
# ♾️ ⚠️  LIMPIO tras el fix del eco — si no, es una máquina de ruido perpetuo.
# ♾️ ⚠️  Este script NACE APAGADO: pide confirmación (SI) salvo --si.
# ♾️
# ♾️   Freno de mano LIMPIO (sin Ctrl+C): touch data/senales/PARAR_PERPETUO
# ♾️     → para tras el pleno en curso y consume la señal (trazado en el log).
# ♾️   Respeta data/pausa.flag del vigía (MacBook a tope → espera, no dispara).
# ♾️   PID guard: data/.perpetuo.pid — UNO a la vez (poll-primero, lección zombi).
# ♾️ Uso:  ./perpetuo.sh [--si]
# ♾️   env: PLENO_CADA_MIN (60) · PERPETUO_MAX (0 = sin tope de plenos) ·
# ♾️        PERPETUO_PORTAVOZ=0 (pleno sin portavoz)
# ♾️ =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
PLENO="$BASE/pleno.sh"
PIDF="$BASE/data/.perpetuo.pid"
SENALES="$BASE/data/senales"
PARAR="$SENALES/PARAR_PERPETUO"
PAUSA_FLAG="$BASE/data/pausa.flag"
CADA_MIN="${PLENO_CADA_MIN:-60}"
MAX="${PERPETUO_MAX:-0}"

log() { printf '[%s] ♾️  %s\n' "$(date '+%F %T')" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date '+%F %T')" "$*" >&2; }

# limpieza SOLO de lo propio: si el pidfile es de OTRO perpetuo vivo (rechazo del guard),
# tocarlo sería matarle el candado — la lección del zombi, versión pidfile.
cleanup() {
    if [ "$(cat "$PIDF" 2>/dev/null || true)" = "$$" ]; then
        rm -f "$PIDF" 2>/dev/null || true
        log "perpetuo detenido (pid limpio)."
    fi
}
trap cleanup EXIT
trap 'echo; log "parado por ti (Ctrl+C) — el freno limpio es: touch $PARAR"; exit 0' INT TERM

validar() {
    [ -x "$PLENO" ] || { err "no encuentro pleno.sh ejecutable en $PLENO"; exit 1; }
    [[ "$CADA_MIN" =~ ^[0-9]+$ ]] && [ "$CADA_MIN" -ge 1 ] || { err "PLENO_CADA_MIN raro: $CADA_MIN (minutos, ≥1)"; exit 2; }
    [[ "$MAX" =~ ^[0-9]+$ ]] || { err "PERPETUO_MAX raro: $MAX"; exit 2; }
    mkdir -p "$SENALES" "$(dirname "$PIDF")"
    # PID guard, poll-primero (la lección del zombi): un pid muerto no bloquea, se roba
    if [ -f "$PIDF" ]; then
        local viejo
        viejo="$(cat "$PIDF" 2>/dev/null || echo 0)"
        if [[ "$viejo" =~ ^[0-9]+$ ]] && kill -0 "$viejo" 2>/dev/null; then
            err "ya hay un perpetuo corriendo (PID $viejo) — uno a la vez"; exit 1
        fi
        log "pid huérfano ($viejo, muerto) → lo robo"
    fi
    echo "$$" > "$PIDF"
}

confirmar() {
    [ "${1:-}" = "--si" ] && return 0
    echo "♾️  =============================================================="
    echo "♾️   PERPETUO: pleno de la orquesta cada ${CADA_MIN} min, SIN FIN"
    echo "♾️   (tope: $([ "$MAX" -gt 0 ] && echo "$MAX plenos" || echo 'ninguno'))."
    echo "♾️   Prerrequisito de Opus: un pleno LIMPIO tras el fix del eco."
    echo "♾️   Freno limpio: touch data/senales/PARAR_PERPETUO · Ctrl+C también vale."
    echo "♾️  =============================================================="
    if [ ! -t 0 ]; then
        err "sin terminal interactiva: lanza con --si para confirmar."; exit 1
    fi
    printf '¿Encender el perpetuo? Escribe SI en mayúsculas: '
    local resp; read -r resp
    [ "$resp" = "SI" ] || { echo "cancelado (no escribiste SI)."; exit 0; }
}

ejecutar() {
    local i=0 t=0
    log "perpetuo ENCENDIDO · pleno cada ${CADA_MIN} min · tope: $([ "$MAX" -gt 0 ] && echo "$MAX" || echo 'sin tope')"
    while :; do
        # 🛑 freno de mano: la señal se CONSUME (a un lado, con sello de hora — trazable)
        if [ -f "$PARAR" ]; then
            mv "$PARAR" "$PARAR.consumida.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || rm -f "$PARAR"
            log "señal PARAR_PERPETUO → paro limpio tras $i plenos. Hasta la próxima."
            break
        fi
        # 🩺 el vigía manda: MacBook a tope → este NO es momento de pleno
        if [ -f "$PAUSA_FLAG" ]; then
            log "pausa.flag del vigía ($(head -c 60 "$PAUSA_FLAG" 2>/dev/null || true)) — espero 60s"
            sleep 60
            continue
        fi
        i=$((i + 1))
        log "═══ pleno $i$([ "$MAX" -gt 0 ] && echo "/$MAX") ═══"
        # pleno.sh toma el lock del orquestador: si hay CICLO en marcha, CEDE (exit 0) y
        # este bucle simplemente reintenta a la próxima — el no-solape es del lock, no mío.
        if PORTAVOZ_ARGS=""; [ "${PERPETUO_PORTAVOZ:-1}" = "0" ] && PORTAVOZ_ARGS="--sin-portavoz"; \
           MOSAIC_BASE="$BASE" bash "$PLENO" $PORTAVOZ_ARGS; then
            log "pleno $i terminado limpio"
        else
            err "pleno $i acabó con fallos (las cartas que entraron, entraron) — sigo"
        fi
        if [ "$MAX" -gt 0 ] && [ "$i" -ge "$MAX" ]; then
            log "tope de $MAX plenos alcanzado → paro."
            break
        fi
        log "duermo ${CADA_MIN} min (freno: touch data/senales/PARAR_PERPETUO)…"
        t=0
        while [ "$t" -lt $((CADA_MIN * 60)) ]; do
            sleep 15
            t=$((t + 15))
            [ -f "$PARAR" ] && break                      # el freno no espera a que acabe la siesta
        done
    done
}

validar
confirmar "${1:-}"
ejecutar
