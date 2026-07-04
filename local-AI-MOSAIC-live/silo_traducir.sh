#!/bin/bash
# 🌐 =====================================================================
# 🌐 SILO TRADUCIR (#78) — traduce una transcripción a un idioma destino.
# 🌐 Intenta primero argos-translate (OFFLINE, local); si no está, usa el
# 🌐 cluster LLM (MOSAIC_LLM_BASE_URL). Escribe la traducción y NO toca el
# 🌐 original. Degrada sin romper (si no hay ninguno, sale 1 en silencio).
# 🌐 Uso:  ./silo_traducir.sh ARCHIVO.txt IDIOMA [salida.txt]
# 🌐       IDIOMA: en · es · ja · de · fr …
# 🌐 =====================================================================
set -uo pipefail

f="${1:?uso: silo_traducir.sh ARCHIVO.txt IDIOMA [salida.txt]}"
dst="${2:?idioma destino (ej: en, es, ja)}"
out="${3:-${f%.*}_$dst.txt}"
[ -f "$f" ] || { echo "no existe: $f" >&2; exit 1; }
texto="$(head -c "${TRAD_MAX:-6000}" "$f")"
[ -n "${texto// /}" ] || { echo "vacío: $f" >&2; exit 1; }

# 1) argos-translate (offline) si está instalado
if command -v argos-translate >/dev/null 2>&1; then
    if printf '%s' "$texto" | argos-translate --to "$dst" > "$out" 2>/dev/null && [ -s "$out" ]; then
        echo "$out"; exit 0
    fi
fi

# 2) cluster LLM (mismo endpoint que MOSAIC)
URL="${TRAD_URL:-${MOSAIC_LLM_BASE_URL:-http://127.0.0.1:8090/v1}}"
prompt="$(printf 'Traduce el siguiente texto al idioma "%s". Devuelve SOLO la traducción, sin comentarios ni el original.\n\n%s' "$dst" "$texto")"
printf '%s' "$prompt" | python3 - "$URL" "$out" <<'PY'
import sys, json, urllib.request
url, out = sys.argv[1], sys.argv[2]
contenido = sys.stdin.read()
body = json.dumps({"model": "local", "messages": [{"role": "user", "content": contenido}],
                   "max_tokens": 1500, "temperature": 0.2}).encode("utf-8")
try:
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        t = json.loads(r.read())["choices"][0]["message"]["content"].strip()
    if not t:
        sys.exit(1)
    open(out, "w", encoding="utf-8").write(t + "\n")
    print(out)
except Exception as e:
    print(f"traducción no disponible: {e}", file=sys.stderr); sys.exit(1)
PY
