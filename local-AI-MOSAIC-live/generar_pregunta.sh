#!/bin/bash
# 🎲 =====================================================================
# 🎲 MOSAIC — generador de preguntas (3 voces) -> ingesta automática
# 🎲 Tres fuentes generan preguntas aleatorias y cada una se pasa a mosaic:
# 🎲   1) Phi-4-mini local (llama-cli, plantilla Phi a mano — 2.5G, decisión Gustavo 4-jul)
# 🎲   2) Qwen3-14B server (PRINCIPAL 8092; proxy 8080 si existe) — ⚔️ 4-jul: EL 24B JAMÁS
# 🎲   3) Unholy-13B       (proxy 8081 -> directo 8091 si el proxy está caído)
# 🎲 Hace cd, abre/cierra el entorno py, asegura el cluster y avisa cuando
# 🎲 algo se va a SEGUNDO PLANO.  Uso:  ./generar_pregunta.sh [RONDAS]  (def. 1)
# 🎲 =====================================================================
set -euo pipefail

# --- rutas / endpoints literales (tu entorno) --------------------------
HOME_USER="${HOME_USER:-$HOME}"
MOSAIC_DIR="$HOME_USER/Mosaic_privado"
LLAMA_CLI="$HOME_USER/modelo/llama.cpp/build/bin/llama-cli"
# 🐣 4-jul (decisión de Gustavo): la voz LOCAL = Phi-4-mini (2.5G — cabe SIEMPRE junto a la
# flota; el Qwen3 local cargaba 9G APARTE de los 44 en danza: la clase de fuego del día 3).
_PHI4_GGUF="$(ls "$HOME_USER"/modelo/modelos_grandes/phi4-mini/*.gguf 2>/dev/null | head -1 || true)"
MODELO="${MODELO_LOCAL:-$_PHI4_GGUF}"
MOSAIC_SH="$MOSAIC_DIR/mosaic.sh"
COLA_SH="$MOSAIC_DIR/cola.sh"
PAUSA_FLAG="$MOSAIC_DIR/data/pausa.flag"   # el vigía la levanta si el MacBook está a tope
LLAMA_LAUNCH="$HOME_USER/cluster/lanzar_cluster.sh"
# ⚔️ 4-jul: el 8090 del MacBook está MUERTO (vive en el MINI como juez) → chequeo y directo al 8092.
CLUSTER_URL="${MOSAIC_LLM_BASE_URL:-http://127.0.0.1:8092/v1}"   # para el chequeo (principal)
PROXY_PRINCIPAL="${PROXY_PRINCIPAL:-${PROXY_24B:-http://127.0.0.1:8080/v1}}" ; DIRECT_PRINCIPAL="${MOSAIC_LLM_BASE_URL:-http://127.0.0.1:8092/v1}"
PROXY_13B="${PROXY_13B:-http://127.0.0.1:8081/v1}" ; DIRECT_13B="http://127.0.0.1:8091/v1"
CLUSTER_LOG="$MOSAIC_DIR/logs/cluster.auto.log"
INSTR="Inventa UNA sola pregunta breve, original y curiosa, de cualquier tema (puede ser absurda o divertida). Responde solo con la pregunta, sin comillas ni numeracion."
# 🧭 FASE 6: si el gobernador pide ejercitar dormidas, sesga la pregunta (rotando, un cursor)
EJERCITAR_TXT="$MOSAIC_DIR/data/ejercitar.txt"
if [ -s "$EJERCITAR_TXT" ]; then
    _ej_n="$(grep -cve '^[[:space:]]*$' "$EJERCITAR_TXT" 2>/dev/null || echo 0)"
    if [ "${_ej_n:-0}" -gt 0 ]; then
        _ej_cur="$MOSAIC_DIR/data/ejercitar.cursor"
        _ej_i=0; [ -f "$_ej_cur" ] && _ej_i="$(cat "$_ej_cur" 2>/dev/null || echo 0)"
        [[ "$_ej_i" =~ ^[0-9]+$ ]] || _ej_i=0
        _ej_cap="$(grep -ve '^[[:space:]]*$' "$EJERCITAR_TXT" | sed -n "$(( _ej_i % _ej_n + 1 ))p")"
        echo $(( (_ej_i + 1) % _ej_n )) > "$_ej_cur"
        [ -n "$_ej_cap" ] && INSTR="Inventa UNA sola pregunta breve y concreta que ejercite la capacidad «${_ej_cap}» (una petición que la necesite). Responde solo con la pregunta, sin comillas ni numeracion."
    fi
fi
# Con llama-cli -no-cnv la plantilla embebida NO se aplica → se escribe a mano. Phi-4-mini
# habla formato Phi (<|user|>…<|end|>) y NO piensa → fuera el /no_think (aquel freno era de Qwen3).
PROMPT_LOCAL=$'<|system|>Generas exactamente UNA pregunta. Nada más.<|end|><|user|>'"$INSTR"$'<|end|><|assistant|>'

# --- salida limpia de mosaic.sh (silencia el ruido del reranker) -------
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TRANSFORMERS_VERBOSITY=error
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TQDM_DISABLE=1
export PYTHONUNBUFFERED=1

# --- knobs -------------------------------------------------------------
VECES="${1:-1}"                              # nº de RONDAS (cada ronda = hasta 3 preguntas)
ESPERA_CLUSTER="${ESPERA_CLUSTER:-120}"      # s máximos esperando arranque del cluster
MARGEN="${MARGEN_CLUSTER:-3}"                # s extra tras verlo vivo
AUTO_CLUSTER="${MOSAIC_AUTO_CLUSTER:-1}"     # 0 = no tocar el cluster
DESTINO="${DESTINO:-mosaic}"                 # mosaic = ejecuta ya · cola = encola (fábrica)
USAR_LOCAL="${USAR_LOCAL:-1}"                # 1) Phi-4-mini local por llama-cli (2.5G: cabe siempre; voz distinta del server)
USAR_PRINCIPAL="${USAR_PRINCIPAL:-${USAR_24B:-1}}"   # 2) principal Qwen3-14B@8092 (alias legado: USAR_24B)
USAR_13B="${USAR_13B:-1}"                    # 3) Unholy-13B  (proxy/directo)
MOSAIC_USE_WIKIRAG_VENV="${MOSAIC_USE_WIKIRAG_VENV:-1}"
CLUSTER_LANZADO=0
VENV="$MOSAIC_DIR/venv"
TMP_DIR="$(mktemp -d)"

# shellcheck disable=SC1091
source "$MOSAIC_DIR/colores.sh" 2>/dev/null || true
log()   { printf '%s[%s] [INFO]%s  %s\n' "${FASE_COLOR:-${C_VERDE:-}}" "$(date '+%H:%M:%S')" "${C_RESET:-}" "$*"; }
err()   { printf '%s[%s] [ERROR]%s %s\n' "${C_ROJO:-}" "$(date '+%H:%M:%S')" "${C_RESET:-}" "$*" >&2; }
aviso() { printf '[%s] [⚠️  2º PLANO] %s\n' "$(date '+%H:%M:%S')" "$*" >&2; }

# --- limpieza: desactiva el venv y borra temporales (NO mata el cluster) -
cleanup() {
    command -v deactivate >/dev/null 2>&1 && deactivate || true
    rm -rf "$TMP_DIR" 2>/dev/null || true
    log "Entorno desactivado y temporales limpiados."
}
trap cleanup EXIT

# --- entorno py: el de wikirag si existe; si no, uno local con numpy ----
activar_venv() {
    if [ "$MOSAIC_USE_WIKIRAG_VENV" = "1" ] && [ -d "$HOME_USER/wikirag/venv" ]; then
        # shellcheck disable=SC1091
        source "$HOME_USER/wikirag/venv/bin/activate"
        log "venv: el de wikirag."
        return 0
    fi
    [ -d "$VENV" ] || { log "Creando venv en $VENV..."; python3 -m venv "$VENV"; }
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    python3 -c 'import numpy' 2>/dev/null || { log "Instalando numpy/pyyaml..."; pip install -q numpy pyyaml; }
}

# --- normaliza la salida del modelo a una sola línea limpia ------------
limpiar() {
    tr -d '\r' \
    | sed -e 's/<|[^|]*|>//g' -e 's/\[end of text\]//g' -e 's#</s>##g' -e 's/^<s>//' -e 's/###.*$//' \
          -e 's#<think>##g' -e 's#</think>##g' \
    | tr '\n' ' ' \
    | sed -e 's/  */ /g' -e 's/^ *//' -e 's/ *$//'
}

# --- validaciones ------------------------------------------------------
validar() {
    [[ "$VECES" =~ ^[0-9]+$ ]] || { err "RONDAS debe ser un numero: $VECES"; exit 1; }
    command -v curl >/dev/null 2>&1 || { err "falta curl"; exit 1; }
    [ "$((USAR_LOCAL + USAR_PRINCIPAL + USAR_13B))" -ge 1 ] || { err "no hay ningun generador activo"; exit 1; }
    [ -x "$MOSAIC_SH" ] || { err "mosaic.sh no existe o no es ejecutable: $MOSAIC_SH"; exit 1; }
    if [ "$USAR_LOCAL" = "1" ]; then
        [ -x "$LLAMA_CLI" ] || { err "llama-cli no existe/ejecutable: $LLAMA_CLI"; exit 1; }
        [ -r "$MODELO" ]    || { err "modelo no existe/legible: $MODELO"; exit 1; }
    fi
    if [ "$USAR_PRINCIPAL" = "1" ] || [ "$USAR_13B" = "1" ]; then
        command -v python3 >/dev/null 2>&1 || { err "falta python3 (para los proxies)"; exit 1; }
    fi
}

# --- cluster: ¿responde el principal? ----------------------------------
cluster_vivo() { curl -s -m 3 "$CLUSTER_URL/models" >/dev/null 2>&1; }

# Asegura el cluster. Idempotente. Si lo lanza, AVISA de que va a 2º plano.
asegurar_cluster() {
    [ "$AUTO_CLUSTER" = "1" ] || return 0
    cluster_vivo && return 0
    if [ "$CLUSTER_LANZADO" = "0" ]; then
        [ -x "$LLAMA_LAUNCH" ] || { err "cluster caído y no encuentro $LLAMA_LAUNCH"; return 1; }
        aviso "Lanzo el CLUSTER en SEGUNDO PLANO (nohup): $LLAMA_LAUNCH"
        aviso "Quedará VIVO al terminar. Para pararlo:  pkill -f lanzar_cluster   (log: $CLUSTER_LOG)"
        mkdir -p "$(dirname "$CLUSTER_LOG")"
        nohup "$LLAMA_LAUNCH" subir >"$CLUSTER_LOG" 2>&1 &   # 4-jul: el lanzador v3 exige el modo
        CLUSTER_LANZADO=1
    fi
    log "Esperando a que el cluster responda (máx ${ESPERA_CLUSTER}s)..."
    local t=0
    until cluster_vivo; do
        sleep 3; t=$((t + 3))
        [ "$t" -ge "$ESPERA_CLUSTER" ] && { err "cluster sin respuesta tras ${t}s (ver $CLUSTER_LOG)"; return 1; }
    done
    log "Cluster arriba (${t}s). Espero ${MARGEN}s de margen."
    sleep "$MARGEN"
}

# --- generador 1: mythomax local (stdout=pregunta; telemetria a log) ---
generar_local() {
    local raw_log="$TMP_DIR/llama.log"
    # OJO: NADA de --log-disable (en tu build silencia tambien la generacion).
    "$LLAMA_CLI" -m "$MODELO" -p "$PROMPT_LOCAL" \
        -n 48 -c 2048 --temp 1.0 --top-p 0.95 \
        -no-cnv --no-display-prompt \
        2>"$raw_log" | limpiar
}

# --- generador HTTP (OpenAI-compatible) para un endpoint ---------------
generar_http() {
    local base="$1" raw_log="$TMP_DIR/http.log" body resp
    body="$(python3 -c 'import json,sys; print(json.dumps({"model":"local","messages":[{"role":"user","content":sys.argv[1]}],"temperature":1.0,"top_p":0.95,"max_tokens":60}))' "$INSTR")"
    resp="$(curl -s -m 90 "$base/chat/completions" -H 'Content-Type: application/json' -d "$body" 2>"$raw_log")" || return 1
    printf '%s' "$resp" | python3 -c 'import sys,json
try:
    d=json.load(sys.stdin); sys.stdout.write(d["choices"][0]["message"]["content"])
except Exception as e:
    sys.stderr.write("parse %s\n"%e)' 2>>"$raw_log" | limpiar
}

# --- generador 2/3: intenta el proxy; si falla/vacío, cae al directo ----
generar_modelo() {
    local primary="$1" fallback="$2" etiqueta="$3" out
    out="$(generar_http "$primary" || true)"
    if [ -z "${out// /}" ]; then
        err "[$etiqueta] proxy caído/vacío ($primary) -> uso DIRECTO $fallback (sin mejora de prompts)"
        out="$(generar_http "$fallback" || true)"
    fi
    printf '%s' "$out"
}

# --- pasa una pregunta a mosaic (asegurando cluster antes) -------------
procesar() {
    local etiqueta="$1" pregunta="$2"
    if [ -z "${pregunta// /}" ]; then
        err "[$etiqueta] pregunta vacía, la salto (no lanzo mosaic con argumento vacío)."
        return 0
    fi
    log "[$etiqueta] 🎯 $pregunta"
    if [ "$DESTINO" = "cola" ]; then
        "$COLA_SH" add "$pregunta" "$etiqueta"   # FÁBRICA: encola en vez de ejecutar
        return 0
    fi
    while [ -f "$PAUSA_FLAG" ]; do log "[$etiqueta] ⏸️ vigía: MacBook a tope, espero 30s..."; sleep 30; done
    if ! asegurar_cluster; then
        err "[$etiqueta] cluster no disponible; no la paso a mosaic."
        return 0
    fi
    MOSAIC_FUENTE="$etiqueta" "$MOSAIC_SH" "$pregunta"   # registra QUÉ modelo generó la pregunta
}

# --- main --------------------------------------------------------------
cd "$MOSAIC_DIR" || { err "no puedo cd a $MOSAIC_DIR"; exit 1; }
activar_venv
validar
log "Generadores: local=$USAR_LOCAL  principal=$USAR_PRINCIPAL  13B=$USAR_13B   ·   rondas=$VECES"
# Los proxies necesitan el cluster YA para generar -> lo aseguramos de inicio.
if [ "$USAR_PRINCIPAL" = "1" ] || [ "$USAR_13B" = "1" ]; then
    asegurar_cluster || err "sigo igualmente; los modelos del cluster podrían fallar."
fi
for i in $(seq 1 "$VECES"); do
    log "=========== Ronda $i/$VECES ==========="
    if [ "$USAR_LOCAL" = "1" ]; then procesar "local-phi4mini" "$(generar_local || true)"; fi
    if [ "$USAR_PRINCIPAL" = "1" ]; then procesar "Qwen3-14B" "$(generar_modelo "$PROXY_PRINCIPAL" "$DIRECT_PRINCIPAL" "Qwen3-14B" || true)"; fi
    if [ "$USAR_13B"   = "1" ]; then procesar "Unholy-13B"      "$(generar_modelo "$PROXY_13B" "$DIRECT_13B" "Unholy-13B"  || true)"; fi
done
log "Hecho (todas las rondas)."
