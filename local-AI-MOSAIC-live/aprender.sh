#!/bin/bash
# 🧠 =====================================================================
# 🧠 MOSAIC — aprendizaje automático a escala
# 🧠 Compone, ejecuta, se autojuzga con el cluster y REALIMENTA los scores
# 🧠 y el grafo. El estado es acumulativo: cada ejecución sigue aprendiendo.
# 🧠 Uso:  ./aprender.sh [CICLOS] [flags...]    (CICLOS por defecto = 1)
# 🧠 =====================================================================
set -euo pipefail

export HOME_USER="${HOME_USER:-$HOME}"
export MOSAIC_DIR="$HOME_USER/Mosaic_privado"
# ⚔️ 4-jul: EL 24B JAMÁS y el 8090 del MacBook está MUERTO (el 8090 vive en el MINI como juez).
# Flota vigente: principal = Qwen3-14B@8092 · ligero = Unholy-13B@8091. MODEL con "qwen3" es
# OBLIGATORIO: el gate /no_think de mosaic.py mira ese nombre (sin él, asfixia del pensador).
export MOSAIC_LLM_BASE_URL="${MOSAIC_LLM_BASE_URL:-http://127.0.0.1:8092/v1}"   # principal (Qwen3-14B)
export MOSAIC_LLM_FAST_URL="${MOSAIC_LLM_FAST_URL:-http://127.0.0.1:8091/v1}"   # 13B (ejecutor si --fast)
export MOSAIC_LLM_LIGHT_URL="${MOSAIC_LLM_LIGHT_URL:-http://127.0.0.1:8091/v1}" # 13B: trabajos ligeros (C1)
export MOSAIC_LLM_MODEL="${MOSAIC_LLM_MODEL:-qwen3-14b}"
export MOSAIC_EMBEDDER="${MOSAIC_EMBEDDER:-sentence-transformers}"   # por defecto, embeddings reales
export MOSAIC_CAPS_DIR="$MOSAIC_DIR/capabilities"
export MOSAIC_STATE="$MOSAIC_DIR/data/state.json"
export MOSAIC_CONTEXT_CACHE="$MOSAIC_DIR/data/context_cache.json"
export MOSAIC_CONTEXTUALIZE="1"

# --- integración con wikirag (reranker/evaluador) + gate CRAG ---
export MOSAIC_WIKIRAG="$HOME_USER/wikirag"   # de aquí salen reranker/evaluador maduros
export MOSAIC_RERANKER="auto"                # auto: cross-encoder de wikirag si está
export MOSAIC_PREFILTER="1"                  # pre-filtro heurístico antes del juez
export MOSAIC_CRAG="1"                       # gate de calidad de recuperación + huecos
export MOSAIC_GAPS="$MOSAIC_DIR/data/huecos.json"
export MOSAIC_HISTORIAL="$MOSAIC_DIR/data/historial.jsonl"   # cola de uso real (mosaic.sh)
# Por defecto usa el venv de wikirag (trae sentence-transformers/torch/faiss);
# si no existe, cae al venv local. Pon =0 para forzar el local.
export MOSAIC_USE_WIKIRAG_VENV="${MOSAIC_USE_WIKIRAG_VENV:-1}"

# A/B integrado: tras aprender, compara composición vs 'raw' (sin MOSAIC) en una
# muestra. MOSAIC_AB=raw|<url-modelo>  ·  MOSAIC_AB_MUESTRA=6 (0 = desactivar, all = todas)
export MOSAIC_AB="${MOSAIC_AB:-raw}"
export MOSAIC_AB_MUESTRA="${MOSAIC_AB_MUESTRA:-6}"

# Modelos desde la caché local, sin red (ya descargados una vez). Pon HF_HUB_OFFLINE=0
# si alguna vez quieres permitir una descarga nueva.
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}"        # caché-primero; descarga si falta (arregla el fallo del reranker)
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-0}"
export MOSAIC_EMBED_MODEL="${MOSAIC_EMBED_MODEL:-sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2}"
export MOSAIC_RERANK_MODEL="${MOSAIC_RERANK_MODEL:-cross-encoder/mmarco-mMiniLMv2-L12-H384-v1}"

VENV="$MOSAIC_DIR/venv"
TMP_DIR="$(mktemp -d)"
MODO="aprender"
if [ "${1:-}" = "consolidar" ]; then MODO="consolidar"; shift; fi   # aprende del uso real
CICLOS="${1:-1}"; [ "$#" -gt 0 ] && shift || true
if [ "$MODO" = "consolidar" ]; then
    OUT="$MOSAIC_DIR/resultados/consolidado_$(date '+%Y%m%d_%H%M%S')"
else
    OUT="$MOSAIC_DIR/resultados/aprendizaje_$(date '+%Y%m%d_%H%M%S')"
fi

log() { printf '[%s] [INFO]  %s\n' "$(date '+%H:%M:%S')" "$*"; }
err() { printf '[%s] [ERROR] %s\n' "$(date '+%H:%M:%S')" "$*" >&2; }

cleanup() {
    command -v deactivate >/dev/null 2>&1 && deactivate || true
    rm -rf "$TMP_DIR" 2>/dev/null || true
}
trap cleanup EXIT

activar_venv() {
    if [ "$MOSAIC_USE_WIKIRAG_VENV" = "1" ] && [ -d "$HOME_USER/wikirag/venv" ]; then
        # shellcheck disable=SC1091
        source "$HOME_USER/wikirag/venv/bin/activate"
        log "venv: el de wikirag (sentence-transformers/torch/faiss disponibles)"
        return 0
    fi
    [ -d "$VENV" ] || { log "Creando venv en $VENV..."; python3 -m venv "$VENV"; }
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    python3 -c "import numpy" 2>/dev/null || { log "Instalando numpy/pyyaml..."; pip install -q numpy pyyaml; }
}

main() {
    activar_venv
    mkdir -p "$OUT"
    if ! ( command -v curl >/dev/null 2>&1 && curl -s -m 3 "$MOSAIC_LLM_BASE_URL/models" >/dev/null 2>&1 ); then
        err "Cluster sin respuesta en $MOSAIC_LLM_BASE_URL — lanza ~/cluster/lanzar_cluster.sh"
        err "(añade --offline para ensayar el bucle sin red)"
    fi
    if [ "$MODO" = "consolidar" ]; then
        log "Consolidando el USO REAL ($MOSAIC_HISTORIAL)..."
        python3 "$MOSAIC_DIR/mosaic.py" --consolidar --out "$OUT" "$@" \
            > >(tee "$OUT/_log.out") 2> >(tee "$OUT/_log.err" >&2)
        echo
        log "CONSOLIDADO.  Resumen: $OUT/consolidacion.md   ·   Estado: $MOSAIC_STATE"
        return 0
    fi
    log "Aprendizaje: $CICLOS ciclo(s). Resultados en $OUT"
    python3 "$MOSAIC_DIR/mosaic.py" --aprender --ciclos "$CICLOS" --out "$OUT" "$@" \
        > >(tee "$OUT/_log.out") 2> >(tee "$OUT/_log.err" >&2)
    echo
    log "CICLO COMPLETO."
    log "  Informe:  $OUT/aprendizaje.md"
    log "  Análisis: $OUT/analisis.md   (diagnóstico del propio modelo)"
    log "  Estado:   $MOSAIC_STATE   ·   Huecos: $MOSAIC_GAPS"
}

main "$@"
