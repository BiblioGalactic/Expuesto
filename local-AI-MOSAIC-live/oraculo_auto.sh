#!/bin/bash
# 🔮 =====================================================================
# 🔮 ORACULO AUTO — automatiza el scraping: elige un tema, corre el crawler
# 🔮 (descubre + juzga repos) y clona los KEEP a cuarentena. Sin comandos a mano.
# 🔮 El token sale del store central (apikey.sh github). Temas rotan desde un
# 🔮 fichero (oraculo_temas.txt) para no buscar siempre lo mismo.
# 🔮 Lo llama el ciclo en FASE 1 si ORACULO_AUTO=1. Falla en silencio si no hay token.
# 🔮 =====================================================================
set -uo pipefail

BASE="${MOSAIC_DIR:-$HOME/Mosaic_privado}"
ORACULO="${ORACULO_BIN:-$HOME/proyecto/laboratorio/script/completo/oraculo_codigo.sh}"
VENV="${ORACULO_VENV:-$HOME/wikirag/venv}"
TEMAS="${ORACULO_TEMAS:-$BASE/oraculo_temas.txt}"
CURSOR="${ORACULO_CURSOR:-$BASE/data/oraculo_tema.cursor}"
NOTA_MIN="${ORACULO_NOTA_MIN:-7}"
STARS="${ORACULO_STARS:-3}"

log() { printf '[%s] 🔮 %s\n' "$(date +%H:%M:%S)" "$*"; }

TOKEN="$("$BASE/apikey.sh" github 2>/dev/null || true)"
[ -n "$TOKEN" ] || { log "sin token github en el store · salto el oráculo auto"; exit 0; }
[ -f "$ORACULO" ] || { log "no encuentro el crawler ($ORACULO) · salto"; exit 0; }

# temas por defecto la primera vez (edítalos a tu gusto)
if [ ! -f "$TEMAS" ]; then
    printf '%s\n' \
        "rag local en bash con llama.cpp" \
        "embeddings locales con python y faiss" \
        "orquestacion de agentes llm en local" \
        "scripts bash para automatizar tareas con IA" > "$TEMAS"
    log "creado $TEMAS con temas por defecto (edítalo cuando quieras)"
fi

mapfile -t LISTA < <(grep -vE '^[[:space:]]*(#|$)' "$TEMAS")
[ "${#LISTA[@]}" -gt 0 ] || { log "no hay temas en $TEMAS · salto"; exit 0; }

idx=0; [ -f "$CURSOR" ] && idx="$(cat "$CURSOR" 2>/dev/null || echo 0)"
[[ "$idx" =~ ^[0-9]+$ ]] || idx=0
idx=$(( idx % ${#LISTA[@]} ))
QUERY="${LISTA[$idx]}"
mkdir -p "$(dirname "$CURSOR")"; echo $(( (idx + 1) % ${#LISTA[@]} )) > "$CURSOR"

log "tema [$((idx+1))/${#LISTA[@]}]: [$QUERY] -> descubre (una pasada)"
(
    [ -f "$VENV/bin/activate" ] && source "$VENV/bin/activate" 2>/dev/null || true
    GITHUB_TOKEN="$TOKEN" bash "$ORACULO" "$QUERY" --una-pasada --nota-min="$NOTA_MIN" --stars="$STARS" --max-paginas=1
) || log "crawler con incidencias (sigo)"

log "clono los KEEP a cuarentena"
bash "$BASE/cuarentena.sh" clonar || log "clonar con incidencias"
log "oráculo auto: listo (la cuarentena lo analiza en el pull: fuente_cuarentena)"
