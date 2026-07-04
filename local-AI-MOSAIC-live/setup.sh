#!/bin/bash
# 🧰 =====================================================================
# 🧰 SETUP — prepara un clon RECIÉN CLONADO de MOSAIC para su primer ciclo.
# 🧰   1) valida binarios (núcleo obligatorio · formatos opcionales)
# 🧰   2) crea la estructura de directorios (data/ silo/ trash/ …)
# 🧰   3) copia .env.example → .env si no existe (NUNCA pisa el tuyo)
# 🧰   4) selftest offline: sintaxis de todos los .sh y compilación de los .py
# 🧰 No instala nada por ti: te dice QUÉ falta y CÓMO conseguirlo.
# 🧰 Idempotente: puedes lanzarlo las veces que quieras.
# 🧰 Uso:  ./setup.sh
# 🧰 =====================================================================
set -euo pipefail

HOME_USER="${HOME_USER:-$HOME}"
MOSAIC_DIR="${MOSAIC_DIR:-$(cd "$(dirname "$0")" && pwd)}"
TMP_SETUP="$(mktemp -d)"

log()  { printf '[%s] 🧰 %s\n' "$(date '+%H:%M:%S')" "$*"; }
warn() { printf '[%s] ⚠️  %s\n' "$(date '+%H:%M:%S')" "$*" >&2; }
cleanup() { rm -rf "$TMP_SETUP" 2>/dev/null || true; }
trap cleanup EXIT

FALTAN_NUCLEO=0

mirar() {   # mirar <binario> <nucleo|opcional> <para-qué> <cómo-instalar>
    if command -v "$1" >/dev/null 2>&1; then
        log "  ✅ $1 — $3"
    elif [ "$2" = "nucleo" ]; then
        warn "  ❌ $1 (NÚCLEO) — $3 · instala: $4"
        FALTAN_NUCLEO=$((FALTAN_NUCLEO + 1))
    else
        warn "  ◽ $1 (opcional) — $3 · si lo quieres: $4"
    fi
}

validar() {
    log "1/4 · Binarios ═══════════════════════════════════════════"
    mirar bash     nucleo   "shell (se requiere bash ≥4; macOS: brew install bash)" "brew install bash"
    mirar python3  nucleo   "pegamento y motor (stdlib)"            "https://www.python.org o brew install python"
    mirar curl     nucleo   "hablar con llama-server"               "brew install curl"
    mirar git      nucleo   "control de versiones"                  "https://git-scm.com"
    mirar ssh      opcional "2º cerebro (juez) por red"             "incluido en macOS/Linux"
    mirar pdftotext opcional "PDF → texto"                          "brew install poppler"
    mirar pdftoppm opcional "PDF escaneado → imagen (para OCR)"     "brew install poppler"
    mirar tesseract opcional "OCR de imágenes y escaneados"         "brew install tesseract tesseract-lang"
    mirar whisper  opcional "audio/vídeo → texto"                   "pip install -U openai-whisper"
    mirar ffmpeg   opcional "extraer audio de vídeo"                "brew install ffmpeg"
    mirar textutil opcional "docx/rtf/odt → texto (solo macOS)"     "incluido en macOS; en Linux usa pandoc"
    mirar sips     opcional "HEIC de iPhone → png (solo macOS)"     "incluido en macOS; en Linux usa heif-convert"
    mirar unzip    opcional "Apple iWork (pages/numbers/key)"       "incluido"
    if command -v llama-server >/dev/null 2>&1 || [ -x "$HOME_USER/modelo/llama.cpp/build/bin/llama-server" ]; then
        log "  ✅ llama-server — el motor LLM local"
    else
        warn "  ◽ llama-server no visto — compílalo: https://github.com/ggml-org/llama.cpp (los ciclos reales lo necesitan; el modo --offline no)"
    fi
    if [ "$FALTAN_NUCLEO" -gt 0 ]; then
        warn "faltan $FALTAN_NUCLEO binarios de NÚCLEO — instálalos y relanza ./setup.sh"
        exit 1
    fi
}

estructura() {
    log "2/4 · Directorios ════════════════════════════════════════"
    local d
    for d in data data/actas data/cola silo silo/extraciones silo/.pendiente silo/.procesando \
             resultados logs cuarentena cuarentena/.procesando \
             procesados/silo procesados/cuarentena info packs \
             capabilities roles trash/logs trash/historico trash/backups trash/otros; do
        mkdir -p "$MOSAIC_DIR/$d"
    done
    log "  ✅ estructura lista (data/ silo/ resultados/ trash/ capabilities/ roles/ …)"
}

entorno() {
    log "3/4 · Entorno ════════════════════════════════════════════"
    if [ -f "$MOSAIC_DIR/.env" ]; then
        log "  ✅ .env ya existe (no lo toco)"
    elif [ -f "$MOSAIC_DIR/.env.example" ]; then
        cp "$MOSAIC_DIR/.env.example" "$MOSAIC_DIR/.env"
        log "  ✅ .env creado desde .env.example → EDÍTALO con tus IPs/hosts"
    else
        warn "  ◽ no hay .env.example (¿clon incompleto?)"
    fi
    if [ ! -f "$MOSAIC_DIR/info/apiskeys.txt" ]; then
        printf '# API KEYS — formato: SERVICIO|clave (lee apikey.sh)\n' > "$MOSAIC_DIR/info/apiskeys.txt" 2>/dev/null \
            && chmod 600 "$MOSAIC_DIR/info/apiskeys.txt" \
            && log "  ✅ info/apiskeys.txt creado vacío (chmod 600) — añade ahí tus claves" \
            || warn "  ◽ no pude crear info/apiskeys.txt"
    else
        chmod 600 "$MOSAIC_DIR/info/apiskeys.txt" 2>/dev/null || true
        log "  ✅ info/apiskeys.txt existe (permisos 600 asegurados)"
    fi
}

selftest() {
    log "4/4 · Selftest offline ═══════════════════════════════════"
    local f errores=0
    for f in "$MOSAIC_DIR"/*.sh; do
        bash -n "$f" 2>"$TMP_SETUP/err" || { warn "  ❌ sintaxis: $(basename "$f") — $(head -1 "$TMP_SETUP/err")"; errores=$((errores+1)); }
    done
    log "  ✅ bash -n de todos los .sh"
    for f in "$MOSAIC_DIR"/*.py; do
        python3 -m py_compile "$f" 2>"$TMP_SETUP/err" || { warn "  ❌ py_compile: $(basename "$f")"; errores=$((errores+1)); }
    done
    log "  ✅ py_compile de todos los .py"
    if [ "$errores" -gt 0 ]; then
        warn "selftest con $errores error(es) — revisa arriba"
        exit 1
    fi
}

log "MOSAIC · setup en: $MOSAIC_DIR"
validar
estructura
entorno
selftest
log "🎉 listo. Siguiente paso: edita .env · luego ./mosaic.sh ciclo  (o ./tribunal.py --offline \"pregunta\" \"respuesta\" para probar sin modelos)"
