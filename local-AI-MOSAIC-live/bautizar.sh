#!/bin/bash
# 🎭 =====================================================================
# 🎭 BAUTIZAR — pone un NOMBRE HUMANO (nombre_humano) a cada agente, dentro de su
# 🎭   bloque `persona`. La firma técnica (MOSAIC-<rol>) NO cambia → la traza se
# 🎭   conserva; el nombre humano da calidez y memoria ("Mari José avisó" se recuerda
# 🎭   mejor que "MOSAIC-seguridad depositó Informe"). Sin sed -i: inserción por texto,
# 🎭   escritura atómica, backup previo (reglas de la casa).
# 🎭 Uso:  ./bautizar.sh                 (al azar, solo a quien NO tenga)
# 🎭       ./bautizar.sh <rol> "Nombre"  (uno concreto)
# 🎭       ./bautizar.sh --reroll        (rebautiza a TODOS al azar)
# 🎭 =====================================================================
set -euo pipefail
BASE="${MOSAIC_BASE:-$HOME/Mosaic_privado}"
TURNOS="$BASE/roles/turnos"
err() { printf '⚠️  %s\n' "$*" >&2; }

[ -d "$TURNOS" ] || { err "no hay $TURNOS"; exit 1; }
python3 -c 'import yaml' 2>/dev/null || { err "falta pyyaml"; exit 1; }

# backup (regla de la casa)
mkdir -p "$BASE/trash/backups"
cp -r "$TURNOS" "$BASE/trash/backups/turnos.pre-bautizo.$(date +%Y%m%d_%H%M%S)"

MODO="${1:-azar}"; ROL="${1:-}"; NOMBRE="${2:-}"
TURNOS_D="$TURNOS" MODO="$MODO" ROL="$ROL" NOMBRE="$NOMBRE" python3 - <<'PY'
import os, glob, random, re

turnos = os.environ["TURNOS_D"]; modo = os.environ["MODO"]
pool = ["Mari José", "Paco", "Elena", "Ramón", "Bruno", "Chema", "Rosa", "Manolo",
        "Lola", "Ígor", "Nuria", "Álvaro", "Carmen", "Txema", "Vicente", "Pilar",
        "Nacho", "Sole", "Quique", "Diógenes", "Amparo", "Chus"]

def leer(p): return open(p, encoding="utf-8").read().splitlines(keepends=True)
def escribir(p, lines):
    tmp = p + ".tmp"; open(tmp, "w", encoding="utf-8").writelines(lines); os.replace(tmp, p)

def quitar_nombre(lines):
    return [l for l in lines if not re.match(r"\s*nombre_humano:", l)]

def poner_nombre(p, nombre):
    lines = quitar_nombre(leer(p))
    out = []
    for l in lines:
        out.append(l)
        if re.match(r"^persona:\s*$", l):
            out.append(f'  nombre_humano: "{nombre}"\n')   # justo dentro del bloque persona
    escribir(p, out)

def tiene_nombre(p):
    return any(re.match(r"\s*nombre_humano:", l) for l in leer(p))
def tiene_persona(p):
    return any(re.match(r"^persona:\s*$", l) for l in leer(p))

yamls = sorted(glob.glob(os.path.join(turnos, "*.yaml")))

# modo: uno concreto — CON nombre lo pone; SIN nombre RE-RUEDA al azar
# (pestaña [P] del monitor, handoff Opus 14:39: «bautizar.sh <rol>» = 🎲; evita repetir
# los nombres ya en uso mientras el pool dé de sí)
if modo not in ("azar", "--reroll"):
    rol, nombre = os.environ["ROL"], os.environ["NOMBRE"]
    p = os.path.join(turnos, rol + ".yaml")
    if not os.path.isfile(p) or not tiene_persona(p):
        print(f"⚠️  {rol}: no existe o no tiene bloque persona"); raise SystemExit(1)
    if not nombre:
        en_uso = set()
        for q in glob.glob(os.path.join(turnos, "*.yaml")):
            for l in leer(q):
                m = re.match(r'\s*nombre_humano:\s*"?([^"\n]+)"?\s*$', l)
                if m:
                    en_uso.add(m.group(1).strip())
        libres = [n for n in pool if n not in en_uso]
        nombre = random.choice(libres or pool)
    poner_nombre(p, nombre); print(f"   ✅ {rol} → «{nombre}»"); raise SystemExit(0)

# modo azar / reroll
random.shuffle(pool)
i = 0
for p in yamls:
    rol = os.path.basename(p)[:-5]
    if not tiene_persona(p):
        continue
    if modo == "azar" and tiene_nombre(p):
        print(f"   · {rol} ya bautizado (idempotente)"); continue
    nombre = pool[i % len(pool)]; i += 1
    poner_nombre(p, nombre); print(f"   ✅ {rol} → «{nombre}»")
PY
