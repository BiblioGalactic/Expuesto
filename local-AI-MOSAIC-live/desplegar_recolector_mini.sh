#!/bin/bash
# 🛰️ =====================================================================
# 🛰️ DESPLEGAR RECOLECTOR → MINI   ·   F6 (los 6 pasos de Opus)
# 🛰️ El crawler de GitHub corre en el MINI (ocioso en FASE 1), juzga los repos
# 🛰️ con SU pequeño (no el 24B), deduplica LÉXICO (sin torch) y llena una
# 🛰️ despensa (~/oraculo). El MacBook la RECOGE sin esperar (fire-and-forget).
# 🛰️ Handoff por rsync: mini:~/oraculo/{hallazgos,lotes} → MacBook (cuarentena.sh clona).
# 🛰️ DRY-RUN por defecto.  Aplica con:  ./desplegar_recolector_mini.sh --aplicar
# 🛰️ =====================================================================
set -euo pipefail

# ── Config (rutas ABSOLUTAS: lección del ~ remoto — no tropezamos dos veces) ──
MINI_SSH="${MINI_SSH:-$USER@localhost}"
MINI_HOME="${MINI_HOME:-$HOME}"
MINI_BIN="${MINI_BIN:-$MINI_HOME/recolector}"              # scripts en el mini
MINI_ORACULO="$MINI_HOME/oraculo"                          # despensa (hallazgos/lotes)
MINI_JUEZ="${MINI_JUEZ:-http://127.0.0.1:8090}"            # juez de repos = pequeño del mini (3B) · EL 24B JAMÁS
NOTA_MIN="${NOTA_MIN:-5.5}"                                # un 3B puntúa distinto que un 24B: empezar INDULGENTE
COOLDOWN="${COOLDOWN:-1800}"                               # segundos entre pasadas (supervisión, desacoplado del ciclo)
TEMAS="${RECOLECTOR_TEMAS:-async python retries;rust cli parser;go concurrency patterns;sqlite wal queue;bash strict mode}"

MB_MOSAIC="${MB_MOSAIC:-$HOME/Mosaic_privado}"
MB_COMPLETO="${MB_COMPLETO:-$HOME/proyecto/laboratorio/script/completo}"

APLICAR=0; [ "${1:-}" = "--aplicar" ] && APLICAR=1
LOGDIR="$MB_MOSAIC/logs"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/desplegar_recolector_$(date +%Y%m%d_%H%M%S).log"
TMP="$(mktemp -d)"

log()  { echo -e "\033[0;36m[$(date +%H:%M:%S)]\033[0m $*" | tee -a "$LOG" >&2; }
ok()   { echo -e "\033[0;32m[✓]\033[0m $*"                 | tee -a "$LOG" >&2; }
warn() { echo -e "\033[1;33m[!]\033[0m $*"                 | tee -a "$LOG" >&2; }
err()  { echo -e "\033[0;31m[✗]\033[0m $*"                 | tee -a "$LOG" >&2; }
push() { if [ "$APLICAR" = 1 ]; then scp -q "$1" "$MINI_SSH:$2"; else log "DRY scp: $1 → $2"; fi; }
mini() { if [ "$APLICAR" = 1 ]; then ssh "$MINI_SSH" "$@"; else log "DRY ssh: $*"; fi; }

cleanup() { rm -rf "$TMP" 2>/dev/null || true; }
trap cleanup EXIT

# ── Paso 0 · validaciones ──
validar() {
    log "=== Validando (local + mini) ==="
    [ -f "$MB_COMPLETO/oraculo_codigo.sh" ] || { err "falta oraculo_codigo.sh en $MB_COMPLETO"; exit 1; }
    [ -f "$MB_MOSAIC/dedup.py" ]            || warn "sin dedup.py local (opcional; el crawler ya trae el fallback léxico)"
    command -v scp >/dev/null || { err "falta scp"; exit 1; }
    command -v rsync >/dev/null || { err "falta rsync (lo usa el handoff)"; exit 1; }
    if [ -f "$HOME/.github_token" ]; then ok "token local presente"; else warn "sin ~/.github_token local — pon el token en el mini a mano"; fi
    if [ "$APLICAR" = 1 ]; then
        ssh -o ConnectTimeout=6 "$MINI_SSH" \
            'for c in git jq curl python3; do command -v $c >/dev/null || { echo "FALTA $c"; exit 3; }; done; echo MINI_OK' \
            || { err "el mini no cumple deps mínimas (git/jq/curl/python3) o no hay ssh"; exit 1; }
        ok "mini con deps mínimas — dedup LÉXICO puro stdlib ⇒ NADA de torch/numpy/sentence-transformers"
    else
        warn "DRY-RUN: la sonda de deps del mini se ejecuta con --aplicar"
    fi
}

# ── Pasos 1-6 · desplegar ──
ejecutar() {
    log "=== Paso 1 · migrar scripts (rutas absolutas) → $MINI_SSH:$MINI_BIN ==="
    mini "mkdir -p '$MINI_BIN' '$MINI_ORACULO/hallazgos' '$MINI_ORACULO/lotes' '$MINI_ORACULO/estado'"
    push "$MB_COMPLETO/oraculo_codigo.sh" "$MINI_BIN/"
    [ -f "$MB_MOSAIC/dedup.py" ] && push "$MB_MOSAIC/dedup.py" "$MINI_BIN/"
    [ -f "$MB_MOSAIC/tema_modelo.sh" ] && push "$MB_MOSAIC/tema_modelo.sh" "$MINI_BIN/"

    log "=== Paso 4 · token en el mini ==="
    if [ -f "$HOME/.github_token" ]; then push "$HOME/.github_token" "$MINI_HOME/.github_token"; mini "chmod 600 '$MINI_HOME/.github_token'"; else warn "salto token (ponlo a mano en $MINI_HOME/.github_token)"; fi

    log "=== Paso 2+3 · env: juez=pequeño del mini · dedup léxico · nota indulgente ==="
    cat > "$TMP/recolector.env" <<EOF
# generado por desplegar_recolector_mini.sh ($(date +%F))
export CLUSTER_ENDPOINTS_OVERRIDE="$MINI_JUEZ"   # el juez de repos es el pequeño del mini · EL 24B JAMÁS
export EMB_MODEL=""                               # vacío ⇒ dedup LÉXICO por hashing (sin torch)
export ORACULO_BIN="$MINI_BIN/oraculo_codigo.sh"
# Modelos que PROPONEN el tema (rotación · el mini alcanza el roster del MacBook). Vacío ⇒ solo lista estática.
export MODELOS_TEMA="Qwen3-14B@http://127.0.0.1:8092 Coder-14B@http://127.0.0.1:8093 DeepSeek-R1@http://127.0.0.1:8094 Unholy@http://127.0.0.1:8091"
EOF
    push "$TMP/recolector.env" "$MINI_BIN/recolector.env"

    log "=== Paso 6 · supervisión: bucle periódico en el mini (rota temas, escribe la despensa) ==="
    cat > "$TMP/recolector_loop.sh" <<EOF
#!/bin/bash
# bucle del recolector en el MINI · desacoplado del reloj del MacBook · escribe ~/oraculo
set -uo pipefail
source '$MINI_BIN/recolector.env' 2>/dev/null || true
export GITHUB_TOKEN="\$(cat '$MINI_HOME/.github_token' 2>/dev/null || true)"
IFS=';' read -ra TEMAS <<< "$TEMAS"                    # lista estática de reserva
read -ra MODS <<< "\${MODELOS_TEMA:-}"                 # modelos que PROPONEN el tema (rotación)
i=0
while true; do
    q=""
    if [ "\${#MODS[@]}" -gt 0 ]; then                  # el modelo de turno propone el tema
        modelo="\${MODS[\$(( i % \${#MODS[@]} ))]}"
        q="\$(bash '$MINI_BIN/tema_modelo.sh' "\$modelo" 2>/dev/null)"
        [ -n "\$q" ] && echo "[\$(date '+%F %T')] tema (por \$modelo): \$q" >> '$MINI_ORACULO/recolector.log'
    fi
    if [ -z "\$q" ]; then                              # fallback: lista estática (nunca se rompe)
        q="\${TEMAS[\$(( i % \${#TEMAS[@]} ))]}"
        echo "[\$(date '+%F %T')] tema (fallback estático): \$q" >> '$MINI_ORACULO/recolector.log'
    fi
    i=\$(( i + 1 ))
    CLUSTER_ENDPOINTS_OVERRIDE="\$CLUSTER_ENDPOINTS_OVERRIDE" EMB_MODEL="" \\
        bash '$MINI_BIN/oraculo_codigo.sh' --query="\$q" --nota-min=$NOTA_MIN \\
        >> '$MINI_ORACULO/recolector.log' 2>&1 || echo "[\$(date '+%F %T')] pasada con incidencias" >> '$MINI_ORACULO/recolector.log'
    sleep $COOLDOWN
done
EOF
    push "$TMP/recolector_loop.sh" "$MINI_BIN/recolector_loop.sh"
    mini "chmod +x '$MINI_BIN/recolector_loop.sh'; pkill -f recolector_loop.sh 2>/dev/null || true; nohup '$MINI_BIN/recolector_loop.sh' >/dev/null 2>&1 & echo 'bucle lanzado en el mini'"

    log "=== Paso 5 · handoff local (fire-and-forget · SIN barrera bloqueante) ==="
    cat > "$MB_MOSAIC/recoger_del_mini.sh" <<EOF
#!/bin/bash
# 🚚 Recoge la despensa del mini → ~/oraculo local (hallazgos+lotes). NO bloquea:
#    si el mini no responde en 60s, sigue. Llamar en 2º plano al INICIO de FASE 1:
#        "\$HOME/Mosaic_privado/recoger_del_mini.sh" &
set -uo pipefail
MINI_SSH="\${MINI_SSH:-$MINI_SSH}"
mkdir -p "\$HOME/oraculo/hallazgos" "\$HOME/oraculo/lotes"
for sub in hallazgos lotes; do
    timeout 60 rsync -az -e ssh "\$MINI_SSH:$MINI_ORACULO/\$sub/" "\$HOME/oraculo/\$sub/" 2>/dev/null \\
        && echo "🚚 recogido \$sub del mini" || echo "🚚 mini no disponible (\$sub) — sigo sin esperar"
done
EOF
    chmod +x "$MB_MOSAIC/recoger_del_mini.sh"
    ok "handoff: $MB_MOSAIC/recoger_del_mini.sh (cuélgalo en 2º plano al inicio de FASE 1; cuarentena.sh clona)"
}

validar
ejecutar
if [ "$APLICAR" = 1 ]; then
    ok "Despliegue APLICADO. El mini ya recolecta. Engancha recoger_del_mini.sh a FASE 1."
else
    warn "DRY-RUN (no se tocó el mini). Revisa el plan de arriba y relanza con:  $0 --aplicar"
fi
