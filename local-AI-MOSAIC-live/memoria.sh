#!/bin/bash
# 🧠 =====================================================================
# 🧠 MEMORIA — "¿ya lo he visto?" UNIFICADO y reanudable para TODAS las fuentes.
# 🧠 Un solo registro: data/vistos.jsonl  (sustituye a .noticias_vistos,
# 🧠 .libros_vistos, cuarentena/.clonados, data/oraculo_vistos). La planta ya
# 🧠 rota data/vistos*.jsonl. Identidad EXACTA por (ambito|clave) con hash →
# 🧠 a prueba de rutas/URLs con caracteres raros.
# 🧠 Uso:
# 🧠   memoria.sh nuevo  <ambito> <clave>   # 0 = NUEVO (y lo marca) · 1 = ya estaba
# 🧠   memoria.sh visto  <ambito> <clave>   # 0 = ya estaba · 1 = nuevo (no marca)
# 🧠   memoria.sh marcar <ambito> <clave>   # lo registra (idempotente)
# 🧠   memoria.sh migrar                    # importa los registros viejos (NO borra)
# 🧠   memoria.sh estado                    # cuántos por ámbito
# 🧠 =====================================================================
set -uo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
REG="${VISTOS_REG:-$BASE/data/vistos.jsonl}"
SILO="${SILO_DIR:-$BASE/silo}"
CUAR="${CUARENTENA_DIR:-$BASE/cuarentena}"
mkdir -p "$(dirname "$REG")"; touch "$REG"

_hash()   { printf '%s' "$1|$2" | { shasum 2>/dev/null || sha1sum 2>/dev/null; } | cut -d' ' -f1; }
_visto()  { grep -qF "\"h\":\"$(_hash "$1" "$2")\"" "$REG"; }
_marcar() {
    _visto "$1" "$2" && return 0
    local k; k="$(printf '%s' "$2" | tr -d '"\\' | tr '\n\t' '  ' | cut -c1-140)"
    printf '{"a":"%s","h":"%s","k":"%s","t":%s}\n' "$1" "$(_hash "$1" "$2")" "$k" "$(date +%s)" >> "$REG"
}
_importar() {   # ambito  fichero-plano (una clave por línea)
    [ -f "$2" ] || { echo "  $1: (sin $(basename "$2"))"; return 0; }
    local n=0 linea
    while IFS= read -r linea; do
        [ -n "$linea" ] || continue
        _visto "$1" "$linea" || { _marcar "$1" "$linea"; n=$((n+1)); }
    done < "$2"
    echo "  $1: +$n (de $(basename "$2"))"
}

case "${1:-}" in
    nuevo)  [ "$#" -ge 3 ] || { echo "uso: memoria.sh nuevo <ambito> <clave>" >&2; exit 2; }
            _visto "$2" "$3" && exit 1; _marcar "$2" "$3"; exit 0 ;;
    visto)  [ "$#" -ge 3 ] || { echo "uso: memoria.sh visto <ambito> <clave>" >&2; exit 2; }
            _visto "$2" "$3" && exit 0 || exit 1 ;;
    marcar) [ "$#" -ge 3 ] || { echo "uso: memoria.sh marcar <ambito> <clave>" >&2; exit 2; }
            _marcar "$2" "$3"; exit 0 ;;
    migrar) echo "🧠 importando registros viejos → $REG (los originales NO se borran):"
            _importar noticias   "$SILO/.noticias_vistas.txt"
            _importar libros     "$SILO/.libros_vistos.txt"
            _importar cuarentena "$CUAR/.clonados.txt"
            _importar oraculo    "$BASE/data/oraculo_vistos.txt"
            echo "  total: $(wc -l < "$REG" | tr -d ' ') entradas" ;;
    estado) echo "🧠 vistos por ámbito (en $(basename "$REG")):"
            grep -oE '"a":"[^"]+"' "$REG" 2>/dev/null | sort | uniq -c | sed 's/^/  /' || echo "  (vacío)" ;;
    *) echo "uso: memoria.sh nuevo|visto|marcar <ambito> <clave> | migrar | estado" >&2; exit 2 ;;
esac
