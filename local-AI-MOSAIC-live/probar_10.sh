#!/bin/bash
# 🧪 =====================================================================
# 🧪 MOSAIC — batería de 10 formas de comunicación + autoevaluación
# 🧪 Lanza 10 peticiones variadas, guarda cada salida en una carpeta y
# 🧪 luego el PROPIO cluster juzga si MOSAIC funcionó.
# 🧪 =====================================================================
set -euo pipefail

export HOME_USER="${HOME_USER:-$HOME}"
export MOSAIC_DIR="$HOME_USER/Mosaic_privado"
# ⚔️ 4-jul: EL 24B JAMÁS; el 8090 local está muerto. MODEL "qwen3" activa el gate /no_think.
export MOSAIC_LLM_BASE_URL="${MOSAIC_LLM_BASE_URL:-http://127.0.0.1:8092/v1}"   # principal (Qwen3-14B)
export MOSAIC_LLM_FAST_URL="${MOSAIC_LLM_FAST_URL:-http://127.0.0.1:8091/v1}"   # 13B (rápido)
export MOSAIC_LLM_MODEL="${MOSAIC_LLM_MODEL:-qwen3-14b}"
export MOSAIC_EMBEDDER="hashing"
export MOSAIC_CAPS_DIR="$MOSAIC_DIR/capabilities"
export MOSAIC_STATE="$MOSAIC_DIR/data/state.json"
export MOSAIC_CONTEXT_CACHE="$MOSAIC_DIR/data/context_cache.json"
export MOSAIC_CONTEXTUALIZE="1"

VENV="$MOSAIC_DIR/venv"
STAMP="$(date '+%Y%m%d_%H%M%S')"
OUT="$MOSAIC_DIR/resultados/run_$STAMP"
TMP_DIR="$(mktemp -d)"

log() { printf '[%s] [INFO]  %s\n' "$(date '+%H:%M:%S')" "$*"; }
err() { printf '[%s] [ERROR] %s\n' "$(date '+%H:%M:%S')" "$*" >&2; }

cleanup() {
    command -v deactivate >/dev/null 2>&1 && deactivate || true
    rm -rf "$TMP_DIR" 2>/dev/null || true
}
trap cleanup EXIT

activar_venv() {
    [ -d "$VENV" ] || { log "Creando venv en $VENV..."; python3 -m venv "$VENV"; }
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    python3 -c "import numpy" 2>/dev/null || { log "Instalando numpy/pyyaml..."; pip install -q numpy pyyaml; }
}

# 10 formas distintas: imperativa, pregunta, vaga, detallada, inglés, datos,
# solo-tests, tipos, restricción, y una contra el modelo rápido (13B).
# Formato:  "petición|flags"   (flags vacío o "--fast")
PRUEBAS=(
    "escribe un fetcher async con reintentos y tests|"
    "¿cómo valido los tipos de una función python que procesa un dataframe?|"
    "ordena datos|"
    "necesito una clase python bien tipada que lea un csv grande por chunks con pandas, maneje filas corruptas y tenga pruebas pytest de los casos límite|"
    "write a python function to retry failed async http requests with exponential backoff|"
    "analiza la distribución de una columna y detecta valores atípicos|"
    "escribe tests pytest para una función que divide dos números|"
    "añade anotaciones de tipos y dataclasses a un módulo de usuarios|"
    "haz un parser de json sin usar librerías externas|"
    "escribe una función async con manejo de errores|--fast"
)

main() {
    activar_venv
    mkdir -p "$OUT"
    log "Resultados en: $OUT"

    if ! ( command -v curl >/dev/null 2>&1 && curl -s -m 3 "$MOSAIC_LLM_BASE_URL/models" >/dev/null 2>&1 ); then
        err "Cluster sin respuesta en $MOSAIC_LLM_BASE_URL"
        err "Lanza primero: $HOME_USER/cluster/lanzar_cluster.sh"
        err "(continúo; sin red se guarda el prompt compuesto, sin respuesta del modelo)"
    fi

    local i=0
    for fila in "${PRUEBAS[@]}"; do
        i=$((i + 1))
        local req="${fila%%|*}"
        local flags="${fila##*|}"
        local nn; nn="$(printf '%02d' "$i")"
        log "[$nn] ${flags:+[$flags] }$req"
        # stdout legible -> NN.txt | errores -> NN.err | registro JSON -> NN.json
        python3 "$MOSAIC_DIR/mosaic.py" "$req" $flags \
            --out "$OUT/$nn.json" \
            > "$OUT/$nn.txt" 2> "$OUT/$nn.err" \
            || err "[$nn] falló (revisa $OUT/$nn.err)"
    done

    log "Autoevaluación: el cluster (principal) juzga cada resultado..."
    python3 "$MOSAIC_DIR/mosaic.py" --evaluar "$OUT" \
        > "$OUT/_evaluacion.stdout" 2>&1 || err "evaluación falló (revisa _evaluacion.stdout)"

    echo
    log "LISTO. Carpeta de resultados: $OUT"
    log "Resumen:  $OUT/evaluacion.md"
    log "Detalle:  $OUT/NN.txt (legible) · $OUT/NN.json (datos) · $OUT/evaluacion.json"
}

main "$@"
