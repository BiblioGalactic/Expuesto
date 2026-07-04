#!/bin/bash
# 🗄️ =====================================================================
# 🗄️ ARCHIVADO — rota CARTAS.md cuando pesa (RONDA 4 · diseño Opus).
# 🗄️   Lo VIEJO (~70%, cortado en FRONTERA de cabecera '## ', jamás a media
# 🗄️   carta) → info/historico/CARTAS_YYYY-MM.md. Reabre un CARTAS ligero con
# 🗄️   RESUMEN EJECUTIVO determinista (índice de lo archivado + estado del sistema).
# 🗄️   CARTAS = fuente ÚNICA (Gustavo). MISMO cerrojo que reportar.sh (sin carreras).
# 🗄️   Corte por LÍNEAS (no bytes): inmune al multibyte de los emojis.
# 🗄️ Criterios (con --aplicar aplica si se cumple ALGUNO; --forzar salta el gate):
# 🗄️   tamaño > CARTAS_MAX_KB (450) · el día 1 del mes · manual.
# 🗄️ Uso:  ./archivado.sh            (DRY-RUN: enseña el plan)
# 🗄️       ./archivado.sh --aplicar  [--forzar]
# 🗄️ =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
CARTAS="${CARTAS_MD:-$BASE/info/CARTAS.md}"
HIST_DIR="$BASE/info/historico"
ESTADO="$BASE/data/estado_sistema.json"
BACKUPS="$BASE/trash/backups"
MAX_KB="${CARTAS_MAX_KB:-450}"
ARCH_PCT="${CARTAS_ARCHIVAR_PCT:-70}"       # % de LÍNEAS que se archiva; el resto se retiene

APLICAR=0; FORZAR=0
for a in "$@"; do case "$a" in --aplicar) APLICAR=1 ;; --forzar) FORZAR=1 ;; esac; done

# shellcheck disable=SC1091
export LOCK_MAXEDAD="${LOCK_MAXEDAD:-60}"   # el lock de CARTAS dura seg → uno >60s está muerto: auto-cura el huérfano
source "$BASE/lock.sh"
TMPS=()
cleanup() { soltar_locks 2>/dev/null || true; for t in "${TMPS[@]:-}"; do [ -n "${t:-}" ] && rm -f "$t" 2>/dev/null || true; done; }
trap cleanup EXIT

log() { printf '[%s] 🗄️  %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

validar() {
    [ -f "$CARTAS" ] || { err "no encuentro el epistolar: $CARTAS"; exit 1; }
    for c in awk grep sed date wc mktemp; do command -v "$c" >/dev/null || { err "falta $c"; exit 1; }; done
}

# ¿toca archivar por criterio? 0=sí · 1=no
toca_archivar() {
    [ "$FORZAR" = 1 ] && { log "forzado (--forzar)"; return 0; }
    local kb dia
    kb=$(( $(wc -c < "$CARTAS") / 1024 )); dia="$(date +%d)"
    [ "$kb" -gt "$MAX_KB" ] && { log "criterio ✓ tamaño ${kb}KB > ${MAX_KB}KB"; return 0; }
    [ "$dia" = "01" ]      && { log "criterio ✓ día 1 del mes"; return 0; }
    log "sin criterio (${kb}KB ≤ ${MAX_KB}KB · día $dia). --forzar para archivar igual."
    return 1
}

# frontera de corte: primera cabecera '## ' en/ tras el ARCH_PCT% de las líneas (line-based)
frontera() {
    local total thr
    total="$(wc -l < "$CARTAS")"
    thr=$(( total * ARCH_PCT / 100 ))
    awk -v thr="$thr" 'NR>=thr && /^## / { print NR; exit }' "$CARTAS"
}

ejecutar() {
    local cut n mes hist tmp_new
    cut="$(frontera)"
    if [ -z "${cut:-}" ] || [ "${cut:-0}" -le 1 ]; then
        err "sin frontera '## ' limpia ≥${ARCH_PCT}% de líneas — no archivo (ajusta CARTAS_ARCHIVAR_PCT)"; exit 1
    fi
    n="$(sed -n "1,$((cut-1))p" "$CARTAS" | grep -c '^## ' || true)"
    mes="$(date +%Y-%m)"; hist="$HIST_DIR/CARTAS_${mes}.md"

    log "plan: archivar $n cartas (líneas 1..$((cut-1))) → $hist · retener desde la línea $cut ($(wc -l < "$CARTAS") totales)"
    if [ "$APLICAR" != 1 ]; then
        log "DRY-RUN (nada tocado). Índice de lo que archivaría:"
        sed -n "1,$((cut-1))p" "$CARTAS" | grep '^## ' | sed 's/^## /   · /' | head -10
        [ "$n" -gt 10 ] && log "   … y $((n-10)) más. Aplica con: $0 --aplicar"
        return 0
    fi

    mkdir -p "$BACKUPS" "$HIST_DIR"
    cp -p "$CARTAS" "$BACKUPS/CARTAS.md.$(date +%Y%m%d_%H%M%S)_prearchivado.bak"   # reescribimos: backup OBLIGATORIO

    # cerrojo (el MISMO que reportar.sh) con retry — el archivado jamás pisa una escritura
    local i=0
    until tomar_lock cartas 2>/dev/null; do
        i=$((i+1)); [ "$i" -ge 15 ] && { err "epistolar ocupado ~3s (¿lock huérfano? data/.lock_cartas)"; exit 1; }; sleep 0.2
    done

    # 1) lo viejo → histórico del mes (append con marca de sesión)
    { printf '\n<!-- ===== archivado %s · %s cartas ===== -->\n' "$(date '+%Y-%m-%d %H:%M')" "$n"
      sed -n "1,$((cut-1))p" "$CARTAS"; } >> "$hist"

    # 2) CARTAS nuevo = resumen ejecutivo determinista + trozo retenido
    tmp_new="$(mktemp "$(dirname "$CARTAS")/.cartas_new.XXXXXX")"; TMPS+=("$tmp_new")   # MISMO fs que CARTAS → mv atómico (no inter-device)
    {
        printf '# 📁 CARTAS — la mesa (epistolar vivo)\n\n'
        printf '## 🗄️ Resumen ejecutivo · archivado %s\n\n' "$(date '+%Y-%m-%d %H:%M')"
        printf '**%s cartas** movidas a `info/historico/CARTAS_%s.md` (histórico completo ahí).\n\n' "$n" "$mes"
        if [ -f "$ESTADO" ]; then
            ESTADO_JSON="$ESTADO" python3 - <<'PY' 2>/dev/null || true
import json, os
try:
    d = json.load(open(os.environ["ESTADO_JSON"]))
    m = d.get("metricas", {}); b = d.get("banco", {}); ab = m.get("ab") or {}
    print("**Estado ahora:** %s · CRAG %s · banco %s/%s · A/B %s-%s-%s · %s" % (
        d.get("estado_general", "?"), m.get("crag", "?"), b.get("pendientes", "?"),
        b.get("tope", "?"), ab.get("a", "?"), ab.get("b", "?"), ab.get("empates", "?"),
        d.get("acta", "")))
    print()
except Exception:
    pass
PY
        fi
        printf '**Índice de lo archivado:**\n\n'
        sed -n "1,$((cut-1))p" "$CARTAS" | grep '^## ' | sed 's/^## /- /'
        printf '\n> Histórico completo → `info/historico/CARTAS_%s.md`\n\n---\n' "$mes"
        tail -n +"$cut" "$CARTAS"                         # el trozo retenido (arranca en una cabecera '## ')
    } > "$tmp_new"

    mv "$tmp_new" "$CARTAS"                               # reemplazo atómico bajo el cerrojo
    log "hecho: $n cartas → $(basename "$hist") · CARTAS reabierto $(( $(wc -c < "$CARTAS")/1024 ))KB con resumen ejecutivo"
}

validar
CRITERIO=0; toca_archivar && CRITERIO=1 || true
if [ "$APLICAR" = 1 ] && [ "$CRITERIO" = 0 ] && [ "$FORZAR" = 0 ]; then
    err "no se cumple ningún criterio. --forzar para archivar igual (o baja CARTAS_MAX_KB)."; exit 0
fi
ejecutar
