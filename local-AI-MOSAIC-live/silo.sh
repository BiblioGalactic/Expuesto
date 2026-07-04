#!/bin/bash
# 📦 =====================================================================
# 📦 SILO — depósito de archivos locales → cola, por LOTES y por EXTENSIÓN.
# 📦 Tiras CUALQUIER archivo a silo/. Cuando hay ≥ LOTE, activa ese lote; el
# 📦 resto espera. Cada archivo se discrimina por extensión y se convierte a
# 📦 texto (pdf/audio/img→texto), se envuelve como TAREA y entra a la cola
# 📦 (fuente=silo). Originales → procesados/silo (VISIBLE en Finder — 4-jul; nunca se borran).
# 📦 Uso:  ./silo.sh           (procesa lo que haya por lotes)
# 📦       ./silo.sh estado    (cuántos archivos esperando)
# 📦       ./silo.sh reintentar (devuelve silo/.pendiente → silo tras instalar OCR/whisper)
# 📦 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
SILO="${SILO_DIR:-$BASE/silo}"
# 👁️ 4-jul (petición de Gustavo): los procesados a carpeta VISIBLE (Finder), FUERA de silo/
# para que los globs de lote no la pisen. Los .procesando/.pendiente siguen ocultos (tránsito).
PROC="$SILO/.procesando"; HECHOS="${SILO_HECHOS:-$BASE/procesados/silo}"
COLA_SH="${COLA_SH:-$BASE/cola.sh}"
LOTE="${SILO_LOTE:-4}"               # nº de archivos que activa un lote
MAXTEXTO="${SILO_MAXTEXTO:-4000}"    # chars por documento al encolar
MAX_ENCOLAR="${SILO_MAX:-100000}"    # tope por pasada (lo usa fuente_silo con su presupuesto)
DEDUP="${DEDUP_PY:-$BASE/dedup.py}"                      # 🧬 servicio de dedup semántico (#60)
DEDUP_IDX="${DEDUP_INDEX:-$BASE/data/dedup_index.jsonl}" # índice persistente de lo ya ingerido
DEDUP_UMBRAL="${DEDUP_UMBRAL:-0.82}"                     # sim >= esto = duplicado
MOSAIC_DEDUP="${MOSAIC_DEDUP:-1}"                        # 1 = filtra duplicados antes de encolar
PYDEDUP="${PYDEDUP:-$HOME/wikirag/venv/bin/python3}"; [ -x "$PYDEDUP" ] || PYDEDUP="$(command -v python3)"

log()  { printf '[%s] 📦 %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

validar() {
    command -v python3 >/dev/null || { warn "falta python3"; exit 1; }
    [ -f "$COLA_SH" ] || { warn "no encuentro cola.sh en $COLA_SH"; exit 1; }
    mkdir -p "$SILO" "$PROC" "$HECHOS" "$SILO/.pendiente" "$BASE/trash/otros"
}

# extensión → texto por stdout; return 1 si no se sabe/puede convertir
convertir() {
    local f="$1" ext; ext="$(printf '%s' "${1##*.}" | tr '[:upper:]' '[:lower:]')"
    case "$ext" in
        txt|md|markdown|text|csv|tsv|log|json|yaml|yml|xml|html|htm|rst|tex|ini|toml|conf|srt|vtt) cat "$f" ;;
        pdf)  command -v pdftotext >/dev/null && pdftotext -q "$f" - || { warn "pdf sin pdftotext: $(basename "$f")"; return 1; } ;;
        docx|doc|rtf|rtfd|odt|wordml|webarchive) command -v textutil  >/dev/null && textutil -convert txt -stdout "$f" || { warn "doc sin textutil: $(basename "$f")"; return 1; } ;;
        mp3|wav|m4a|flac|ogg)
            if command -v whisper >/dev/null; then
                whisper "$f" --model base --output_format txt --output_dir "$PROC" >/dev/null 2>&1
                cat "$PROC/$(basename "${f%.*}").txt" 2>/dev/null || { warn "audio no transcrito: $(basename "$f")"; return 1; }
            else warn "audio sin whisper: $(basename "$f")"; return 1; fi ;;
        png|jpg|jpeg|tiff|bmp|gif)
            command -v tesseract >/dev/null && tesseract "$f" - 2>/dev/null || { warn "imagen sin tesseract: $(basename "$f")"; return 1; } ;;
        py|sh|js|ts|rb|go|rs|c|cpp|h|java|php|swift|kt|kts|scala|lua|pl|pm|r|sql|jl|dart|ex|exs|clj|hs|css|scss|sass|less|tsx|jsx|vue|cs|vb|mm) printf 'Código del fichero %s:\n%s' "$(basename "$f")" "$(cat "$f")" ;;
        *) warn "extensión no soportada: $(basename "$f")"; return 1 ;;
    esac
}

procesar_uno() {   # $1 = archivo en PROC
    local f="$1" nom ext; nom="$(basename "$f")"; ext="$(printf '%s' "${f##*.}" | tr 'A-Z' 'a-z')"
    case "$ext" in   # MEDIA → extractor: texto útil a silo, subproductos a extraciones, consume el original
        mp4|mkv|avi|mov|webm|m4v|wmv|flv|mpg|mpeg|3gp|ts|ogv|m2ts|mp3|wav|m4a|flac|ogg|aac|opus|aiff|aif|wma|amr|m4b|caf|png|jpg|jpeg|tiff|bmp|gif|webp|heic|heif|pdf|xlsx|xls|xlsm|pages|numbers|key|keynote)
            local rc=0
            SILO_DIR="$SILO" bash "$BASE/silo_extractor.sh" "$f" 2>&1 || rc=$?
            if [ "$rc" = 0 ]; then
                log "extraído: $nom → texto a silo (se ingiere en la próxima pasada)"; return 0
            elif [ "$rc" = 3 ]; then   # falta herramienta: NO se pierde, espera en .pendiente
                warn "falta herramienta (OCR/whisper): $nom → .pendiente (reintenta con: silo.sh reintentar)"
                mv "$f" "$SILO/.pendiente/" 2>/dev/null || true; return 1
            else
                warn "extracción falló: $nom → trash/otros"; mv "$f" "$BASE/trash/otros/" 2>/dev/null || mv "$f" "$HECHOS/" 2>/dev/null || true; return 1
            fi ;;
    esac
    local texto; texto="$(convertir "$f" 2>/dev/null || true)"
    if [ -z "${texto// /}" ]; then
        warn "no convertido → a trash/otros: $nom"; mv "$f" "$BASE/trash/otros/" 2>/dev/null || mv "$f" "$HECHOS/"; return 0
    fi
    local recorte; recorte="$(printf '%s' "$texto" | head -c "$MAXTEXTO")"
    if "$COLA_SH" add "Lee el documento [$nom] y extrae sus puntos clave y qué capacidades requiere para tratarlo: $recorte" silo >/dev/null; then
        mv "$f" "$HECHOS/"; log "encolado: $nom (${#recorte}c)"; return 0
    fi
    warn "no pude encolar → trash/otros (no reintento en bucle): $nom"; mv "$f" "$BASE/trash/otros/" 2>/dev/null || mv "$f" "$HECHOS/" 2>/dev/null || true; return 1
}

contar() { local n=0 f; shopt -s nullglob; for f in "$SILO"/*; do [ -f "$f" ] && n=$((n+1)); done; shopt -u nullglob; echo "$n"; }

# 🧬 dedup semántico del lote en PROC: UNA carga de modelo; los DUP → .hechos (no se encolan).
dedup_lote() {
    [ "$MOSAIC_DEDUP" = "1" ] && [ -f "$DEDUP" ] || return 0
    local textos=() f
    for f in "$PROC"/*; do
        [ -f "$f" ] || continue
        case "$(printf '%s' "${f##*.}" | tr 'A-Z' 'a-z')" in
            txt|md|markdown|text|csv|tsv|log|json|yaml|yml|xml|html|htm|rst|tex|ini|toml|conf|srt|vtt) textos+=("$f") ;;   # solo texto plano
        esac
    done
    [ "${#textos[@]}" -gt 0 ] || return 0
    local veredicto ruta dup=0
    while IFS=$'\t' read -r veredicto ruta; do
        [ "$veredicto" = "DUP" ] || continue
        warn "🧬 duplicado semántico → no encolo: $(basename "$ruta")"
        mv "$ruta" "$HECHOS/" 2>/dev/null || true; dup=$((dup+1))
    done < <("$PYDEDUP" "$DEDUP" nuevos --indice "$DEDUP_IDX" --umbral "$DEDUP_UMBRAL" "${textos[@]}" 2>/dev/null)
    [ "$dup" -gt 0 ] && log "🧬 lote: $dup duplicado(s) apartados (.hechos); el resto se encola."
    return 0
}

ejecutar() {
    shopt -s nullglob
    for f in "$PROC"/*; do [ -e "$f" ] && mv "$f" "$SILO/" 2>/dev/null || true; done   # recupera cortes previos
    local encolados=0
    while [ "$encolados" -lt "$MAX_ENCOLAR" ]; do
        local lote=() f; for f in "$SILO"/*; do [ -f "$f" ] && lote+=("$f"); done
        local n=${#lote[@]}
        if [ "$n" -lt "$LOTE" ]; then log "silo: $n archivo(s) < lote $LOTE → esperan"; break; fi
        log "silo: $n ≥ $LOTE → activo un lote de $LOTE"
        local i=0; for f in "${lote[@]}"; do [ "$i" -ge "$LOTE" ] && break; mv "$f" "$PROC/"; i=$((i+1)); done
        dedup_lote   # 🧬 aparta duplicados del lote antes de encolar (#60)
        for f in "$PROC"/*; do
            [ -e "$f" ] || continue
            procesar_uno "$f" && encolados=$((encolados+1))
            [ "$encolados" -ge "$MAX_ENCOLAR" ] && break
        done
    done
    shopt -u nullglob
    log "silo: $encolados encolados en esta pasada."
}

case "${1:-procesar}" in
    procesar) validar; ejecutar ;;
    estado)   validar; log "esperando en silo: $(contar) archivo(s) (lote = $LOTE)" ;;
    reintentar) validar; n=0; shopt -s nullglob
        for f in "$SILO/.pendiente"/*; do [ -f "$f" ] && { mv "$f" "$SILO/" && n=$((n+1)); }; done
        shopt -u nullglob; log "reintentar: $n archivo(s) de .pendiente → silo (se procesan en la próxima pasada)" ;;
    *)        warn "uso: silo.sh procesar | estado | reintentar"; exit 1 ;;
esac
