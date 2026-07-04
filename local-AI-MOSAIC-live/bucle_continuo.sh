#!/bin/bash
# 🔁 =====================================================================
# 🔁 BUCLE CONTINUO v2 — ciclos COMPLETOS encadenados hasta TERMINAR el trabajo.
# 🔁
# 🔁 ⚠️  ADVERTENCIA: esto puede correr HORAS o DÍAS (procesamiento continuo).
# 🔁 ⚠️  Pide CONFIRMACIÓN antes de arrancar (o pásale --si para saltarla).
# 🔁 ⚠️  Ctrl+C es seguro en cualquier momento (ciclo.sh suelta sus locks).
# 🔁
# 🔁 v2 (2-jul-2026, encargo de Gustavo): la v1 era de la época en que SOLO existía
# 🔁 la fábrica de preguntas (régimen humo). Ahora DELEGA TODO en ciclo.sh —
# 🔁 cascada anti-humo, banco, pipeline 2 máquinas, tribunal, FASE 7 acta y
# 🔁 FASE 6 gobernador — y se detiene SOLO cuando no queda trabajo real:
# 🔁   trabajo = cola pendiente (banco) + archivos en silo + cuarentena.
# 🔁 (La v1 queda en trash/backups/bucle_continuo.sh.*.bak)
# 🔁
# 🔁 Uso:  ./bucle_continuo.sh [CICLOS_MAX] [--si]
# 🔁         CICLOS_MAX  tope de ciclos (0 o vacío = sin tope, hasta agotar trabajo)
# 🔁         --si        salta la confirmación (para lanzamientos desatendidos)
# 🔁 =====================================================================
set -euo pipefail

HOME_USER="${HOME_USER:-$HOME}"
MOSAIC_DIR="${MOSAIC_DIR:-$HOME_USER/Mosaic_privado}"
CICLO="$MOSAIC_DIR/ciclo.sh"
LANZADOR="${LANZADOR:-$HOME_USER/cluster/lanzar_cluster.sh}"   # Tarea 2: el lanzador único de la flota
DB="${COLA_DB:-$MOSAIC_DIR/data/cola.db}"
SILO_DIR="${SILO_DIR:-$MOSAIC_DIR/silo}"
CUAR_DIR="${CUARENTENA_DIR:-$MOSAIC_DIR/cuarentena}"
PAUSA="${PAUSA:-10}"                    # s de respiro entre ciclos
FALLOS_MAX="${FALLOS_MAX:-2}"           # ciclos fallidos SEGUIDOS antes de abortar (cauteloso)

CICLOS_MAX=0
CONFIRMADO=0
for arg in "$@"; do
    case "$arg" in
        --si) CONFIRMADO=1 ;;
        *[!0-9]*) echo "uso: ./bucle_continuo.sh [CICLOS_MAX] [--si]" >&2; exit 2 ;;
        *) CICLOS_MAX="$arg" ;;
    esac
done

log() { printf '[%s] 🔁 %s\n' "$(date '+%H:%M:%S')" "$*"; }
cleanup() { log "bucle terminado (los locks los gestiona ciclo.sh)."; }
trap cleanup EXIT
trap 'echo; log "Parado por ti (Ctrl+C). ./panel.sh para el estado."; exit 0' INT TERM

validar() {
    [ -d "$MOSAIC_DIR" ] || { echo "⚠️  no existe MOSAIC_DIR: $MOSAIC_DIR" >&2; exit 1; }
    [ -x "$CICLO" ] || { echo "⚠️  no encuentro ciclo.sh ejecutable en $CICLO" >&2; exit 1; }
    command -v python3 >/dev/null 2>&1 || { echo "⚠️  falta python3" >&2; exit 1; }
}

contar_trabajo() {   # cola pendiente + silo + cuarentena (solo lectura, no bloquea)
    local pend=0 sil=0 cuar=0 f
    pend="$(python3 - "$DB" 2>/dev/null <<'PY'
import sqlite3, sys
try:
    db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
    print(db.execute("SELECT COUNT(*) FROM cola WHERE estado=0").fetchone()[0])
except Exception:
    print(0)
PY
)" || pend=0
    [[ "$pend" =~ ^[0-9]+$ ]] || pend=0
    shopt -s nullglob
    for f in "$SILO_DIR"/*;  do [ -f "$f" ] && sil=$((sil+1)); done
    for f in "$CUAR_DIR"/*; do [ -e "$f" ] && cuar=$((cuar+1)); done
    shopt -u nullglob
    echo "$pend $sil $cuar"
}

confirmar() {
    [ "$CONFIRMADO" = "1" ] && return 0
    echo "⚠️  =============================================================="
    echo "⚠️   BUCLE CONTINUO: esto encadena ciclos COMPLETOS de MOSAIC"
    echo "⚠️   y puede estar HORAS o DÍAS procesando sin parar."
    echo "⚠️   Se detendrá solo cuando no quede trabajo (o con Ctrl+C)."
    echo "⚠️   Tope de ciclos: $([ "$CICLOS_MAX" -gt 0 ] && echo "$CICLOS_MAX" || echo 'SIN TOPE')"
    echo "⚠️  =============================================================="
    if [ ! -t 0 ]; then
        echo "⚠️  sin terminal interactiva: lanza con --si para confirmar." >&2
        exit 1
    fi
    printf '¿Lanzar el bucle continuo? Escribe SI en mayúsculas: '
    local resp; read -r resp
    [ "$resp" = "SI" ] || { echo "cancelado (no escribiste SI)."; exit 0; }
}

ejecutar() {
    local i=0 fallos=0 pend sil cuar total
    while :; do
        read -r pend sil cuar <<< "$(contar_trabajo)"
        total=$(( pend + sil + cuar ))
        if [ "$total" -eq 0 ]; then
            log "🎉 no queda trabajo (cola 0 · silo 0 · cuarentena 0) → paro. Ciclos hechos: $i"
            break
        fi
        if [ "$CICLOS_MAX" -gt 0 ] && [ "$i" -ge "$CICLOS_MAX" ]; then
            log "tope de $CICLOS_MAX ciclos alcanzado (quedaba trabajo: cola=$pend silo=$sil cuar=$cuar) → paro."
            break
        fi
        i=$((i + 1))
        log "═══ ciclo $i$([ "$CICLOS_MAX" -gt 0 ] && echo "/$CICLOS_MAX" || true) · trabajo: cola=$pend silo=$sil cuarentena=$cuar ═══"
        # Tarea 2 (3-jul): flota comprobada ANTES de cada ciclo — levanta lo caído, revive lo muerto
        if [ -x "$LANZADOR" ]; then
            "$LANZADOR" subir || log "⚠️  flota con bajas (el ciclo sigue; FASE 0 hará lo suyo)"
        fi
        # P4: entre ciclos la flota NO baja (recargar 40G de modelos cada vuelta sería tirar tiempo);
        # la baja ESTE bucle al terminar todo el trabajo (final de ejecutar()).
        if MOSAIC_MANTENER_FLOTA=1 "$CICLO" 1; then
            fallos=0
        else
            fallos=$((fallos + 1))
            log "⚠️  ciclo con fallo ($fallos/$FALLOS_MAX seguidos)"
            if [ "$fallos" -ge "$FALLOS_MAX" ]; then
                log "⚠️  $FALLOS_MAX fallos seguidos → aborto cauteloso. Mira logs/ y ./panel.sh"
                exit 1
            fi
        fi
        log "respiro ${PAUSA}s antes del siguiente…"
        sleep "$PAUSA"
    done
    # 🔻 P4 (4-jul): trabajo TERMINADO (o tope) → la flota baja en orden (mini verificado →
    # MacBook). Con Ctrl+C o aborto por fallos NO se baja: interrumpir/depurar ≠ apagar.
    if [ "${MOSAIC_BAJAR_AL_ACABAR:-1}" = "1" ] && [ -x "$LANZADOR" ]; then
        log "🔻 fin del trabajo → flota abajo en orden (mini verificado → MacBook)"
        "$LANZADOR" bajar || log "⚠️  apagado con incidencias — revisa: $LANZADOR estado"
    fi
}

validar
confirmar
log "arranca el bucle (Ctrl+C para parar · tope=$([ "$CICLOS_MAX" -gt 0 ] && echo "$CICLOS_MAX" || echo 'sin tope'))"
ejecutar
