#!/bin/bash
# 🔮 =====================================================================
# 🔮 FUENTE ORÁCULO — adaptador: convierte los HALLAZGOS del oráculo de código
# 🔮 (~/oraculo) en TAREAS de MOSAIC y las encola (fuente=oraculo). El oráculo
# 🔮 descubre repos; MOSAIC los usa para exponer huecos y crear capacidades.
# 🔮 NO reimplementa el crawler: lo puentea. Idempotente y reanudable (registro 'vistos').
# 🔮 Lee tanto hallazgos/ vivos como los lotes/*.tar.gz comprimidos.
# 🔮 Uso:  ./fuente_oraculo.sh            (una pasada; encola lo nuevo con nota suficiente)
# 🔮 =====================================================================
set -euo pipefail

HOME_USER="${HOME_USER:-$HOME}"
MOSAIC_DIR="${MOSAIC_DIR:-$HOME_USER/Mosaic_privado}"
COLA_SH="${COLA_SH:-$MOSAIC_DIR/cola.sh}"
ORACULO_BASE="${ORACULO_BASE:-$HOME_USER/oraculo}"
HALLAZGOS="$ORACULO_BASE/hallazgos"
LOTES="$ORACULO_BASE/lotes"
SEEN="${ORACULO_SEEN:-$MOSAIC_DIR/data/oraculo_vistos.txt}"   # repos ya ingeridos (idempotencia)
MEM="${MEMORIA:-$MOSAIC_DIR/memoria.sh}"                      # ¿ya visto? unificado (#61)
NOTA_MIN="${ORACULO_NOTA_MIN:-7}"                             # solo encola nota >= esto
MAX="${ORACULO_MAX:-0}"                                       # 0 = sin límite por pasada

TMP="$(mktemp -d)"; cleanup() { rm -rf "$TMP" 2>/dev/null || true; }; trap cleanup EXIT
log() { printf '[%s] 🔮 %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ✗  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

validar() {
    command -v python3 >/dev/null || { err "falta python3"; exit 1; }
    command -v tar >/dev/null     || { err "falta tar"; exit 1; }
    [ -f "$COLA_SH" ] || { err "no encuentro cola.sh en $COLA_SH"; exit 1; }
    mkdir -p "$(dirname "$SEEN")"; touch "$SEEN"
}

# veredicto.json (+README) -> JSON {repo,nota,pregunta} por stdout
meta_de() {
    python3 - "$1" "${2:-}" <<'PY'
import json, sys
try:
    v = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(1)
rm = ""
if len(sys.argv) > 2 and sys.argv[2]:
    try:
        rm = open(sys.argv[2], encoding="utf-8").read()[:600]
    except Exception:
        rm = ""
repo = v.get("repo", "?"); cat = v.get("categoria", "general")
raz = v.get("razon", ""); fun = v.get("funcion_util", ""); nec = v.get("necesidad", "")
q = (f"El repositorio «{repo}» (categoría: {cat}) aporta: {raz}. "
     f"Parte útil: {fun}. Necesidad original: {nec}. "
     f"¿Qué capacidad GENERAL y reutilizable debería tener MOSAIC para resolver tareas de este tipo? "
     f"Contexto (README): {rm}")
print(json.dumps({"repo": repo, "nota": v.get("nota", 0), "pregunta": q}, ensure_ascii=False))
PY
}

procesar() {   # $1 veredicto.json   $2 README
    local meta repo nota preg
    meta="$(meta_de "$1" "$2")" || { err "  veredicto ilegible: $1"; return 0; }
    repo="$(printf '%s' "$meta" | python3 -c 'import json,sys;print(json.load(sys.stdin)["repo"])')"
    nota="$(printf '%s' "$meta" | python3 -c 'import json,sys;print(json.load(sys.stdin)["nota"])')"
    preg="$(printf '%s' "$meta" | python3 -c 'import json,sys;print(json.load(sys.stdin)["pregunta"])')"
    awk -v n="$nota" -v m="$NOTA_MIN" 'BEGIN{exit !(n+0>=m+0)}' \
        || { log "  · $repo nota $nota < $NOTA_MIN, salto"; return 0; }
    bash "$MEM" visto oraculo "$repo" && { log "  · $repo ya ingerido, salto"; return 0; }
    if "$COLA_SH" add "$preg" oraculo >/dev/null; then
        bash "$MEM" marcar oraculo "$repo"; log "  + encolado: $repo (nota $nota)"; ENCOLADOS=$((ENCOLADOS + 1))
    else
        err "  no pude encolar $repo"
    fi
}

ejecutar() {
    ENCOLADOS=0
    if [ -d "$HALLAZGOS" ]; then
        while IFS= read -r vj; do
            [ -z "$vj" ] && continue
            procesar "$vj" "$(dirname "$vj")/README.md"
            [ "$MAX" -gt 0 ] && [ "$ENCOLADOS" -ge "$MAX" ] && { log "límite $MAX alcanzado"; return 0; }
        done < <(find "$HALLAZGOS" -name veredicto.json 2>/dev/null)
    fi
    if [ -d "$LOTES" ]; then                       # lotes comprimidos del oráculo
        for tgz in "$LOTES"/*.tar.gz; do
            [ -e "$tgz" ] || continue
            local d="$TMP/$(basename "$tgz" .tar.gz)"; mkdir -p "$d"
            tar -xzf "$tgz" -C "$d" 2>/dev/null || continue
            while IFS= read -r vj; do
                [ -z "$vj" ] && continue
                procesar "$vj" "$(dirname "$vj")/README.md"
                [ "$MAX" -gt 0 ] && [ "$ENCOLADOS" -ge "$MAX" ] && { log "límite $MAX alcanzado"; return 0; }
            done < <(find "$d" -name veredicto.json 2>/dev/null)
        done
    fi
    log "fuente oráculo: pasada completa · $ENCOLADOS encolados."
}

validar
ejecutar
