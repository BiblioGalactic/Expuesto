#!/bin/bash
# 📚 =====================================================================
# 📚 SILO LIBROS — flujo continuo desde tu corpus Gutenberg (27 GB · 69k libros).
# 📚 Si el silo se queda sin trabajo, toma N libros NO vistos, les quita el
# 📚 boilerplate LEGAL de Gutenberg (marcadores *** START/END ***) y deja un
# 📚 FRAGMENTO crudo en silo/ (libro_<lang>_<id>.txt).
# 📚 El cuerpo queda SUCIO a propósito (saltos duros, notas, restos): es el
# 📚 gimnasio para que MOSAIC haga EMERGER una capacidad de REFINADO/INGESTA.
# 📚 No es conocimiento; es entrenar el ACTO de limpiar texto difícil.
# 📚 Genera fragmentos (no toca tu corpus) + memoria UNIFICADA → sin agotar.
# 📚 Uso:  ./silo_libros.sh [N]    (def. 3)
# 📚 =====================================================================
set -uo pipefail

GUT="${GUTENBERG_DIR:-$HOME/wikirag/gutenberg}"
SILO="${SILO_DIR:-$HOME/Mosaic_privado/silo}"
MEM="${MEMORIA:-$HOME/Mosaic_privado/memoria.sh}"   # ¿ya visto? unificado (#61)
CATALOGO="$GUT/pg_catalog.csv"
N="${1:-${LIBROS_LOTE:-3}}"
OFFSET="${LIBROS_OFFSET:-40}"        # líneas a saltar tras el marcador (portada/índice)
TROZO="${LIBROS_TROZO:-3500}"        # chars del fragmento (deja hueco a la cabecera)
IDIOMAS=(txt_es txt_en txt_fr txt_it txt_de txt_pt)   # rota; español primero

log() { printf '[%s] 📚 %s\n' "$(date +%H:%M:%S)" "$*"; }
[ -d "$GUT" ] || { log "no encuentro el corpus en $GUT (define GUTENBERG_DIR)"; exit 0; }
mkdir -p "$SILO"

titulo() {  # id → título (best-effort desde el catálogo)
    [ -f "$CATALOGO" ] || { echo ""; return; }
    grep -m1 "^$1," "$CATALOGO" 2>/dev/null | cut -d, -f4 | tr -d '"' | cut -c1-80
}

# desollado: imprime SOLO lo que hay ENTRE los marcadores legales *** START/END ***
despelleja() {  # archivo → cuerpo por stdout (sin la jerga legal)
    awk '
        /\*\*\* *START OF TH(E|IS) PROJECT GUTENBERG/ { dentro=1; next }
        /\*\*\* *END OF TH(E|IS) PROJECT GUTENBERG/   { dentro=0 }
        dentro { print }
    ' "$1"
}

copiados=0
for sub in "${IDIOMAS[@]}"; do
    dir="$GUT/$sub"; [ -d "$dir" ] || continue
    lang="${sub#txt_}"
    while IFS= read -r f; do
        [ "$copiados" -ge "$N" ] && break 2
        [ -f "$f" ] || continue
        bash "$MEM" visto libros "$f" && continue            # ya entró una vez (memoria unificada)
        id="$(basename "$f" .txt)"; id="${id#pg}"
        # fragmento: cuerpo sin boilerplate, saltando portada/índice, TROZO chars.
        # Si no hay marcadores (formato viejo) → archivo crudo como respaldo.
        frag="$(despelleja "$f" | tail -n +"$OFFSET" | head -c "$TROZO")"
        [ -z "${frag// /}" ] && frag="$(tail -n +"$OFFSET" "$f" 2>/dev/null | head -c "$TROZO")"
        [ -z "${frag// /}" ] && frag="$(head -c "$TROZO" "$f" 2>/dev/null)"
        if [ -z "${frag// /}" ]; then bash "$MEM" marcar libros "$f"; continue; fi   # vacío → marca y sigue
        tit="$(titulo "$id")"
        out="$SILO/libro_${lang}_${id}.txt"
        {
            printf 'FRAGMENTO CRUDO de un libro de Gutenberg, SIN refinar.\n'
            printf 'id=%s · idioma=%s · titulo=%s\n' "$id" "$lang" "${tit:-?}"
            printf 'Viene con formato irregular (saltos de linea duros, notas del transcriptor, restos de OCR).\n\n'
            printf '%s\n' "$frag"
        } > "$out" && { bash "$MEM" marcar libros "$f"; copiados=$((copiados + 1)); }
    done < <(find "$dir" -name '*.txt' 2>/dev/null)
done
log "flujo continuo: $copiados fragmento(s) de libro → silo (gimnasio de refinado; corpus intacto)"
