#!/bin/bash
# 🗂 =====================================================================
# 🗂 REORDENAR SSD — consolida el zoo de modelos de la Extreme SSD en un árbol
# 🗂 limpio por capacidad:  MODELOS/{llm,multimodal,audio,embed}.
# 🗂 MUEVE dentro de la MISMA SSD (instantáneo, 0 espacio extra). NO borra nada:
# 🗂 el cajón duplicado "modelos/" va a llm/_revisar/ para que TÚ decidas.
# 🗂 Por defecto DRY-RUN (solo enseña). Para hacerlo de verdad:  --aplicar
# 🗂 Uso (desde el MacBook, la SSD está en el mini):
# 🗂   ssh MINI 'bash -s'              < reordenar_ssd.sh    # ver el plan
# 🗂   ssh MINI 'bash -s -- --aplicar' < reordenar_ssd.sh    # ejecutarlo
# 🗂 =====================================================================
set -uo pipefail

SSD="${SSD_DIR:-/Volumes/Extreme SSD}"
SRC="$SSD/Macbook/modelos_grandes"
D="$SSD/MODELOS"
MIN_MB="${MIN_MB:-50}"                  # ignora ficheros < esto (vocab/stubs)
APLICAR=0; [ "${1:-}" = "--aplicar" ] && APLICAR=1

log()   { printf '🗂 %s\n' "$*"; }
crear() { if [ "$APLICAR" = 1 ]; then mkdir -p "$1"; else printf '   [dry] mkdir -p %s\n' "${1##*/MODELOS/}"; fi; }
mover() {  # $1 fichero  $2 dir_destino
    if [ "$APLICAR" = 1 ]; then mkdir -p "$2"; mv -n "$1" "$2/"
    else printf '   [dry] mv  %-44s →  %s/\n' "$(basename "$1")" "${2##*/MODELOS/}"; fi
}
tam_mb() { local b; b="$(stat -f%z "$1" 2>/dev/null || stat -c%s "$1" 2>/dev/null || echo 0)"; echo $(( b / 1048576 )); }

[ -d "$SSD" ] || { log "❌ SSD no montada en: $SSD"; exit 1; }
[ -d "$SRC" ] || { log "❌ no encuentro el zoo en: $SRC"; exit 1; }
[ "$APLICAR" = 1 ] && log "═══ MODO REAL (--aplicar) ═══" || log "═══ DRY-RUN (solo enseño · añade --aplicar para hacerlo) ═══"

# 1) árbol limpio por capacidad
for d in llm multimodal audio embed; do crear "$D/$d"; done

# 2) relocaliza los .gguf grandes por categoría (mv = instantáneo, misma SSD, no gasta espacio)
shopt -s nullglob
cat_n=0; rev_n=0
for catdir in "$SRC"/*/; do
    name="$(basename "$catdir")"
    for f in "$catdir"*.gguf; do
        [ -f "$f" ] || continue
        [ "$(tam_mb "$f")" -lt "$MIN_MB" ] && continue        # salta vocab/stubs pequeños
        if [ "$name" = "modelos" ]; then mover "$f" "$D/llm/_revisar"; rev_n=$((rev_n+1))
        else mover "$f" "$D/llm/$name"; cat_n=$((cat_n+1)); fi
    done
done
shopt -u nullglob

log "Plan: $cat_n modelos → su categoría  ·  $rev_n del cajón 'modelos/' → _revisar (duplicados a decidir)"

# 3) manifiesto (solo en modo real)
if [ "$APLICAR" = 1 ]; then
    man="$D/_MANIFIESTO.tsv"
    { printf 'capacidad\tcategoria\tmodelo\ttamano\n'
      find "$D" -type f -iname '*.gguf' 2>/dev/null | while IFS= read -r f; do
          rel="${f##*/MODELOS/}"; printf 'llm\t%s\t%s\t%s\n' "$(dirname "$rel")" "$(basename "$f")" "$(du -h "$f" 2>/dev/null | cut -f1)"
      done; } > "$man"
    log "manifiesto → $man  ·  carpetas viejas vacías: revísalas y las quitas tú."
fi
