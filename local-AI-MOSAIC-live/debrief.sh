#!/bin/bash
# 🧭 =====================================================================
# 🧭 DEBRIEF — el mapa del ciclo en ~20 líneas (diseño de la MESA, 4-jul-2026).
# 🧭   · ESPEJO del acta (regla de MOSAIC: se LEE data/actas/acta_*.json, jamás se recalcula)
# 🧭   · cada fila con su ANCLA grep-able (regla de Opus/Fable: función, no línea)
# 🧭   · semáforo de colores (petición de Gustavo: verde=bien · ámbar=ojo · rojo=roto)
# 🧭   · delta vs acta anterior (Opus/el Nuevo) · flags vivos (Fable) · bucle acta→gobernador
# 🧭     y procedencia del banco (MOSAIC) · guarda copia PLANA en data/debrief_ultimo.md
# 🧭 Uso:  dentro del ciclo lo llama ciclo.sh (DEBRIEF=0 lo apaga) ·
# 🧭       en frío: ./debrief.sh  (reimprime el panel del ÚLTIMO acta, sin marcas de fase)
# 🧭 =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
ACTAS="$BASE/data/actas"
PERFIL="$BASE/data/perfil_lanzamiento.json"
FAB_SALTOS="$BASE/data/fabrica_saltos.txt"
MD="$BASE/data/debrief_ultimo.md"
FASES_LOG="${DEBRIEF_FASES:-}"           # lo pasa ciclo.sh; vacío = modo frío
INC_LOG="${DEBRIEF_INC:-}"

# shellcheck disable=SC1091
source "$BASE/colores.sh" 2>/dev/null || true
V="${C_VERDE:-}"; R="${C_ROJO:-}"; A="${C_AMARILLO:-}"; G="${C_GRIS:-}"; B="${C_BOLD:-}"; X="${C_RESET:-}"

validar() {
    command -v python3 >/dev/null 2>&1 || { echo "debrief: falta python3" >&2; exit 1; }
    ls "$ACTAS"/acta_*.json >/dev/null 2>&1 || { echo "debrief: sin actas en $ACTAS (corre un ciclo primero)" >&2; exit 1; }
}

# imprime coloreado en terminal Y acumula la versión PLANA para el .md
MDBUF=""
fila() { printf '%b\n' "$1"; MDBUF="$MDBUF$2"$'\n'; }

# estado de una fase según el rastro: ✓ alcanzada · ✗ con incidencia · ⊘ no alcanzada · · sin rastro (frío)
estado_fase() {
    local f="$1" inc=""
    [ -n "$INC_LOG" ] && [ -f "$INC_LOG" ] && inc="$(grep -c "^F$f " "$INC_LOG" 2>/dev/null || true)"
    if [ "${inc:-0}" -gt 0 ] 2>/dev/null; then printf 'X'; return; fi
    if [ -z "$FASES_LOG" ] || [ ! -f "$FASES_LOG" ]; then printf '.'; return; fi
    grep -qx "$f" "$FASES_LOG" 2>/dev/null && printf 'V' || printf 'O'
}
marca() {  # estado → símbolo coloreado + plano
    case "$1" in
        V) printf '%s' "${V}✓${X}|✓" ;;
        X) printf '%s' "${R}✗${X}|✗" ;;
        O) printf '%s' "${A}⊘${X}|⊘" ;;
        *) printf '%s' "${G}·${X}|·" ;;
    esac
}

ejecutar() {
    # ── todo lo del ACTA (fuente única) + delta, en una sola pasada de python ──
    # ⚠️ bash 3.2 (el /bin/bash de macOS): un heredoc DENTRO de $( ) se parsea MAL — el primer
    # panel real de Gustavo salió con ACTA_BASE=')' (mi sandbox corre bash 5 y no lo vio).
    # Patrón SEGURO en 3.2: heredoc → fichero temporal → source. Lección nueva del 3.2:
    # ni declare -A, ni heredoc dentro de $().
    local envtmp; envtmp="$(mktemp "${TMPDIR:-/tmp}/debrief_env.XXXXXX")"
    python3 - "$ACTAS" > "$envtmp" <<'PY'
import json, glob, os, sys
actas = sorted(glob.glob(os.path.join(sys.argv[1], "acta_*.json")), key=os.path.getmtime)
a = json.load(open(actas[-1])); p = json.load(open(actas[-2])) if len(actas) > 1 else {}
t, ab = a.get("tanda_resumen", {}), a.get("ab", {})
hu, ba = a.get("huecos", {}), a.get("banco", {})
pt, pba = p.get("tanda_resumen", {}), p.get("banco", {})
def num(x, d=0):
    return x if isinstance(x, (int, float)) else d
crag, pcrag = num(t.get("crag_medio")), num(pt.get("crag_medio"), None) if pt else None
d = (crag - pcrag) if isinstance(pcrag, (int, float)) else None
fl = "=" if d is None else ("↑" if d > 0.005 else "↓" if d < -0.005 else "=")
print(f'ACTA_BASE="{os.path.basename(actas[-1]).replace(".json","")}"')
print(f'CRAG={crag:.3f}'); print(f'DELTA="{fl}{abs(d):.3f}"' if d is not None else 'DELTA="—"')
print(f'RES={num(t.get("resueltos"))}'); print(f'EJEC={num(t.get("ejecuciones"))}')
print(f'AB="{num(ab.get("gana_a"))}-{num(ab.get("gana_b"))}-{num(ab.get("empates"))}"')
print(f'HN={num(hu.get("huecos_nuevos"))}'); print(f'HT={num(hu.get("huecos_total"))}')
print(f'BANCO={num(ba.get("pendientes"))}')
fp = ba.get("fuentes_pendientes") or {}
proc = " · ".join(f"{k} {v}" for k, v in sorted(fp.items(), key=lambda x: -x[1])) or "(vacío)"
print(f'PROC="{proc}"')
PY
    # shellcheck disable=SC1090
    . "$envtmp"; rm -f "$envtmp"
    # guard (nota de la lupa de Opus): acta ilegible → salir limpio; JAMÁS pintar un panel a medias
    [ -n "${ACTA_BASE:-}" ] || { echo "debrief: acta ilegible (sin ACTA_BASE) — no pinto un panel que mienta" >&2; return 1; }
    # ── bucle acta→gobernador · SELLO robusto (el gobernador FIRMA qué acta digirió) + mtime de reserva ──
    local m_acta m_perf sello BUCLE="${A}⊘ sin verificar${X}" BUCLE_P="⊘ sin verificar" BUCLE_OK=0
    sello="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("ultima_acta",""))' "$PERFIL" 2>/dev/null || true)"
    if [ -n "$sello" ]; then                       # acuse de recibo: ¿el gobernador firmó ESTA acta?
        if [ "$sello" = "$ACTA_BASE" ]; then
            BUCLE="${V}acta→gobernador ✓ (sello)${X}"; BUCLE_P="acta→gobernador ✓ (sello)"; BUCLE_OK=1
        else
            BUCLE="${R}gobernador digirió OTRA acta ($sello)${X}"; BUCLE_P="gobernador digirió otra acta ($sello) ✗"
        fi
    else                                           # reserva por FECHA (perfil ≥ acta) si el perfil no lleva sello
        m_acta="$( { stat -c %Y "$ACTAS/$ACTA_BASE.json" 2>/dev/null || stat -f %m "$ACTAS/$ACTA_BASE.json" 2>/dev/null || echo 0; } | head -1)"
        m_perf="$( { stat -c %Y "$PERFIL" 2>/dev/null || stat -f %m "$PERFIL" 2>/dev/null || echo 0; } | head -1)"
        if [ "${m_perf:-0}" -ge "${m_acta:-1}" ] 2>/dev/null && [ "${m_perf:-0}" -gt 0 ]; then
            BUCLE="${V}acta→gobernador ✓ (mtime)${X}"; BUCLE_P="acta→gobernador ✓ (mtime)"; BUCLE_OK=1
        else
            BUCLE="${R}acta ESCRITA pero gobernador NO la digirió${X}"; BUCLE_P="acta escrita pero gobernador NO la digirió ✗"
        fi
    fi
    # ── flags vivos (Fable: un ciclo sin sus flags no es reproducible) ──
    local FLAGS="WORKERS=${MOSAIC_WORKERS:-1} JUECES=${MOSAIC_JUECES:-2} ESCALADA=${MOSAIC_ESCALADA:-1} FNC=${MOSAIC_FNC:-0} CASCADA_BG=${CASCADA_BG:-1} GOB=${MOSAIC_GOBERNADOR:-1} JUEZ_DEM=${MOSAIC_JUEZ_DEMANDA:-1} BAJAR=${MOSAIC_BAJAR_AL_ACABAR:-1}"
    local SALTOS; SALTOS="$(cat "$FAB_SALTOS" 2>/dev/null || echo 0)"

    # ── el panel ──
    local m0 m1 m2 m3 m4 m5 m7 m6 c p
    # estados CRUDOS primero (los consume también el JSON de la consola — Ronda 1), marcas después
    local e0 e1 e2 e3 e4 e5 e7 e6
    e0="$(estado_fase 0)"; e1="$(estado_fase 1)"; e2="$(estado_fase 2)"; e3="$(estado_fase 3)"
    e4="$(estado_fase 4)"; e5="$(estado_fase 5)"; e7="$(estado_fase 7)"; e6="$(estado_fase 6)"
    m0="$(marca "$e0")"; m1="$(marca "$e1")"; m2="$(marca "$e2")"
    m3="$(marca "$e3")"; m4="$(marca "$e4")"; m5="$(marca "$e5")"
    m7="$(marca "$e7")"; m6="$(marca "$e6")"
    local modo="en ciclo"; [ -z "$FASES_LOG" ] && modo="en frío: último acta"
    MDBUF="# DEBRIEF — $ACTA_BASE ($modo)"$'\n\n```\n'
    fila "${B}═══ DEBRIEF · $ACTA_BASE · $(date '+%Y-%m-%d %H:%M') ($modo) ═══${X}" \
         "═══ DEBRIEF · $ACTA_BASE · $(date '+%Y-%m-%d %H:%M') ($modo) ═══"
    c="${m0%|*}"; p="${m0#*|}"; fila "$c F0 infra      cluster+mini             'FASE 0 · ASEGURAR' · asegurar_cluster/asegurar_mini" "$p F0 infra      cluster+mini             'FASE 0 · ASEGURAR' · asegurar_*"
    c="${m1%|*}"; p="${m1#*|}"; fila "$c F1 fuentes    cascada→banco            'FASE 1 · FUENTES' · fuentes.sh::pull" "$p F1 fuentes    cascada→banco            'FASE 1 · FUENTES' · fuentes.sh::pull"
    c="${m2%|*}"; p="${m2#*|}"; fila "$c F2 ingesta    $RES/$EJEC resueltos          'FASE 2 · INGESTA' · mosaic.py::aprender" "$p F2 ingesta    $RES/$EJEC resueltos          'FASE 2 · INGESTA' · mosaic.py::aprender"
    c="${m3%|*}"; p="${m3#*|}"; fila "$c F3 juicio     tribunal                 'FASE 3 · JUICIO' · trampa.py/tribunal.py" "$p F3 juicio     tribunal                 'FASE 3 · JUICIO' · trampa.py/tribunal.py"
    c="${m4%|*}"; p="${m4#*|}"; fila "$c F4 aprende    generar+consolidar       'FASE 4 · APRENDER' · mosaic.py::generar_capacidades" "$p F4 aprende    generar+consolidar       'FASE 4 · APRENDER' · mosaic.py::generar_capacidades"
    c="${m5%|*}"; p="${m5#*|}"; fila "$c F5 panel      META madurez             'FASE 5 · PANEL' · panel.sh" "$p F5 panel      META madurez             'FASE 5 · PANEL' · panel.sh"
    c="${m6%|*}"; p="${m6#*|}"; fila "$c F6 acta       $ACTA_BASE  'FASE 6 · ACTA' · acta.py" "$p F6 acta       $ACTA_BASE  'FASE 6 · ACTA' · acta.py"
    c="${m7%|*}"; p="${m7#*|}"; fila "$c F7 gobern.    perfil próximo ciclo     'FASE 7 · GOBERNADOR' · gobernador.py" "$p F7 gobern.    perfil próximo ciclo     'FASE 7 · GOBERNADOR' · gobernador.py"
    fila "  bucle       $BUCLE       (acuse de recibo · mtime de reserva)" "  bucle       $BUCLE_P       (acuse de recibo · mtime de reserva)"
    fila "${B}── métricas (del acta, espejo) ──${X} CRAG $CRAG ($DELTA) · resueltos $RES/$EJEC · A/B $AB · huecos +$HN ($HT hist)" \
         "── métricas (del acta, espejo) ── CRAG $CRAG ($DELTA) · resueltos $RES/$EJEC · A/B $AB · huecos +$HN ($HT hist)"
    fila "── banco $BANCO ← $PROC · fábrica saltada ${SALTOS}× seguidas (F13)" \
         "── banco $BANCO ← $PROC · fábrica saltada ${SALTOS}× seguidas (F13)"
    fila "── flags ── $FLAGS" "── flags ── $FLAGS"
    fila "${B}── subsistemas ──${X}" "── subsistemas ──"
    fila "  🛡️ defensa   4 lentes+juez Phi-4 · candado 'D0.2' fail-closed · defensa.py::analizar" "  defensa   4 lentes+juez Phi-4 · candado 'D0.2' fail-closed · defensa.py::analizar"
    fila "  🐟 pool      bocas first-to-finish (WORKERS>1) · mosaic.py::_bocas_pool" "  pool      bocas first-to-finish (WORKERS>1) · mosaic.py::_bocas_pool"
    fila "  🧠 mini      recolector F6 · recoger_del_mini.sh (handoff)" "  mini      recolector F6 · recoger_del_mini.sh (handoff)"
    # ── incidencias del ciclo (rojas, con su ancla) ──
    if [ -n "$INC_LOG" ] && [ -s "$INC_LOG" ]; then
        while IFS= read -r ln; do
            fila "  ${R}⚠ $ln${X}" "  ⚠ $ln"
        done < "$INC_LOG"
    else
        fila "  ${V}sin incidencias registradas${X}" "  sin incidencias registradas"
    fi
    fila "${B}═══════════════════════════════════════════════════════${X}" "═══════════════════════════════════════════════════════"

    # copia PLANA para pegar en CARTAS sin copiar del terminal (idea del Nuevo)
    MDBUF="$MDBUF"$'```\n'
    printf '%s' "$MDBUF" > "$MD" 2>/dev/null || true

    # ── 🖥️ RONDA 1 (consola de la mesa): estado_sistema.json — MISMO cómputo, segunda salida.
    # Contrato v1 de Opus (carta 15:13) + garantías de constructor: escritura ATÓMICA (tmp+replace,
    # el visor jamás lee medio fichero) y heredoc por REDIRECCIÓN (la lección del 3.2).
    E0="$e0" E1="$e1" E2="$e2" E3="$e3" E4="$e4" E5="$e5" E7="$e7" E6="$e6" \
    ACTA_BASE="$ACTA_BASE" MODO="$modo" CRAG="$CRAG" DELTA="$DELTA" RES="$RES" EJEC="$EJEC" \
    AB="$AB" HN="$HN" HT="$HT" BANCO="$BANCO" TOPE="${MAX_COLA:-60}" PROC="$PROC" \
    SALTOS="$SALTOS" FLAGS="$FLAGS" BUCLE_OK="$BUCLE_OK" \
    FAILC="$(grep -c "D0.2" "$BASE/defensa.py" 2>/dev/null || echo 0)" \
    INCF="${INC_LOG:-}" CARTAS="$BASE/info/CARTAS.md" OUT="$BASE/data/estado_sistema.json" \
    python3 <<'PY' 2>/dev/null || true
import json, os, time, tempfile
env = os.environ
est = {"V": "ok", "X": "incidencia", "O": "no_alcanzada", ".": "sin_rastro"}
anc = {"F0": "ciclo.sh:'FASE 0 · ASEGURAR' · asegurar_*", "F1": "ciclo.sh:'FASE 1 · FUENTES' · fuentes.sh::pull",
       "F2": "ciclo.sh:'FASE 2 · INGESTA' · mosaic.py::aprender", "F3": "ciclo.sh:'FASE 3 · JUICIO' · trampa.py",
       "F4": "ciclo.sh:'FASE 4 · APRENDER' · mosaic.py::generar_capacidades", "F5": "ciclo.sh:'FASE 5 · PANEL' · panel.sh",
       "F6": "ciclo.sh:'FASE 6 · ACTA' · acta.py", "F7": "ciclo.sh:'FASE 7 · GOBERNADOR' · gobernador.py"}
nom = {"F0": "infra", "F1": "fuentes", "F2": "ingesta", "F3": "juicio", "F4": "aprender", "F5": "panel", "F6": "acta", "F7": "gobernador"}
orden = ["F0", "F1", "F2", "F3", "F4", "F5", "F6", "F7"]
crudos = {"F0": env["E0"], "F1": env["E1"], "F2": env["E2"], "F3": env["E3"],
          "F4": env["E4"], "F5": env["E5"], "F7": env["E7"], "F6": env["E6"]}
fases = [{"id": f, "nombre": nom[f], "estado": est.get(crudos[f], "sin_rastro"), "ancla": anc[f]} for f in orden]
inc = []
p = env.get("INCF", "")
if p and os.path.exists(p):
    for ln in open(p, encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if ln:
            inc.append({"fase": ln.split(" ", 1)[0], "texto": ln})
rep = []
try:
    with open(env["CARTAS"], "rb") as f:
        f.seek(max(0, os.path.getsize(env["CARTAS"]) - 60000))
        colas = f.read().decode("utf-8", errors="ignore").splitlines()
    rep = [{"cabecera": l.lstrip("# ").strip()} for l in colas if l.startswith("## ")][-5:]
except Exception:
    pass
flags = {}
for kv in env.get("FLAGS", "").split():
    if "=" in kv:
        k, v = kv.split("=", 1)
        flags[k] = int(v) if v.isdigit() else v
fuentes = {}
for tr in env.get("PROC", "").split("·"):
    t = tr.strip().rsplit(" ", 1)
    if len(t) == 2 and t[1].isdigit():
        fuentes[t[0].strip()] = int(t[1])
d = env.get("DELTA", "—")
delta = None
if d and d not in ("—", "="):
    try:
        delta = float(d.lstrip("↑↓=")) * (-1 if d.startswith("↓") else 1)
    except ValueError:
        delta = None
bucle = env.get("BUCLE_OK", "0") == "1"
failc = (env.get("FAILC", "0").strip() or "0") != "0"
criticas = {"F2", "F3"}
inc_fases = {i["fase"].rstrip(":") for i in inc}
if (inc_fases & criticas) or not failc or (env["MODO"].startswith("en ciclo") and not bucle):
    general = "rojo"
elif inc or int(env.get("BANCO", "0") or 0) < 10:
    general = "amarillo"
else:
    general = "verde"
salida = {
    "schema_version": 1,
    "generado": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "generado_ts": int(time.time()),
    "acta": env["ACTA_BASE"], "modo": env["MODO"],
    "estado_general": general,
    "salud": {"fases_ok": sum(1 for f in fases if f["estado"] == "ok"),
              "fases_incidencia": sum(1 for f in fases if f["estado"] == "incidencia"),
              "fases_no_alcanzadas": sum(1 for f in fases if f["estado"] == "no_alcanzada"),
              "bucle_acta_gobernador": bucle, "fail_closed": failc},
    "fases": fases,
    "metricas": {"crag": float(env["CRAG"]), "crag_delta": delta,
                 "resueltos": int(env["RES"]), "ejecuciones": int(env["EJEC"]),
                 "ab": dict(zip(("a", "b", "empates"), (int(x) for x in env["AB"].split("-")))),
                 "huecos_nuevos": int(env["HN"]), "huecos_total": int(env["HT"]),
                 "tendencia": ("sube" if (delta or 0) > 0 else "baja" if (delta or 0) < 0 else "plano")},
    "banco": {"pendientes": int(env["BANCO"]), "tope": int(env["TOPE"]),
              "fuentes": fuentes, "fabrica_saltos_seguidos": int(env.get("SALTOS", "0") or 0)},
    "subsistemas": [
        {"id": "defensa", "estado": "ok" if failc else "sin_candado",
         "detalle": "4 lentes + juez Phi-4 · candado D0.2 fail-closed", "ancla": "defensa.py::analizar · 'D0.2'"},
        {"id": "fnc", "estado": "off" if flags.get("FNC", 0) == 0 else "on",
         "detalle": "gated (acuerdo de mesa: A/B ≥2 victorias)", "ancla": "gobernador.py:'FNC' · fnc.py:MOSAIC_FNC"},
        {"id": "cascada_bg", "estado": "on" if flags.get("CASCADA_BG", 1) == 1 else "off",
         "detalle": "F7 cascada solapada", "ancla": "ciclo.sh:'F7 (Opus'"},
        {"id": "pool", "estado": "on" if flags.get("WORKERS", 1) > 1 else "off",
         "detalle": "bocas first-to-finish", "ancla": "mosaic.py::_bocas_pool"},
        {"id": "recolector_mini", "estado": "ok", "detalle": "F6 · handoff recoger_del_mini",
         "ancla": "desplegar_recolector_mini.sh · recolector_loop.sh"}],
    "flags": flags,
    "incidencias": inc,
    "ultimos_reportes": rep,
    "ficheros": {"debrief_md": "data/debrief_ultimo.md",
                 "acta_json": "data/actas/" + env["ACTA_BASE"] + ".json"},
}
tmp = tempfile.NamedTemporaryFile("w", dir=os.path.dirname(env["OUT"]), delete=False, encoding="utf-8")
json.dump(salida, tmp, ensure_ascii=False, indent=2)
tmp.close()
os.replace(tmp.name, env["OUT"])   # ATÓMICO: el visor jamás lee medio fichero
PY
}

validar
ejecutar
