#!/bin/bash
# 🧭 =====================================================================
# 🧭 tema_modelo.sh — pregunta a UN modelo del roster un TEMA de búsqueda
# 🧭 para el recolector (cada pasada, el loop rota qué modelo pregunta →
# 🧭 variedad orgánica en vez de una lista fija que se agota).
# 🧭 Uso:   tema_modelo.sh "Nombre@http://host:puerto"
# 🧭 Sale:  un tema saneado (2-6 palabras) · o VACÍO si el modelo cae
# 🧭        (el loop entonces cae a la lista estática — nunca se rompe).
# 🧭 =====================================================================
set -uo pipefail

spec="${1:-}"; url="${spec#*@}"
[ -n "$url" ] && [[ "$url" == http* ]] || { echo ""; exit 0; }

PROMPT='Propon UN tema concreto y buscable en GitHub (2 a 5 palabras EN INGLES) de una capacidad de programacion util que un asistente de codigo deberia dominar. Varia el area (redes, datos, concurrencia, seguridad, testing, parsers, CLI...). Responde SOLO el tema: sin comillas, sin explicacion, sin puntuacion final.'

# cuerpo JSON sin líos de comillas (lo arma python desde argv)
BODY="$(python3 -c 'import json,sys; print(json.dumps({"model":"local","messages":[{"role":"user","content":sys.argv[1]}],"max_tokens":24,"temperature":1.1}))' "$PROMPT")"

# OJO: `curl | python3 - <<PY` haría que el heredoc (el programa) gane el stdin y la respuesta
# de curl se pierda. Por eso la pasamos por ENV (RESP), no por stdin.
RESP="$(curl -s --max-time 30 "${url%/}/v1/chat/completions" \
     -H 'Content-Type: application/json' -d "$BODY" 2>/dev/null || true)"
RESP="$RESP" python3 - <<'PY' 2>/dev/null || echo ""
import os, json, re
raw = os.environ.get("RESP", "")
try:
    t = json.loads(raw)["choices"][0]["message"]["content"] or ""
except Exception:
    t = ""
t = t.strip()
# Qwen3 puede razonar: quita bloques <think>...</think> y quédate con la última línea con letras
t = re.sub(r"(?is)<think>.*?</think>", " ", t)
lineas = [l.strip() for l in t.splitlines() if re.search(r"[A-Za-z]", l)]
t = lineas[-1] if lineas else ""
t = re.sub(r"[^A-Za-z0-9 +.#-]", " ", t)     # solo ascii buscable (fuera comillas/markdown/emoji)
t = re.sub(r"\s+", " ", t).strip()
print(" ".join(t.split()[:6]))
PY
