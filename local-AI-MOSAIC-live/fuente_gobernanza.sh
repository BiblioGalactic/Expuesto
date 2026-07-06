#!/bin/bash
# 🏛️ =====================================================================
# 🏛️ FUENTE_GOBERNANZA — CARTAS como una ingesta más, EN OBSERVACIÓN (P3 orquesta).
# 🏛️   La idea de Gustavo: que MOSAIC aprenda de su propia historia de gobernanza
# 🏛️   SIN lógica nueva — las cartas entran al silo como cualquier texto y el bucle
# 🏛️   hueco→capacidad hace el resto. Las DOS trampas de Opus (22:21), cableadas:
# 🏛️   (a) anti-eco: las cartas de MOSAIC* NO se ingieren (sus propias salidas);
# 🏛️       el juez NUNCA se compone de capacidades (llamada directa) y el A/B queda
# 🏛️       como verdad-terreno — la deriva se VERÍA antes de hacer daño.
# 🏛️   (b) propuesta ≠ hecho: cada texto lleva la etiqueta EN CABECERA, y el nombre
# 🏛️       del fichero canta la procedencia (gobernanza_*) → trazable en informes.
# 🏛️   KILL-SWITCH NATO: MOSAIC_INGESTA_CARTAS=1 obligatorio (default 0 = ni dry).
# 🏛️   Cursor anti-re-ingesta: data/.gobernanza.cursor (hash de la última carta vista).
# 🏛️ Uso:  MOSAIC_INGESTA_CARTAS=1 ./fuente_gobernanza.sh            (DRY: qué entraría)
# 🏛️       MOSAIC_INGESTA_CARTAS=1 ./fuente_gobernanza.sh --aplicar  (al silo)
# 🏛️ =====================================================================
set -euo pipefail

BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
CARTAS="${CARTAS_MD:-$BASE/info/CARTAS.md}"
SILO="${SILO_DIR:-$BASE/silo}"
CURSOR="$BASE/data/.gobernanza.cursor"
N="${GOBERNANZA_N:-8}"                     # cuántas cartas recientes mirar por pasada
APLICAR=0; [ "${1:-}" = "--aplicar" ] && APLICAR=1

log() { printf '[%s] 🏛️  %s\n' "$(date +%H:%M:%S)" "$*"; }
err() { printf '[%s] ⚠️  %s\n' "$(date +%H:%M:%S)" "$*" >&2; }

validar() {
    if [ "${MOSAIC_INGESTA_CARTAS:-0}" != "1" ]; then
        log "MOSAIC_INGESTA_CARTAS≠1 → la ingesta de gobernanza está APAGADA (kill-switch nato). No hago nada."
        exit 0
    fi
    [ -r "$CARTAS" ] || { err "no encuentro el epistolar: $CARTAS"; exit 1; }
    [ -d "$SILO" ] || { err "no encuentro el silo: $SILO"; exit 1; }
    command -v python3 >/dev/null || { err "falta python3"; exit 1; }
}

ejecutar() {
    CARTAS_F="$CARTAS" SILO_D="$SILO" CURSOR_F="$CURSOR" N_CARTAS="$N" APLICAR_F="$APLICAR" python3 - <<'PY'
import hashlib, os, re, datetime

cartas_f, silo, cursor_f = os.environ["CARTAS_F"], os.environ["SILO_D"], os.environ["CURSOR_F"]
n, aplicar = int(os.environ["N_CARTAS"]), os.environ["APLICAR_F"] == "1"

src = open(cartas_f, encoding="utf-8", errors="replace").read()
# trocear por cabeceras de carta (el formato de la mesa)
partes = re.split(r"(?m)^(## .+)$", src)
cartas = [(partes[i], partes[i + 1]) for i in range(1, len(partes) - 1, 2)]
cartas = cartas[-n:]

visto = set()
if os.path.exists(cursor_f):
    visto = set(open(cursor_f, encoding="utf-8").read().split())

def hash_de(cab, cuerpo):
    return hashlib.sha256((cab + cuerpo[:400]).encode("utf-8", "replace")).hexdigest()[:16]

def slug(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s)[:48].strip("_")
    return s or "carta"

nuevos, saltadas_mosaic, ya_vistas = [], 0, 0
for cab, cuerpo in cartas:
    # anti-eco (trampa a): las salidas del propio MOSAIC no se le dan de comer
    if re.match(r"##\s+[^·]*\bMOSAIC\b", cab) or "— MOSAIC" in cuerpo[:200] or "MOSAIC-" in cab.split("·")[0]:
        saltadas_mosaic += 1
        continue
    h = hash_de(cab, cuerpo)
    if h in visto:
        ya_vistas += 1
        continue
    nuevos.append((h, cab.strip(), cuerpo.strip()))

print(f"PLAN|cartas miradas {len(cartas)} · nuevas {len(nuevos)} · anti-eco (MOSAIC) {saltadas_mosaic} · ya vistas {ya_vistas}")
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
for i, (h, cab, cuerpo) in enumerate(nuevos):
    nombre = f"gobernanza_{ts}_{i:02d}_{slug(cab)}.txt"
    print(f"PLAN|→ {nombre}")
    if aplicar:
        texto = (
            "[PROCEDENCIA: gobernanza-interna — carta del epistolar de la mesa]\n"
            "[TIPO: PROPUESTA/DEBATE de gobernanza — NO es un hecho verificado; son opiniones\n"
            " y decisiones de un equipo sobre su propio sistema. Trátalo como testimonio, no como dato.]\n\n"
            f"{cab}\n\n{cuerpo}\n")
        with open(os.path.join(silo, nombre), "w", encoding="utf-8") as f:
            f.write(texto)

if aplicar and nuevos:
    visto |= {h for h, _, _ in nuevos}
    os.makedirs(os.path.dirname(cursor_f), exist_ok=True)
    with open(cursor_f, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(visto)))
    print(f"PLAN|✅ {len(nuevos)} carta(s) al silo con etiqueta de procedencia · cursor actualizado")
elif not aplicar:
    print("PLAN|DRY-RUN — nada escrito. Aplica con: MOSAIC_INGESTA_CARTAS=1 ./fuente_gobernanza.sh --aplicar")
PY
}

validar
log "ingesta de gobernanza EN OBSERVACIÓN · $([ "$APLICAR" = 1 ] && echo APLICAR || echo DRY-RUN) · últimas ${N} cartas"
ejecutar
