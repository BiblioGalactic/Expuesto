#!/bin/bash
# 🔎 =====================================================================
# 🔎 INVENTARIO DE MODELOS — escanea QUÉ modelos de IA hay y los clasifica por
# 🔎 capacidad (LLM · visión · imagen · OCR · detección · ASR · separación ·
# 🔎 TTS · hablantes · embeddings). Sirve para decidir qué mover a la SSD (#45)
# 🔎 y qué capacidades enchufar (#76+). Corre igual en el MacBook y en el mini.
# 🔎 Incluye cachés (~/.cache, ~/Library) y SSD externas (/Volumes/*).
# 🔎 Uso:  bash inventario_modelos.sh [raíces extra...]
# 🔎       ssh MINI 'bash -s' < inventario_modelos.sh      (escanea el mini + su SSD)
# 🔎 =====================================================================
set -uo pipefail

ROOTS=(
    "$HOME/modelo" "$HOME/wikirag"
    "$HOME/.cache/huggingface" "$HOME/.cache/torch" "$HOME/.cache/whisper" "$HOME/.cache/demucs"
    "$HOME/Library/Application Support/tts" "$HOME/.local/share/tts"
)
for v in /Volumes/*; do [ -d "$v" ] && [ ! -L "$v" ] && ROOTS+=("$v"); done   # SSD externas (salta el symlink Macintosh HD→/)
ROOTS+=("$@")                                                # raíces extra por argumento

TMP="$(mktemp)"; TMP2="$(mktemp)"
cleanup() { rm -f "$TMP" "$TMP2" 2>/dev/null || true; }
trap cleanup EXIT

clasifica() {   # ruta → categoría (orden importa: lo específico primero)
    local p; p="$(printf '%s' "$1" | tr 'A-Z' 'a-z')"
    case "$p" in
        *llava*|*vlm*|*-vl-*|*clip*|*blip*|*siglip*)                 echo "👁  VISION (imagen→texto)";;
        *yolo*|*ultralytics*|*/deteccion/*|*detection*)              echo "🎯 DETECCION (objetos)";;
        *stable*diffusion*|*sd_xl*|*sdxl*|*flux*|*/imagen/*)         echo "🎨 IMAGEN (generacion)";;
        *paddle*|*pp-ocr*|*ppocr*|*trocr*|*/ocr/*|*tesseract*)       echo "🔤 OCR";;
        *whisper*|*wav2vec*|*faster-whisper*)                        echo "🎙  ASR (audio→texto)";;
        *demucs*|*spleeter*|*htdemucs*|*mdx*)                        echo "🎚  SEPARACION de audio";;
        *xtts*|*coqui*|*piper*|*vits*|*bark*|*tacotron*|*/tts*)      echo "🗣  TTS (texto→voz)";;
        *resemblyzer*|*speechbrain*|*pyannote*|*ecapa*|*xvector*)    echo "👤 HABLANTES (diarizacion)";;
        *minilm*|*sentence-transformers*|*bge*|*e5-*|*reranker*|*cross-encoder*|*/semantico/*) echo "🧬 EMBED/RERANK";;
        *.gguf)                                                      echo "🧠 LLM (gguf)";;
        *)                                                           echo "❔ otros";;
    esac
}

echo "=================================================================="
echo " INVENTARIO DE MODELOS · host: $(hostname 2>/dev/null || echo '?') · $(date '+%Y-%m-%d %H:%M')"
echo "=================================================================="

for r in "${ROOTS[@]}"; do
    [ -d "$r" ] || continue
    find "$r" -maxdepth 7 -type f \( \
        -iname '*.gguf' -o -iname '*.ggml' -o -iname '*.safetensors' -o -iname '*.pt' -o \
        -iname '*.pth'  -o -iname '*.onnx' -o -iname '*.bin'         -o -iname '*.tflite' -o \
        -iname '*.mlmodel' -o -iname '*.npz' -o -iname '*.ckpt' \) 2>/dev/null
done | sort -u > "$TMP"

n="$(wc -l < "$TMP" | tr -d ' ')"
if [ "$n" -eq 0 ]; then echo "🔎 no encontré ficheros de modelo en las raíces escaneadas."; exit 0; fi

while IFS= read -r f; do printf '%s\t%s\n' "$(clasifica "$f")" "$f"; done < "$TMP" | sort > "$TMP2"

cut -f1 "$TMP2" | uniq | while IFS= read -r cat; do
    echo; echo "$cat"
    grep -F "$cat"$'\t' "$TMP2" | cut -f2- | while IFS= read -r f; do
        printf '   • %-6s %s\n' "$(du -h "$f" 2>/dev/null | cut -f1)" "$f"
    done
done

echo; echo "------------------------------------------------------------------"
echo " RESUMEN por capacidad (nº ficheros):"
cut -f1 "$TMP2" | sort | uniq -c | sort -rn | sed 's/^/   /'
echo " TOTAL: $n ficheros de modelo."
echo "------------------------------------------------------------------"
