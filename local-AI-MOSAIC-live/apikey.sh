#!/bin/bash
# 🔑 =====================================================================
# 🔑 apikey.sh — buscador CENTRAL de claves. Toda API pide su clave aquí:
# 🔑     KEY="$(~/Mosaic_privado/apikey.sh github)"
# 🔑 Lee info/apiskeys.txt (formato SERVICIO|clave). Tolerante: case-insensitive
# 🔑 y normaliza espacios/guiones (apikey.sh "alpha vantage" → ALPHA_VANTAGE).
# 🔑 La clave sale por STDOUT (para capturarla); los errores/listado por STDERR.
# 🔑 =====================================================================
set -euo pipefail

ARCHIVO="${APIKEYS_FILE:-$HOME/Mosaic_privado/info/apiskeys.txt}"
[ -f "$ARCHIVO" ] || { echo "🔑 no existe $ARCHIVO" >&2; exit 1; }

# normaliza la consulta igual que las etiquetas del fichero
q="$(printf '%s' "${1:-}" | tr '[:lower:]' '[:upper:]' | sed -E 's/[^A-Z0-9]+/_/g; s/^_+//; s/_+$//')"
if [ -z "$q" ]; then
    echo "uso: apikey.sh <servicio>   ·   servicios disponibles:" >&2
    grep -v '^#' "$ARCHIVO" | cut -d'|' -f1 | sed 's/^/  · /' >&2
    exit 1
fi

# busca la etiqueta normalizada; imprime TODO lo que va tras el primer '|' (valor intacto)
clave="$(awk -v s="$q" '
    /^[[:space:]]*#/ { next }
    {
        p = index($0, "|"); if (p == 0) next
        k = toupper(substr($0, 1, p-1)); gsub(/[^A-Z0-9]+/, "_", k); sub(/^_+/, "", k); sub(/_+$/, "", k)
        if (k == s) { print substr($0, p+1); exit }
    }' "$ARCHIVO")"

if [ -z "$clave" ]; then
    echo "🔑 sin clave para «${1:-}». Servicios disponibles:" >&2
    grep -v '^#' "$ARCHIVO" | cut -d'|' -f1 | sed 's/^/  · /' >&2
    exit 2
fi
printf '%s' "$clave"
