#!/bin/bash
# 🩺 =====================================================================
# 🩺 VIGÍA — watchdog de salud del MacBook
# 🩺 Vigila la carga; si lleva demasiado tiempo A TOPE, levanta data/pausa.flag
# 🩺 y el bucle continuo PAUSA la ingesta hasta que se enfría.
# 🩺 Stats LOCALES (córrelo en el MacBook) o por SSH (VIGIA_SSH=user@ip; p.ej.
# 🩺 desde el mini cuando tengas las llaves). Veredicto en lenguaje natural vía el 8B.
# 🩺 Uso:  ./vigia.sh          (bucle; Ctrl+C para parar)
# 🩺 =====================================================================
set -euo pipefail

HOME_USER="${HOME_USER:-$HOME}"
MOSAIC_DIR="$HOME_USER/Mosaic_privado"
FLAG="$MOSAIC_DIR/data/pausa.flag"
SALUD="$MOSAIC_DIR/data/salud.txt"

UMBRAL="${VIGIA_UMBRAL:-85}"          # % de carga = "a tope"
SOSTENIDO="${VIGIA_SOSTENIDO:-120}"   # s seguidos a tope antes de pausar
ENFRIA="${VIGIA_ENFRIA:-30}"          # s por debajo del umbral para quitar la pausa
INTERVALO="${VIGIA_INTERVALO:-15}"    # s entre lecturas
SSH_TARGET="${VIGIA_SSH:-}"           # vacío = local; o user@127.0.0.1 (vigilar desde el mini)
MINI="${MINI_URL:-http://localhost:8090/v1}"
USAR_MINI="${VIGIA_MINI:-1}"          # 1 = pide al 8B una frase de aviso

log() { printf '[%s] [VIGÍA] %s\n' "$(date '+%H:%M:%S')" "$*"; }
trap 'echo; log "Detenido."; exit 0' INT TERM
mkdir -p "$(dirname "$FLAG")"

# carga en % = load1 / nº_cpus * 100   (local con sysctl, o remoto por SSH)
leer_pct() {
    local l1 n raw
    if [ -n "$SSH_TARGET" ]; then
        raw="$(ssh -o ConnectTimeout=4 "$SSH_TARGET" 'sysctl -n vm.loadavg; sysctl -n hw.ncpu' 2>/dev/null)" || return 1
        l1="$(printf '%s\n' "$raw" | sed -n '1p' | awk '{print $2}')"
        n="$(printf '%s\n' "$raw" | sed -n '2p')"
    else
        l1="$(sysctl -n vm.loadavg 2>/dev/null | awk '{print $2}')"
        n="$(sysctl -n hw.ncpu 2>/dev/null)"
    fi
    [ -n "${l1:-}" ] && [ -n "${n:-}" ] || return 1
    awk -v a="$l1" -v b="$n" 'BEGIN{ if(b>0) printf "%d",(a/b)*100; else exit 1 }'
}

# frase de aviso (opcional) vía el 8B del mini -> salud.txt; si no, mensaje plano
veredicto() {
    local pct="$1" segs="$2" msg="MacBook a tope: carga ${pct}% durante ${segs}s."
    if [ "$USAR_MINI" = "1" ] && command -v curl >/dev/null 2>&1; then
        local prompt body r
        prompt="En UNA frase corta avisa de que el MacBook lleva ${segs}s con la CPU al ${pct}% y conviene pausar. Solo la frase."
        body="$(python3 -c 'import json,sys;print(json.dumps({"model":"local","messages":[{"role":"user","content":sys.argv[1]}],"max_tokens":60,"temperature":0.4}))' "$prompt" 2>/dev/null)" || body=""
        if [ -n "$body" ]; then
            r="$(curl -s -m 10 "$MINI/chat/completions" -H 'Content-Type: application/json' -d "$body" 2>/dev/null \
                 | python3 -c 'import sys,json
try:
    print(json.load(sys.stdin)["choices"][0]["message"]["content"].strip())
except Exception:
    pass' 2>/dev/null)" || r=""
            [ -n "$r" ] && msg="$r"
        fi
    fi
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$msg" > "$SALUD"
    printf '%s' "$msg"
}

log "Arrancado. umbral=${UMBRAL}% · sostenido=${SOSTENIDO}s · intervalo=${INTERVALO}s · fuente=$([ -n "$SSH_TARGET" ] && echo "ssh:$SSH_TARGET" || echo local)"
acum=0; bajo=0
while true; do
    pct="$(leer_pct || echo "")"
    if [ -n "$pct" ] && [ "$pct" -ge "$UMBRAL" ]; then
        acum=$((acum + INTERVALO)); bajo=0
        if [ "$acum" -ge "$SOSTENIDO" ] && [ ! -f "$FLAG" ]; then
            v="$(veredicto "$pct" "$acum")"
            echo "$v" > "$FLAG"
            log "⚠️  PAUSA (carga ${pct}%): $v"
        fi
    else
        bajo=$((bajo + INTERVALO)); acum=0
        if [ -f "$FLAG" ] && [ "$bajo" -ge "$ENFRIA" ]; then
            rm -f "$FLAG"
            log "✅ Carga normal (${pct:-?}%). Quito la pausa."
        fi
    fi
    sleep "$INTERVALO"
done
