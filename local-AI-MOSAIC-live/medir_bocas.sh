#!/bin/bash
# 📏 =====================================================================
# 📏 MEDIR_BOCAS — tokens/s REALES con N bocas concurrentes (el dato que
# 📏 exige Opus ANTES de paralelizar la FASE 2: ¿satura la GPU o hay margen?)
# 📏
# 📏 Uso:  ./medir_bocas.sh URL1 [URL2] [URL3] [URL4]
# 📏   FASE A: cada boca SOLA (línea base) · FASE B: TODAS A LA VEZ → veredicto.
# 📏 Ejemplos (con la flota arriba y OCIOSA — no en mitad de un ciclo):
# 📏   ./medir_bocas.sh http://127.0.0.1:8092/v1
# 📏   ./medir_bocas.sh http://127.0.0.1:8092/v1 http://127.0.0.1:8091/v1
# 📏   ./medir_bocas.sh http://localhost:8090/v1 http://localhost:8093/v1
# 📏 =====================================================================
set -euo pipefail

TMP="$(mktemp -d)"
# cleanup mata también los curls en 2º plano: un Ctrl+C a media FASE B ya no deja huérfanos
# escribiendo en un TMP borrado (visto 04-jul 01:11: "No such file or directory" tras ^C).
cleanup() { local j; j="$(jobs -p 2>/dev/null || true)"; [ -n "$j" ] && kill $j 2>/dev/null || true; rm -rf "$TMP"; }
trap cleanup EXIT

log()  { printf '[%s] 📏 %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

MAXTOK="${MEDIR_TOKENS:-200}"
PROMPT="Escribe unas 200 palabras sobre la historia de la navegacion a vela. Solo texto corrido."

validar() {
    [ "$#" -ge 1 ] || { warn "uso: $0 URL1 [URL2] [URL3] [URL4]   (endpoints /v1)"; exit 1; }
    [ "$#" -le 4 ] || { warn "máximo 4 bocas por medición"; exit 1; }
    command -v curl >/dev/null    || { warn "falta curl"; exit 1; }
    command -v python3 >/dev/null || { warn "falta python3"; exit 1; }
    local u
    for u in "$@"; do
        curl -s -m 5 "${u%/}/models" >/dev/null 2>&1 || { warn "no responde: $u (¿flota arriba?)"; exit 1; }
    done
}

# una petición → escribe "predicted_n predicted_per_second" en $2
pedir() {
    local url="$1" out="$2"
    curl -s -m 300 "${url%/}/chat/completions" -H 'Content-Type: application/json' \
      -d "{\"messages\":[{\"role\":\"user\",\"content\":\"$PROMPT\"}],\"max_tokens\":$MAXTOK,\"temperature\":0.7}" 2>/dev/null \
    | python3 -c '
import json, sys
try:
    t = json.load(sys.stdin).get("timings", {})
    print(t.get("predicted_n", 0), round(float(t.get("predicted_per_second", 0)), 1))
except Exception:
    print(0, 0)' > "$out" || printf '0 0\n' > "$out"
}

ejecutar() {
    local urls=("$@") i n tks
    local solas=()
    log "═══ FASE A · cada boca SOLA (línea base · ${MAXTOK} tokens por boca) ═══"
    for i in "${!urls[@]}"; do
        pedir "${urls[$i]}" "$TMP/solo_$i"
        read -r n tks < "$TMP/solo_$i"
        [ "$n" = "0" ] && warn "boca $((i+1)) no devolvió timings (¿cargando aún?) — repite en un minuto"
        solas+=("$tks")
        log "  boca $((i+1)) SOLA        → ${tks} tok/s (${n} tokens) · ${urls[$i]}"
    done
    local t0 t1
    log "═══ FASE B · las ${#urls[@]} boca(s) A LA VEZ ═══"
    t0=$(date +%s)
    for i in "${!urls[@]}"; do pedir "${urls[$i]}" "$TMP/conc_$i" & done
    wait
    t1=$(date +%s)
    local suma_conc=0 suma_sola=0
    for i in "${!urls[@]}"; do
        read -r n tks < "$TMP/conc_$i"
        log "  boca $((i+1)) CONCURRENTE → ${tks} tok/s (${n} tokens)"
        suma_conc=$(python3 -c "print(round($suma_conc + $tks, 1))")
        suma_sola=$(python3 -c "print(round($suma_sola + ${solas[$i]}, 1))")
    done
    log "═══ VEREDICTO ═══"
    log "  suma en solitario : ${suma_sola} tok/s (techo teórico si no compartieran GPU)"
    log "  suma concurrente  : ${suma_conc} tok/s · pared FASE B: $((t1 - t0))s"
    python3 -c "
c, s = float('$suma_conc'), float('$suma_sola')
r = (c / s * 100) if s else 0
v = ('GPU con MARGEN: estas bocas conviven bien' if r >= 75 else
     'saturación PARCIAL: conviven a medias' if r >= 45 else
     'GPU SATURADA: se pisan (más bocas aquí NO aceleran)')
print(f'         rendimiento conjunto = {r:.0f}% del teórico → {v}')"
}

validar "$@"
ejecutar "$@"
log "hecho. (Pasa estos números a la carta: son la llave de la FASE 2 paralela.)"
