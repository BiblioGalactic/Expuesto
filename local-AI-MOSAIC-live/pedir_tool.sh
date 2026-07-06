#!/bin/bash
# 🧰 =====================================================================
# 🧰 PEDIR_TOOL — el CLI humano del dispatcher (v2 · manifiesto Opus 13:36).
# 🧰   TODA la lógica de permisos/escalado/contrato vive en herramientas.py
# 🧰   (una sola fuente); esto solo construye el payload cómodo y enseña bonito.
# 🧰   Prioridad del ticket: LA FIJA EL AGENTE (--prioridad 1-5; default = nivel del tool).
# 🧰 Uso:  ./pedir_tool.sh <rol> <tool> [args…] [--prioridad N] [--ticket TCK-…]
# 🧰   args por tool: leer_registro RUTA · rag/buscar CONSULTA · web URL ·
# 🧰                  ocr RUTA · depositar "TEXTO"
# 🧰   crudo: ./pedir_tool.sh <rol> <tool> --json '{"campo":…}'
# 🧰 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
ROL="${1:-}"; TOOL="${2:-}"; shift 2 2>/dev/null || true

log() { printf '[%s] 🧰 %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

[ -n "$ROL" ] && [ -n "$TOOL" ] || { err 'uso: pedir_tool.sh <rol> <tool> [args…] [--prioridad N] [--ticket TCK]'; exit 2; }

PRIO=""; TICKET=""; JSON=""; POS=()
while [ $# -gt 0 ]; do case "$1" in
    --prioridad) shift; PRIO="${1:-}" ;;
    --ticket)    shift; TICKET="${1:-}" ;;
    --json)      shift; JSON="${1:-}" ;;
    *) POS+=("$1") ;;
esac; shift || true; done

if [ -z "$JSON" ]; then
    JSON="$(TOOL_J="$TOOL" python3 - "${POS[@]:-}" <<'PY'
import json, os, sys
t, a = os.environ["TOOL_J"], [x for x in sys.argv[1:] if x]
campo = {"leer_registro": "ruta", "ocr": "ruta", "web": "url",
         "buscar": "q", "rag": "q", "depositar": "texto"}.get(t)
print(json.dumps({campo: " ".join(a)} if campo and a else {}, ensure_ascii=False))
PY
)"
fi

ARGS=(--agente "$ROL" --tool "$TOOL")
[ -n "$PRIO" ] && ARGS+=(--prioridad "$PRIO")
[ -n "$TICKET" ] && ARGS+=(--ticket "$TICKET")

set +e
SALIDA="$(printf '%s' "$JSON" | MOSAIC_BASE="$BASE" python3 "$BASE/herramientas.py" "${ARGS[@]}")"
RC=$?
set -e

# enseñar bonito (el contrato es JSON; el humano merece un vistazo legible)
# ⚠️ por ENV, no por pipe: `python3 - <<PY` ocupa stdin (el clásico de la casa, cazado 5-jul)
SALIDA_J="$SALIDA" python3 - <<'PY'
import json, os
try:
    d = json.loads(os.environ.get("SALIDA_J") or "")
except Exception:
    print("(salida no-JSON del dispatcher — raro)"); raise SystemExit(0)
if d.get("ok"):
    print(f"✅ {d.get('tool','?')} · via {d.get('via','rango')}")
    print(json.dumps(d.get("result"), ensure_ascii=False, indent=1)[:1800])
else:
    print(f"⛔ {d.get('error','?')}")
    if d.get("ticket"):
        print(f"🎫 {d['ticket']} · prioridad {d.get('prioridad','?')} · está en «{d.get('rango_actual','?')}» "
              f"· cadena: {d.get('cadena','?')}")
        print(f"   {d.get('siguiente_paso','')}")
PY
exit $RC
