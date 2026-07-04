#!/bin/bash
# 🧪 =====================================================================
# 🧪 SILO EXTRACTOR — convierte un archivo NO apto para IA en TEXTO plano.
# 🧪 Lo ÚTIL (transcripción, OCR, texto) → silo/ (.txt, para ingerir).
# 🧪 Los SUBPRODUCTOS (vídeo, audio extraído, intermedios) → silo/extraciones/
# 🧪 (se GUARDAN, nunca se ingieren ni se borran).
# 🧪 Usa las MISMAS herramientas que tus scripts (ffmpeg, whisper, tesseract,
# 🧪 pdftotext) pero NO interactivo. Tus scripts fueron la referencia.
# 🧪 Uso:  ./silo_extractor.sh ARCHIVO   ·   0=sacó texto · 1=falló · 2=no aplica · 3=falta herramienta (retener)
# 🧪 =====================================================================
set -uo pipefail

SILO="${SILO_DIR:-$HOME/Mosaic_privado/silo}"
EXTRA="$SILO/extraciones"
WHISPER_VENV="${WHISPER_VENV:-$HOME/modelo/entornos/whisperenv}"
WHISPER_MODEL="${WHISPER_MODEL:-tiny}"   # tiny = memos en segundos (Fase A de Opus, 2-jul); base solo si buscas fidelidad
BASE_DIR="${MOSAIC_BASE:-$HOME/Mosaic_privado}"   # para localizar los enriquecedores
PYBIN="${PYBIN:-$HOME/wikirag/venv/bin/python3}"; [ -x "$PYBIN" ] || PYBIN="$(command -v python3)"   # para xlsx (pandas)
TIMEOUT_BIN="$(command -v gtimeout || command -v timeout || true)"   # macOS: brew install coreutils → gtimeout
WHISPER_TIMEOUT="${WHISPER_TIMEOUT:-180}"   # s máx por transcripción (0 = sin límite); si agota → RETENER (Fase A: 900→180, un audio no congela la cascada 15 min)
MIN_TXT_C="${MIN_TXT_C:-25}"                # transcripción con menos bytes = vacía → no se ingiere (fix 2-jul: entraban txt de 1c)

log() { printf '[%s] 🧪 %s\n' "$(date +%H:%M:%S)" "$*"; }
mkdir -p "$EXTRA"

# ¿está whisper disponible? (venv propio o en PATH). Si no, es "falta herramienta", no un fallo real.
hay_whisper() { [ -f "$WHISPER_VENV/bin/activate" ] || command -v whisper >/dev/null 2>&1; }

# whisper dentro de su venv → deja un .txt en $2; imprime su ruta.
# Fix 2-jul (cuelgue en FASE 1): timeout degradable + stdin cerrado (whisper/su ffmpeg
# interno pueden quedarse esperando stdin y congelar la cascada). rc: 0 ok · 124 timeout.
transcribir() {  # $1 audio  $2 outdir
    local rc=0
    ( [ -f "$WHISPER_VENV/bin/activate" ] && source "$WHISPER_VENV/bin/activate" 2>/dev/null || true
      command -v whisper >/dev/null 2>&1 || exit 0
      if [ -n "$TIMEOUT_BIN" ] && [ "${WHISPER_TIMEOUT:-0}" -gt 0 ]; then
          "$TIMEOUT_BIN" "$WHISPER_TIMEOUT" whisper "$1" --model "$WHISPER_MODEL" \
              --output_format txt --output_dir "$2" </dev/null >/dev/null 2>&1
      else
          whisper "$1" --model "$WHISPER_MODEL" \
              --output_format txt --output_dir "$2" </dev/null >/dev/null 2>&1
      fi ) || rc=$?
    echo "$2/$(basename "${1%.*}").txt"
    return "$rc"
}

# ¿el texto extraído tiene chicha? (evita ingerir transcripciones de 1 carácter)
util() { [ -s "$1" ] && [ "$(wc -c < "$1" | tr -d ' ')" -ge "$MIN_TXT_C" ]; }

# 📄 #76 · PDF escaneado (sin capa de texto) → OCR por páginas: pdftoppm rasteriza, tesseract lee.
ocr_pdf() {  # $1 pdf  $2 salida.txt
    command -v pdftoppm >/dev/null && command -v tesseract >/dev/null || return 1
    local tmp; tmp="$(mktemp -d)"
    pdftoppm -r "${OCR_DPI:-300}" -png "$1" "$tmp/pag" >/dev/null 2>&1 || { rm -rf "$tmp"; return 1; }
    : > "$2"; local p hubo=1
    for p in "$tmp"/pag-*.png; do
        [ -e "$p" ] || continue
        tesseract "$p" - -l "${OCR_LANG:-spa+eng}" 2>/dev/null >> "$2" && hubo=0
        printf '\n' >> "$2"
    done
    rm -rf "$tmp"
    [ "$hubo" = 0 ] && [ -s "$2" ]
}

# 🔧 Enriquecimientos OPCIONALES sobre una transcripción: hablantes (#77) y traducción (#78).
enriquecer() {  # $1 .txt transcripción (silo)  $2 .wav (extraciones)
    local txt="$1" wav="$2" base; base="$(basename "${txt%.*}")"; base="${base%_transcripcion}"
    if [ "${SILO_DIARIZAR:-0}" = "1" ] && [ -f "$wav" ] && [ -f "$BASE_DIR/silo_diarizar.py" ]; then
        local n; n="$("${DIAR_PY:-python3}" "$BASE_DIR/silo_diarizar.py" "$wav" 2>/dev/null | head -1)"
        if [ -n "$n" ] && [ "$n" != 0 ]; then
            printf 'hablantes_estimados: %s\n' "$n" > "$EXTRA/${base}_hablantes.txt"
            log "👤 #77 diarización: ~$n hablante(s) → extraciones/${base}_hablantes.txt"
        fi
    fi
    if [ -n "${SILO_TRADUCIR:-}" ] && [ -f "$BASE_DIR/silo_traducir.sh" ]; then
        if bash "$BASE_DIR/silo_traducir.sh" "$txt" "$SILO_TRADUCIR" "$SILO/${base}_${SILO_TRADUCIR}.txt" >/dev/null 2>&1; then
            log "🌐 #78 traducción → ${base}_${SILO_TRADUCIR}.txt"
        fi
    fi
}

extraer() {
    local f="$1" ext base; ext="$(printf '%s' "${f##*.}" | tr 'A-Z' 'a-z')"; base="$(basename "${f%.*}")"
    case "$ext" in
        mp4|mkv|avi|mov|webm|m4v|wmv|flv|mpg|mpeg|3gp|ts|ogv|m2ts)  # 🎬 VÍDEO → audio → transcripción
            command -v ffmpeg >/dev/null || { log "falta ffmpeg → retener"; return 3; }
            hay_whisper || { log "falta whisper → retener"; return 3; }
            local wav="$EXTRA/${base}.wav" txt rc=0
            ffmpeg -nostdin -y -i "$f" -vn -ac 1 -ar 16000 "$wav" </dev/null >/dev/null 2>&1 || { log "ffmpeg falló: $base"; return 1; }
            txt="$(transcribir "$wav" "$EXTRA")" || rc=$?
            [ "$rc" = 124 ] && { log "whisper agotó ${WHISPER_TIMEOUT}s: $base → retener"; return 3; }
            mv "$f" "$EXTRA/" 2>/dev/null || true   # el vídeo es subproducto
            if util "$txt"; then cp "$txt" "$SILO/${base}_transcripcion.txt"; log "🎬→texto: ${base}_transcripcion.txt (útil) · vídeo+audio→extraciones"; enriquecer "$SILO/${base}_transcripcion.txt" "$wav"; return 0; fi
            log "vídeo sin transcripción útil (<${MIN_TXT_C}c o vacía)"; return 1 ;;
        mp3|wav|m4a|flac|ogg|aac|opus|aiff|aif|wma|amr|m4b|caf)  # 🎙️ AUDIO → transcripción
            hay_whisper || { log "falta whisper → retener"; return 3; }
            local src="$f" txt rc=0
            if [ "$ext" != wav ] && command -v ffmpeg >/dev/null; then
                ffmpeg -nostdin -y -i "$f" -ac 1 -ar 16000 "$EXTRA/${base}.wav" </dev/null >/dev/null 2>&1 && src="$EXTRA/${base}.wav"
            fi
            txt="$(transcribir "$src" "$EXTRA")" || rc=$?
            [ "$rc" = 124 ] && { log "whisper agotó ${WHISPER_TIMEOUT}s: $base → retener"; return 3; }
            mv "$f" "$EXTRA/" 2>/dev/null || true
            if util "$txt"; then cp "$txt" "$SILO/${base}_transcripcion.txt"; log "🎙️→texto: ${base}_transcripcion.txt"; enriquecer "$SILO/${base}_transcripcion.txt" "$EXTRA/${base}.wav"; return 0; fi
            log "audio sin transcripción útil (<${MIN_TXT_C}c o vacía)"; return 1 ;;
        png|jpg|jpeg|tiff|bmp|gif|webp)           # 🖼️ IMAGEN → OCR
            command -v tesseract >/dev/null || { log "falta tesseract → retener"; return 3; }
            if tesseract "$f" "$SILO/${base}_ocr" -l "${OCR_LANG:-spa+eng}" 2>/dev/null && [ -s "$SILO/${base}_ocr.txt" ]; then
                mv "$f" "$EXTRA/" 2>/dev/null || true; log "🖼️→texto: ${base}_ocr.txt"; return 0
            fi; log "OCR vacío: $base"; return 1 ;;
        heic|heif)                                # 🍎 foto iPhone → png (sips/imagemagick) → OCR
            command -v tesseract >/dev/null || { log "falta tesseract → retener"; return 3; }
            local png2="$EXTRA/${base}.png" conv=""
            if   command -v sips    >/dev/null 2>&1; then sips -s format png "$f" --out "$png2" >/dev/null 2>&1 && conv=1
            elif command -v magick  >/dev/null 2>&1; then magick "$f" "$png2" >/dev/null 2>&1 && conv=1
            elif command -v convert >/dev/null 2>&1; then convert "$f" "$png2" >/dev/null 2>&1 && conv=1
            else log "falta sips/imagemagick para heic → retener"; return 3; fi
            [ -n "$conv" ] && [ -s "$png2" ] || { log "no pude convertir heic: $base"; return 1; }
            if tesseract "$png2" "$SILO/${base}_ocr" -l "${OCR_LANG:-spa+eng}" 2>/dev/null && [ -s "$SILO/${base}_ocr.txt" ]; then
                mv "$f" "$EXTRA/" 2>/dev/null || true; log "🍎→texto (heic): ${base}_ocr.txt"; return 0
            fi; log "OCR vacío (heic): $base"; return 1 ;;
        pdf)                                      # 📄 PDF → texto (pdftotext; escaneado → OCR aparte)
            local out="$SILO/${base}_texto.txt"
            if command -v pdftotext >/dev/null && pdftotext -q "$f" "$out" 2>/dev/null && [ -s "$out" ]; then
                mv "$f" "$EXTRA/" 2>/dev/null || true; log "📄→texto: ${base}_texto.txt"; return 0
            fi
            rm -f "$out" 2>/dev/null || true
            if command -v pdftoppm >/dev/null && command -v tesseract >/dev/null; then
                if ocr_pdf "$f" "$out"; then       # escaneado: sin capa de texto → OCR por páginas (#76)
                    mv "$f" "$EXTRA/" 2>/dev/null || true; log "📄(escaneado)→OCR: ${base}_texto.txt"; return 0
                fi
                rm -f "$out" 2>/dev/null || true; log "pdf escaneado ilegible por OCR: $base"; return 1
            fi
            rm -f "$out" 2>/dev/null || true; log "pdf escaneado y faltan pdftoppm/tesseract → retener"; return 3 ;;
        xlsx|xls|xlsm)                            # 📊 Excel → texto (pandas)
            "$PYBIN" -c 'import pandas, openpyxl' 2>/dev/null || { log "falta pandas/openpyxl para Excel → retener"; return 3; }
            local xout="$SILO/${base}_hoja.txt" xrc=0
            "$PYBIN" - "$f" "$xout" <<'PYX' 2>/dev/null || xrc=$?
import sys, pandas as pd
libro = pd.read_excel(sys.argv[1], sheet_name=None, dtype=str)
with open(sys.argv[2], "w", encoding="utf-8") as o:
    for hoja, df in libro.items():
        o.write("# Hoja: %s\n" % hoja)
        o.write(df.fillna("").to_csv(index=False))
        o.write("\n")
PYX
            if [ "$xrc" = 0 ] && [ -s "$xout" ]; then
                mv "$f" "$EXTRA/" 2>/dev/null || true; log "📊→texto: ${base}_hoja.txt"; return 0
            fi
            rm -f "$xout" 2>/dev/null || true; log "Excel ilegible: $base"; return 1 ;;
        pages|numbers|key|keynote)                # 🍎 iWork → Preview.pdf interno → texto
            command -v unzip    >/dev/null 2>&1 || { log "falta unzip para iWork → retener"; return 3; }
            command -v pdftotext >/dev/null 2>&1 || { log "falta pdftotext para iWork → retener"; return 3; }
            local wtmp iout="$SILO/${base}_texto.txt" prev; wtmp="$(mktemp -d)"
            unzip -o -q "$f" -d "$wtmp" 2>/dev/null || true
            prev="$(find "$wtmp" -iname 'Preview*.pdf' 2>/dev/null | head -1)"
            [ -n "$prev" ] || prev="$(find "$wtmp" -iname '*.pdf' 2>/dev/null | head -1)"
            if [ -n "$prev" ] && [ -s "$prev" ] && pdftotext -q "$prev" "$iout" 2>/dev/null && [ -s "$iout" ]; then
                rm -rf "$wtmp"; mv "$f" "$EXTRA/" 2>/dev/null || true; log "🍎→texto (iWork): ${base}_texto.txt"; return 0
            fi
            rm -rf "$wtmp"; rm -f "$iout" 2>/dev/null || true; log "iWork sin preview PDF extraíble: $base"; return 1 ;;
        *) return 2 ;;                            # no es un tipo que extraigamos aquí
    esac
}

extraer "${1:?uso: silo_extractor.sh ARCHIVO}"
