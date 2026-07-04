#!/bin/bash
# 🧩 =====================================================================
# 🧩 MOSAIC LOCAL — lanzador privado (venv automático)
# 🧩 Compone agentes efímeros y los ejecuta contra tu cluster llama.cpp
# 🧩 =====================================================================
set -euo pipefail

# --- rutas / cluster (privado, tu entorno) -----------------------------
export HOME_USER="${HOME_USER:-$HOME}"
export MOSAIC_DIR="$HOME_USER/Mosaic_privado"
export LLAMA_CLI="$HOME_USER/modelo/llama.cpp/build/bin/llama-cli"
export LLAMA_LAUNCH="$HOME_USER/cluster/lanzar_cluster.sh"

# Endpoints DIRECTOS (sin proxy: MOSAIC ya compone el prompt y no queremos que
# el proxy lo reescriba). Cambia a 8080/8081 si quieres los proxys.
# ⚔️ ORDEN DE GUSTAVO (3-jul): el 24B JAMÁS. La flota es SOLO de medianos.
export MOSAIC_LLM_BASE_URL="${MOSAIC_LLM_BASE_URL:-http://127.0.0.1:8092/v1}"   # Qwen3-14B (principal)
export MOSAIC_LLM_FAST_URL="${MOSAIC_LLM_FAST_URL:-http://127.0.0.1:8091/v1}"   # Unholy 13B (rápido)
export MOSAIC_LLM_LIGHT_URL="${MOSAIC_LLM_LIGHT_URL:-http://127.0.0.1:8091/v1}"  # 13B; el bucle lo manda al mini si está
export MOSAIC_LLM_MODEL="${MOSAIC_LLM_MODEL:-qwen3-14b}"
# 🧑‍⚖️ P-A (3-jul, Gustavo): los 4 roles de la defensa = 4 modelos DISTINTOS → juez = Phi-4-mini@8096
# (demanda: cuarentena.sh lo sube con el lote y lo baja al acabar). Entierra el P1 del 8094 (R1 piensa siempre).
export DEFENSA_URL_JUEZ="${DEFENSA_URL_JUEZ:-http://127.0.0.1:8096/v1}"          # Phi-4-mini (juez de seguridad)
export DEFENSA_MODELO_JUEZ="${DEFENSA_MODELO_JUEZ:-Phi-4-mini}"                     # display + gate /no_think (no es Qwen3)

# 🐟 P-F5 (diseño Opus 00:14 + números de Gustavo 01:05): FASE 2 con VARIAS BOCAS first-to-finish
# sobre las 2 GPUs. LÍMITE DE GUSTAVO: máx 3 bocas en el MacBook (la 4ª casi lo congela — medido).
# 🔥 DESPIERTO por orden de Gustavo (4-jul 02:5x: "id con todo"). Kill-switch: MOSAIC_WORKERS=1.
# Nota: hasta que Unholy hable Alpaca (F1), su boca escala todo al 8092 — funciona, pero sin gracia.
export MOSAIC_EXECUTORS="${MOSAIC_EXECUTORS:-http://127.0.0.1:8092/v1,http://127.0.0.1:8091/v1,http://127.0.0.1:8093/v1,http://localhost:8093/v1}"
export MOSAIC_WORKERS="${MOSAIC_WORKERS:-4}"                          # 4 bocas (3 MacBook + 1 mini) · 1 = secuencial
export MOSAIC_JUECES="${MOSAIC_JUECES:-2}"                            # hilos de juez (el mini lleva --parallel 2)

export MOSAIC_EMBEDDER="${MOSAIC_EMBEDDER:-sentence-transformers}"   # embeddings reales por defecto
export MOSAIC_CAPS_DIR="$MOSAIC_DIR/capabilities"
export MOSAIC_STATE="$MOSAIC_DIR/data/state.json"
export MOSAIC_CONTEXT_CACHE="$MOSAIC_DIR/data/context_cache.json"
export MOSAIC_CONTEXTUALIZE="1"

# --- integración con wikirag (reranker/evaluador) + gate CRAG ---
export MOSAIC_WIKIRAG="$HOME_USER/wikirag"
export MOSAIC_RERANKER="auto"
export MOSAIC_PREFILTER="1"
export MOSAIC_CRAG="1"
export MOSAIC_GAPS="$MOSAIC_DIR/data/huecos.json"
export MOSAIC_HISTORIAL="$MOSAIC_DIR/data/historial.jsonl"   # registra cada uso real
export MOSAIC_PREDICTOR="${MOSAIC_PREDICTOR:-1}"             # P2-6: usa el predictor de tokens si existe data/predictor.json
export MOSAIC_PREDICTOR_PATH="${MOSAIC_PREDICTOR_PATH:-$MOSAIC_DIR/data/predictor.json}"
export MOSAIC_AUTO_CONSOLIDAR="${MOSAIC_AUTO_CONSOLIDAR:-30}" # cada N usos: ciclo completo solo (0 = off)
export MOSAIC_AUTO_GENERAR="${MOSAIC_AUTO_GENERAR:-1}"        # incluir 'generar' en el ciclo auto (0 = off)
export MOSAIC_AB="${MOSAIC_AB:-raw}"                          # A/B siempre: composición vs crudo (off = desactivar)
export MOSAIC_AB_MUESTRA="${MOSAIC_AB_MUESTRA:-5}"            # nº de usos a comparar en el A/B automático
export MOSAIC_USE_WIKIRAG_VENV="${MOSAIC_USE_WIKIRAG_VENV:-1}"

# Modelos: caché-primero SIN red por defecto (ya están descargados). Pon =0 para permitir descarga.
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
# Salida limpia: silencia barras/telemetría del reranker y quita el buffer de stdout
# (así la RESPUESTA DEL MODELO no queda enterrada ni sale toda de golpe al final).
export TRANSFORMERS_VERBOSITY="${TRANSFORMERS_VERBOSITY:-error}"
export HF_HUB_DISABLE_PROGRESS_BARS="${HF_HUB_DISABLE_PROGRESS_BARS:-1}"
export TQDM_DISABLE="${TQDM_DISABLE:-1}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export MOSAIC_EMBED_MODEL="${MOSAIC_EMBED_MODEL:-sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2}"
export MOSAIC_RERANK_MODEL="${MOSAIC_RERANK_MODEL:-cross-encoder/mmarco-mMiniLMv2-L12-H384-v1}"

VENV="$MOSAIC_DIR/venv"
LOG_DIR="$MOSAIC_DIR/logs"
TMP_DIR="$(mktemp -d)"

log() { printf '[%s] [INFO]  %s\n' "$(date '+%H:%M:%S')" "$*"; }
err() { printf '[%s] [ERROR] %s\n' "$(date '+%H:%M:%S')" "$*" >&2; }

# --- limpieza: deactivate del venv + borrar temporales -----------------
# shellcheck disable=SC1091
source "$MOSAIC_DIR/lock.sh" 2>/dev/null || true
cleanup() {
    soltar_locks 2>/dev/null || true
    command -v deactivate >/dev/null 2>&1 && deactivate || true
    rm -rf "$TMP_DIR" 2>/dev/null || true
}
trap cleanup EXIT

# --- venv automático ---------------------------------------------------
activar_venv() {
    if [ "$MOSAIC_USE_WIKIRAG_VENV" = "1" ] && [ -d "$HOME_USER/wikirag/venv" ]; then
        # shellcheck disable=SC1091
        source "$HOME_USER/wikirag/venv/bin/activate"
        log "venv: el de wikirag (sentence-transformers/torch/faiss disponibles)"
        return 0
    fi
    if [ ! -d "$VENV" ]; then
        log "Creando entorno virtual en $VENV..."
        python3 -m venv "$VENV"
    fi
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    if ! python3 -c "import numpy" 2>/dev/null; then
        log "Instalando dependencias (numpy, pyyaml)..."
        pip install -q --upgrade pip >/dev/null 2>&1 || true
        pip install -q numpy pyyaml
    fi
}

# --- validaciones ------------------------------------------------------
validar() {
    [ -f "$MOSAIC_DIR/mosaic.py" ] || { err "No existe $MOSAIC_DIR/mosaic.py"; exit 1; }
    mkdir -p "$LOG_DIR" "$(dirname "$MOSAIC_STATE")" \
             "$MOSAIC_DIR/trash/logs" "$MOSAIC_DIR/trash/backups" \
             "$MOSAIC_DIR/trash/historico" "$MOSAIC_DIR/trash/otros"

    for a in "$@"; do [ "$a" = "--offline" ] && return 0; done   # offline: sin cluster
    local url="$MOSAIC_LLM_BASE_URL"
    for a in "$@"; do [ "$a" = "--fast" ] && url="$MOSAIC_LLM_FAST_URL"; done
    if command -v curl >/dev/null 2>&1 && curl -s -m 3 "$url/models" >/dev/null 2>&1; then
        log "Cluster OK en $url"
    else
        err "Cluster sin respuesta en $url"
        err "Lánzalo con: $LLAMA_LAUNCH   (o usa --offline para probar sin red)"
    fi
}

# --- ejecución (stdout/stderr separados, con timestamp en el nombre) ---
ejecutar() {
    local day; day="$(date '+%Y%m%d')"
    log "Lanzando MOSAIC..."
    python3 "$MOSAIC_DIR/mosaic.py" "$@" \
        > >(tee -a "$LOG_DIR/mosaic.$day.out.log") \
        2> >(tee -a "$LOG_DIR/mosaic.$day.err.log" >&2)
}

# --- aviso de mantenimiento: NADA en segundo plano. Si toca, te avisa y TÚ decides ---
#     Política: cuando toca curar se cura, cuando toca aprender se aprende — todo
#     EXPLÍCITO por terminal. Esta función solo recuerda; no lanza trabajo oculto.
auto_mantenimiento() {
    local umbral="${MOSAIC_AUTO_CONSOLIDAR:-0}"
    [ "$umbral" -gt 0 ] 2>/dev/null || return 0
    [ -f "$MOSAIC_HISTORIAL" ] || return 0
    local pend; pend="$(wc -l < "$MOSAIC_HISTORIAL" 2>/dev/null | tr -d ' ')"
    [ "${pend:-0}" -ge "$umbral" ] 2>/dev/null || return 0
    log "📋 Tienes $pend usos sin consolidar. Cuando quieras, EN TERMINAL:"
    log "     ./mosaic.sh generar      (cubre huecos)   ·   ./mosaic.sh consolidar   (aprende + poda)"
}

# --- main: un solo mando con subcomandos --------------------------------
if [ "$#" -eq 0 ]; then
    cat <<EOF
Uso (un solo mando):
  ./mosaic.sh "tu petición"          # compone, ejecuta y registra el uso
  ./mosaic.sh aprender [N]           # entrena con la batería (N ciclos, def. 1)
  ./mosaic.sh consolidar             # aprende de tu uso real (historial)
  ./mosaic.sh generar                # crea capacidades nuevas desde los huecos
  ./mosaic.sh entrenar-predictor     # reentrena el predictor de tokens (features→tokens reales)
  ./mosaic.sh ciclo [N]              # ciclo COMPLETO por tandas (fábrica→ingesta→juicio→aprender)
  ./mosaic.sh server [PUERTO]        # API OpenAI-compatible (def. 8077)
  ./mosaic.sh --offline "prueba"     # sin red (mock)   ·   ./mosaic.sh --selftest
EOF
    exit 0
fi

TS="$(date '+%Y%m%d_%H%M%S')"
SUB="${1:-}"
ES_TAREA=0
case "${1:-}" in
    aprender)
        shift; CIC=1
        if [[ "${1:-}" =~ ^[0-9]+$ ]]; then CIC="$1"; shift; fi
        ARGS=(--aprender --ciclos "$CIC" --out "$MOSAIC_DIR/resultados/aprendizaje_$TS" "$@") ;;
    consolidar)
        shift; ARGS=(--consolidar --out "$MOSAIC_DIR/resultados/consolidado_$TS" "$@") ;;
    generar)
        shift; ARGS=(--generar-capacidades --out "$MOSAIC_DIR/resultados/generar_$TS" "$@") ;;
    entrenar-predictor)
        shift; ARGS=(--entrenar-predictor "$@") ;;          # P2-6: reentrena el predictor de tokens (solo datos, sin cluster)
    curar)
        shift; ARGS=(--curar-existentes --out "$MOSAIC_DIR/resultados/curar_$TS" "$@") ;;
    ciclo)
        shift
        # 🖥️ R2-extra (Gustavo): log VIVO del ciclo para la consola (monitor.py, vista [V]).
        # script(1) de macOS captura TODO (colores incluidos) SIN robarle la tty al ciclo —
        # tu terminal se ve igual; el fichero se trunca en cada arranque (= "el ciclo ACTUAL").
        # MOSAIC_LOG_VIVO=0 = comportamiento de siempre. Solo Darwin (el script de Linux es otro).
        if [ "${MOSAIC_LOG_VIVO:-1}" = "1" ] && [ "$(uname)" = "Darwin" ] && command -v script >/dev/null 2>&1; then
            mkdir -p "$MOSAIC_DIR/logs"
            exec script -q "$MOSAIC_DIR/logs/ciclo_vivo.log" "$MOSAIC_DIR/ciclo.sh" "$@"
        fi
        exec "$MOSAIC_DIR/ciclo.sh" "$@" ;;   # ciclo COMPLETO por tandas, en terminal
    server)
        shift
        if [[ "${1:-}" =~ ^[0-9]+$ ]]; then ARGS=(--server --port "$1"); shift; else ARGS=(--server); fi
        ARGS+=("$@") ;;
    *)
        ARGS=("$@"); ES_TAREA=1 ;;     # una tarea normal -> cuenta para auto-consolidar
esac

# LOCK: consolidar/generar/curar/aprender no corren a la vez que un ciclo (lost-update).
case "$SUB" in
    consolidar|generar|curar|aprender)
        [ -z "${MOSAIC_EN_ORQUESTADOR:-}" ] && { tomar_lock orquestador || { err "Ya hay un ciclo/aprendizaje en marcha; no lanzo otro."; exit 1; }; } ;;
esac

activar_venv
validar "${ARGS[@]}"
ejecutar "${ARGS[@]}"
[ "$ES_TAREA" = "1" ] && auto_mantenimiento
log "Hecho."
