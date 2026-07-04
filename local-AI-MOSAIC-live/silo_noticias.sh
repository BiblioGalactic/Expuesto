#!/bin/bash
# 📰 =====================================================================
# 📰 SILO NOTICIAS — flujo continuo. Si el silo se queda sin trabajo, copia un
# 📰 pequeño número de noticias YA descargadas (hackernews, periódico, biblioteca)
# 📰 a silo/ para que MOSAIC nunca pare por falta de material.
# 📰 COPIA (no mueve) + memoria UNIFICADA → cada noticia entra UNA vez, sin agotar tu corpus.
# 📰 Uso:  ./silo_noticias.sh [N]    (def. 5)
# 📰 =====================================================================
set -uo pipefail

SILO="${SILO_DIR:-$HOME/Mosaic_privado/silo}"
MEM="${MEMORIA:-$HOME/Mosaic_privado/memoria.sh}"   # ¿ya visto? unificado (#61)
N="${1:-${NOTICIAS_LOTE:-5}}"
FUENTES=(
    "$HOME/proyecto/laboratorio/resultados/hackernews"
    "$HOME/proyecto/txtapoyo/periodico"
    "$HOME/proyecto/laboratorio/resultados/biblioteca"
)
log() { printf '[%s] 📰 %s\n' "$(date +%H:%M:%S)" "$*"; }
mkdir -p "$SILO"

copiados=0
for dir in "${FUENTES[@]}"; do
    [ -d "$dir" ] || continue
    while IFS= read -r f; do
        [ "$copiados" -ge "$N" ] && break 2
        [ -f "$f" ] || continue
        bash "$MEM" visto noticias "$f" && continue          # ya entró una vez (memoria unificada)
        if cp "$f" "$SILO/noticia_$(basename "$f")" 2>/dev/null; then
            bash "$MEM" marcar noticias "$f"; copiados=$((copiados + 1))
        fi
    done < <(find "$dir" -name '*.txt' 2>/dev/null)
done
log "flujo continuo: $copiados noticia(s) nuevas → silo (de tu corpus, sin agotarlo)"
