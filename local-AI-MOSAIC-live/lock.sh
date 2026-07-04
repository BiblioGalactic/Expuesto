#!/bin/bash
# 🔒 lock.sh — lock PORTABLE (mkdir atómico, con caducidad). Evita que dos
#    orquestadores/consolidar se pisen (lost-update del state.json, doble cluster).
#    Uso:   source lock.sh ; tomar_lock orquestador || exit 1 ; trap soltar_locks EXIT
LOCK_BASE="${LOCK_BASE:-$HOME/Mosaic_privado/data}"
LOCK_MAXEDAD="${LOCK_MAXEDAD:-7200}"   # s; un lock más viejo que esto se considera muerto y se roba
LOCKS_TOMADOS=()

tomar_lock() {
    local nombre="$1" ld="$LOCK_BASE/.lock_$1"
    mkdir -p "$LOCK_BASE" 2>/dev/null || true
    if [ -d "$ld" ]; then
        local m edad
        m="$(stat -c %Y "$ld" 2>/dev/null || stat -f %m "$ld" 2>/dev/null || echo 0)"
        [[ "$m" =~ ^[0-9]+$ ]] || m=0
        edad=$(( $(date +%s) - m ))
        if [ "$edad" -gt "$LOCK_MAXEDAD" ]; then
            echo "[lock] '$nombre' caducado (${edad}s, proceso muerto) -> lo robo" >&2
            rm -rf "$ld"
        fi
    fi
    if mkdir "$ld" 2>/dev/null; then
        echo "$$" > "$ld/pid"
        LOCKS_TOMADOS+=("$ld")
        return 0
    fi
    echo "[lock] '$nombre' YA en marcha (PID $(cat "$ld/pid" 2>/dev/null || echo '?')). No arranco dos a la vez." >&2
    return 1
}

soltar_locks() { for l in "${LOCKS_TOMADOS[@]:-}"; do [ -n "$l" ] && rm -rf "$l" 2>/dev/null; done; }
