#!/bin/bash
# 📥 =====================================================================
# 📥 COLA — buzón de preguntas en SQLite (productores encolan, 1 worker procesa).
# 📥   ./cola.sh add "pregunta" [fuente]   -> encola (tú, o la fábrica)
# 📥   ./cola.sh run [--once]              -> worker: saca y pasa a mosaic, 1 a 1
# 📥   ./cola.sh ver | size | hechas       -> estado de la cola
# 📥 Claim ATÓMICO (UPDATE..RETURNING + WAL): no se reparte dos veces aunque haya
# 📥 varios workers. Escala a cientos de miles sin el viejo problema de 'ls *.json'.
# 📥 Reanudable: lo que quedó 'procesando' tras un Ctrl+C vuelve a pendiente.
# 📥 =====================================================================
set -euo pipefail

HOME_USER="${HOME_USER:-$HOME}"
MOSAIC_DIR="$HOME_USER/Mosaic_privado"
MOSAIC_SH="${MOSAIC_SH:-$MOSAIC_DIR/mosaic.sh}"
DB="${COLA_DB:-$MOSAIC_DIR/data/cola.db}"          # backend SQLite
COLA_VIEJA="${COLA_VIEJA:-$MOSAIC_DIR/data/cola}"  # maildir antiguo -> se importa una vez
FLAG="$MOSAIC_DIR/data/pausa.flag"
CLUSTER_URL="${MOSAIC_LLM_BASE_URL:-http://127.0.0.1:8090/v1}"
ESPERA_VACIA="${ESPERA_VACIA:-10}"                 # s de espera con la cola vacía (modo run)
PYBIN="${PYBIN:-$HOME_USER/wikirag/venv/bin/python3}"; [ -x "$PYBIN" ] || PYBIN="$(command -v python3)"
DISCRIMINAR_PY="${DISCRIMINAR_PY:-$MOSAIC_DIR/discriminar.py}"   # paso 3: lote diverso
LOTE_DISPATCH="${LOTE_DISPATCH:-23}"               # tamaño del lote discriminado a FASE 2 (primo)

# shellcheck disable=SC1091
source "$MOSAIC_DIR/colores.sh" 2>/dev/null || true
log() { printf '%s[%s] [COLA]%s  %s\n' "${FASE_COLOR:-${C_AZUL:-}}" "$(date '+%H:%M:%S')" "${C_RESET:-}" "$*"; }
err() { printf '[%s] [COLA-ERR] %s\n' "$(date '+%H:%M:%S')" "$*" >&2; }
mkdir -p "$MOSAIC_DIR/data"

cluster_vivo() { curl -s -m 3 "$CLUSTER_URL/models" >/dev/null 2>&1; }
esperar_si_pausa() { while [ -f "$FLAG" ]; do log "⏸️ vigía: pausa activa, espero 30s..."; sleep 30; done; }

# --- BD: crea esquema (idempotente) e importa el maildir antiguo una sola vez ---
db_init() {
    python3 - "$DB" "$COLA_VIEJA" <<'PY'
import sqlite3, sys, os, glob, json
db, vieja = sys.argv[1], sys.argv[2]
con = sqlite3.connect(db); con.execute("PRAGMA journal_mode=WAL")
con.execute("""CREATE TABLE IF NOT EXISTS cola(
  id INTEGER PRIMARY KEY AUTOINCREMENT, estado INT DEFAULT 0,
  fuente TEXT, pregunta TEXT, ts TEXT, ts_proc TEXT)""")          # estado: 0 pend · 1 proc · 2 hecha
con.execute("CREATE INDEX IF NOT EXISTS ix_estado ON cola(estado,id)")
con.commit()
# importar .json del maildir antiguo (no se pierde nada: se mueven a trash/otros)
n = 0
td = os.path.join(os.path.dirname(vieja), "..", "trash", "otros"); os.makedirs(td, exist_ok=True)
for f in sorted(glob.glob(os.path.join(vieja, "*.json"))):
    try:
        d = json.load(open(f, encoding="utf-8"))
        con.execute("INSERT INTO cola(estado,fuente,pregunta,ts) VALUES(0,?,?,?)",
                    (d.get("fuente", "cola"), d.get("pregunta", ""), d.get("ts", "")))
        os.replace(f, os.path.join(td, os.path.basename(f))); n += 1
    except Exception:
        pass
con.commit(); con.close()
if n:
    print(n)
PY
}

_cuenta() { python3 -c 'import sqlite3,sys;print(sqlite3.connect(sys.argv[1]).execute("SELECT COUNT(*) FROM cola WHERE estado=?",(int(sys.argv[2]),)).fetchone()[0])' "$DB" "$1"; }
size()   { db_init >/dev/null; _cuenta 0; }
hechas() { db_init >/dev/null; _cuenta 2; }
fuentes_stats() {   # por fuente: pendientes y hechas (observabilidad #70)
    db_init >/dev/null
    python3 - "$DB" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
for f, p, h in c.execute("SELECT COALESCE(fuente,'?'), SUM(estado=0), SUM(estado=2) "
                         "FROM cola GROUP BY fuente ORDER BY 3 DESC, 2 DESC").fetchall():
    print(f"{f}\t{p or 0}\t{h or 0}")
PY
}

add() {
    local pregunta="${1:-}" fuente="${2:-manual}"
    [ -n "${pregunta// /}" ] || { err "pregunta vacía, no encolo."; return 1; }
    db_init >/dev/null
    python3 - "$DB" "$pregunta" "$fuente" <<'PY'
import sqlite3, sys, time
def limpia(s):                                   # bytes no-UTF8 → texto válido (recupera acentos latin-1)
    b = s.encode("utf-8", "surrogateescape")
    try: return b.decode("utf-8")
    except UnicodeDecodeError: return b.decode("latin-1", "replace")
con = sqlite3.connect(sys.argv[1]); con.execute("PRAGMA busy_timeout=10000")
con.execute("INSERT INTO cola(estado,fuente,pregunta,ts) VALUES(0,?,?,?)",
            (limpia(sys.argv[3]), limpia(sys.argv[2]), time.strftime("%Y-%m-%d %H:%M:%S")))
con.commit()
PY
    log "📥 guardada [$fuente]: ${pregunta:0:60}"
}

ver() {
    db_init >/dev/null
    log "pendientes: $(_cuenta 0)   ·   hechas: $(_cuenta 2)"
    python3 - "$DB" <<'PY'
import sqlite3, sys
for f, p in sqlite3.connect(sys.argv[1]).execute(
        "SELECT fuente,pregunta FROM cola WHERE estado=0 ORDER BY id LIMIT 5"):
    print("   -", f, "::", (p or "")[:70])
PY
}

run() {
    local once=0; [ "${1:-}" = "--once" ] && once=1
    db_init >/dev/null
    log "worker en marcha (db=$DB). Ctrl+C para parar."
    trap 'echo; log "worker detenido."; exit 0' INT TERM
    # recuperación: lo que quedó 'procesando' (estado=1) vuelve a pendiente
    local rec; rec="$(python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);n=c.execute("UPDATE cola SET estado=0 WHERE estado=1").rowcount;c.commit();print(n)' "$DB")"
    [ "${rec:-0}" -gt 0 ] && log "recuperados $rec a medio procesar."
    while true; do
        # claim ATÓMICO: marca el más antiguo como 'procesando' y devuelve su id
        local id; id="$(python3 - "$DB" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1]); con.execute("PRAGMA busy_timeout=10000")
row = con.execute("UPDATE cola SET estado=1, ts_proc=datetime('now') "
                  "WHERE id=(SELECT id FROM cola WHERE estado=0 ORDER BY id LIMIT 1) "
                  "RETURNING id").fetchone()
con.commit()
if row:
    print(row[0])
PY
)"
        if [ -z "$id" ]; then
            [ "$once" = "1" ] && { log "cola vacía; salgo (--once)."; break; }
            sleep "$ESPERA_VACIA"; continue
        fi
        # leer el item reclamado (intacto, ya es nuestro)
        local fuente pregunta
        fuente="$(python3 -c 'import sqlite3,sys;r=sqlite3.connect(sys.argv[1]).execute("SELECT fuente FROM cola WHERE id=?",(int(sys.argv[2]),)).fetchone();print(r[0] if r and r[0] else "cola")' "$DB" "$id")"
        pregunta="$(python3 -c 'import sqlite3,sys;r=sqlite3.connect(sys.argv[1]).execute("SELECT pregunta FROM cola WHERE id=?",(int(sys.argv[2]),)).fetchone();print(r[0] if r and r[0] else "")' "$DB" "$id")"
        esperar_si_pausa
        if ! cluster_vivo; then
            err "cluster caído; libero el item y espero."
            python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);c.execute("UPDATE cola SET estado=0 WHERE id=?",(int(sys.argv[2]),));c.commit()' "$DB" "$id"
            sleep "$ESPERA_VACIA"; continue
        fi
        log "procesando [$fuente]: ${pregunta:0:60}"
        MOSAIC_FUENTE="$fuente" "$MOSAIC_SH" "$pregunta" || err "mosaic falló con este item."
        python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);c.execute("UPDATE cola SET estado=2 WHERE id=?",(int(sys.argv[2]),));c.commit()' "$DB" "$id"
    done
}

# PIPELINE (#72): vuelca pendientes (y re-reclama lo dejado a medias) a stdout, marcándolos 'procesando'
volcar() {
    db_init >/dev/null
    python3 - "$DB" "${1:-100000}" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1]); con.execute("PRAGMA busy_timeout=10000")
rows = con.execute("SELECT id,pregunta FROM cola WHERE estado IN (0,1) ORDER BY id LIMIT ?",
                   (int(sys.argv[2]),)).fetchall()
ids = [r[0] for r in rows]
if ids:
    con.execute("UPDATE cola SET estado=1, ts_proc=datetime('now') WHERE id IN (%s)" % ",".join("?" * len(ids)), ids)
    con.commit()
for _id, preg in rows:
    print((preg or "").replace("\n", " ").replace("\r", " "))
PY
}
# tras el pipeline OK: marca como HECHAS las que estaban 'procesando'
confirmar() {
    db_init >/dev/null
    python3 -c 'import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);n=c.execute("UPDATE cola SET estado=2 WHERE estado=1").rowcount;c.commit();print(n)' "$DB"
}

# lote DISCRIMINADO (paso 3): en vez de volcar TODO, envía un lote diverso (híbrido:
# cupos por fuente + diversidad por embedding + envejecimiento). Degrada a volcar si falla.
discriminar() {
    db_init >/dev/null
    local L="${1:-$LOTE_DISPATCH}"
    "$PYBIN" "$DISCRIMINAR_PY" "$DB" "$L" || { err "discriminar falló → volcado normal (límite $L)"; volcar "$L"; }
}

case "${1:-ver}" in
    add)    shift; add "$@" ;;
    run)    shift; run "${1:-}" ;;
    ver)    ver ;;
    size)   size ;;
    hechas) hechas ;;
    fuentes) fuentes_stats ;;
    volcar) shift; volcar "${1:-}" ;;
    discriminar) shift; discriminar "${1:-}" ;;
    confirmar) confirmar ;;
    *)      err "uso: cola.sh add \"pregunta\" [fuente] | run [--once] | ver | size | hechas | fuentes | volcar | discriminar [N] | confirmar"; exit 1 ;;
esac
